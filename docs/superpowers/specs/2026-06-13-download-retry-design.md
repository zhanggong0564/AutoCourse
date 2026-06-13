# Chromium 下载自动重试设计

## 目标

浏览器组件（Chromium）下载经常因网络问题失败。为 `runtime_installer.install_chromium` 增加自动重试，把短暂网络抖动导致的失败自动消化掉，全部重试失败后仍保留现有的手动再点击能力。

## 范围

仅修改 `runtime_installer.py` 及其测试 `tests/test_runtime_installer.py`。`app.py` 不变——它对 `install_chromium` 的调用接口保持不变。

## 架构

把现有 `install_chromium` 的函数体原样抽成私有函数 `_install_chromium_once`（单次尝试：启动 Playwright CLI 子进程、逐行读取输出并回调 `on_progress`、校验返回码与产物、失败抛 `RuntimeError`）。

`install_chromium` 改为重试包装器，对外签名与行为契约保持兼容：

```
install_chromium(browser_dir, on_progress=None) -> str
```

`app.py` 中 `runtime_installer.install_chromium(self.browser_dir, self.log)` 无需改动即获得重试能力。

单次下载逻辑与重试逻辑由此各自独立、各自可测。

## 重试策略

- 最多 3 次尝试（常量 `MAX_ATTEMPTS = 3`）。
- 失败后递增延迟再试，指数退避：第 2 次前等待 2 秒，第 3 次前等待 4 秒（常量 `RETRY_DELAYS = (2, 4)`，长度 = `MAX_ATTEMPTS - 1`）。
- 每次重试之前先清理：删除 `browser_dir` 下所有匹配 `chromium-*` 的目录。上一次尝试是失败抛出的，残留目录必为不完整产物，清理后从干净状态重新下载。第一次尝试不清理。
- `time.sleep` 通过参数注入，便于测试不真正等待：

```
install_chromium(browser_dir, on_progress=None, *, sleep=time.sleep) -> str
```

## 控制流

```
for attempt in 1..MAX_ATTEMPTS:
    if attempt > 1:
        on_progress("清理未完成的下载文件…")
        _clear_partial_download(browser_dir)
        delay = RETRY_DELAYS[attempt - 2]
        on_progress(f"{delay} 秒后进行第 {attempt} 次重试…")
        sleep(delay)
    try:
        return _install_chromium_once(browser_dir, on_progress)
    except RuntimeError as exc:
        last_error = exc
        on_progress(f"第 {attempt} 次下载失败：{exc}")
raise RuntimeError(
    f"已重试 {MAX_ATTEMPTS} 次仍失败，可重新点击“安装组件”再试。最后错误：{last_error}"
)
```

辅助函数：

```
_clear_partial_download(browser_dir):
    for path in browser_dir.glob("chromium-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
```

## 日志反馈

所有提示经 `on_progress`（在 app.py 中即 `self.log`）流向日志面板，与现有日志着色规则配合（"失败"标红，提醒类标琥珀）：

- 单次失败：`第 N 次下载失败：<错误信息>`
- 清理：`清理未完成的下载文件…`
- 重试等待：`<delay> 秒后进行第 N 次重试…`
- 全部失败：最终 `RuntimeError` 消息含「已重试 N 次仍失败，可重新点击"安装组件"再试」。

## 错误处理边界

仅对单次尝试抛出的 `RuntimeError`（下载/校验失败）重试。磁盘满、权限等非网络问题同样会重试，最多多花约 6 秒，无害，不单独区分。`on_progress` 为 `None` 时所有回调安全跳过（与现状一致）。

## 与手动重试的关系

全部自动重试失败后 `install_chromium` 抛出，`app.py` 现有逻辑（`_apply_runtime_state` 在未安装状态下重新启用安装按钮）使用户可再次点击"安装组件"，即"失败后可手动再试"。本设计不改 UI。

## 测试

`tests/test_runtime_installer.py`：

- 现有针对单次行为的用例改为针对 `_install_chromium_once`（行为不变，仅换目标函数）：
  - 运行内置 Playwright 驱动并传递 `PLAYWRIGHT_BROWSERS_PATH`
  - 失败时以安装输出抛 `RuntimeError`
  - 逐行上报进度
- 新增针对 `install_chromium` 重试包装器：
  - 第 2 次尝试成功：`_install_chromium_once` 首次抛错、二次成功，最终返回成功输出
  - 3 次全部失败：抛 `RuntimeError`，消息含「已重试 3 次」与最后错误
  - 重试前清理：重试时 `browser_dir` 下的 `chromium-*` 残留目录被删除
  - 进度日志包含重试与清理提示
  - 注入假 `sleep`，断言以递增秒数 (2, 4) 被调用，且测试不真正等待
- 新增针对 `_clear_partial_download`：删除 `chromium-*` 目录、对不存在目录安全。

## 验收标准

- 下载因网络失败时自动最多重试 3 次，延迟 2、4 秒递增，无需用户干预。
- 每次失败、清理、重试在日志中有清晰中文提示。
- 全部重试失败后抛错并提示可手动再点"安装组件"，且安装按钮确实可再次点击。
- 重试前清理上次残留的 `chromium-*` 目录。
- `app.py` 调用接口不变；全部既有测试经等价迁移后继续通过。
