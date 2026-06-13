# Chromium 下载自动重试设计

## 目标

浏览器组件（Chromium）下载经常因网络问题失败，且常见表现是"卡在某个百分比不动"——进程不退出、不报错，只是停滞。为 `runtime_installer.install_chromium` 增加：

1. 失败自动重试，消化短暂网络抖动；
2. 停滞检测——下载长时间无进展时主动中止，转为一次可重试的失败；

全部重试失败后仍保留现有的手动再点击能力。

## 范围

仅修改 `runtime_installer.py` 及其测试 `tests/test_runtime_installer.py`。`app.py` 不变——它对 `install_chromium` 的调用接口保持不变。

## 架构

把单次下载逻辑收进私有函数 `_install_chromium_once`：启动 Playwright CLI 子进程、**按字符读取输出**并回调 `on_progress`、**带停滞看门狗**、校验返回码与产物、失败（含停滞）抛 `RuntimeError`。输出读取抽成独立的 `_pump_output` 辅助函数以便测试。

`install_chromium` 改为重试包装器，对外签名与行为契约保持兼容：

```
install_chromium(browser_dir, on_progress=None) -> str
```

`app.py` 中 `runtime_installer.install_chromium(self.browser_dir, self.log)` 无需改动即获得重试能力。

单次下载逻辑与重试逻辑由此各自独立、各自可测。

## 停滞检测（解决"卡住不动"）

Playwright 的下载进度条用 `\r` 原地刷新，按行读取（`for line in stdout`）在整个下载期间收不到新行，无法区分"在下载"和"卡死"。因此 `_install_chromium_once` 改为：

- `_pump_output(stream, on_segment, mark_activity)`：从子进程输出流按字符读取，遇 `\r` 或 `\n` 切分出一段非空文本就回调 `on_segment`；**每读到一个字符就调用 `mark_activity()`**。在后台 daemon 线程中运行。
- 主线程看门狗：记录最近一次活动的单调时钟时间（`time.monotonic`，加锁保护）。循环以 `min(1.0, stall_timeout)` 为间隔 `join` 读取线程；若线程已结束则退出循环；若空闲时间 ≥ `STALL_TIMEOUT` 且进程仍存活（`poll() is None`），判定停滞，`process.kill()` 并标记 `stalled`。
- 进程结束后：若 `stalled`，抛 `RuntimeError`（消息含"下载超过 N 秒无进展（疑似卡住），已中止本次尝试"）；否则按原有返回码/产物校验。

`STALL_TIMEOUT = 60`（秒）。下载只要还在一点点推进就会刷新进度条、重置计时，慢网不会误杀；真正零进展 60 秒才中止。为便于测试，`stall_timeout` 与 `monotonic` 时钟作为 `_install_chromium_once` 的关键字参数注入，默认取常量与 `time.monotonic`。

停滞被转成 `RuntimeError`，因此自动落入下方的重试逻辑：清理残留 → 等待 → 重新下载。

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

- 现有针对单次行为的用例改为针对 `_install_chromium_once`（用带 `read`/`poll`/`wait`/`kill` 的假进程）：
  - 运行内置 Playwright 驱动并传递 `PLAYWRIGHT_BROWSERS_PATH`
  - 失败时以安装输出抛 `RuntimeError`
  - 按段上报进度
  - 停滞中止：输出几个字符后流阻塞、进程不退出，注入小 `stall_timeout` 后抛含"卡住"的 `RuntimeError` 并调用了 `kill`
- 针对 `_pump_output`：以 `\r`/`\n` 混合的字符串切分出正确段落，且按字符数调用 `mark_activity`
- 新增针对 `install_chromium` 重试包装器：
  - 第 2 次尝试成功：`_install_chromium_once` 首次抛错、二次成功，最终返回成功输出
  - 3 次全部失败：抛 `RuntimeError`，消息含「已重试 3 次」与最后错误
  - 重试前清理：重试时 `browser_dir` 下的 `chromium-*` 残留目录被删除
  - 进度日志包含重试与清理提示
  - 注入假 `sleep`，断言以递增秒数 (2, 4) 被调用，且测试不真正等待
- 新增针对 `_clear_partial_download`：删除 `chromium-*` 目录、对不存在目录安全。

## 验收标准

- 下载卡住（长时间无进展）时，超过 60 秒自动中止并触发重试，不再无限等待。
- 下载因网络失败时自动最多重试 3 次，延迟 2、4 秒递增，无需用户干预。
- 每次失败、清理、重试在日志中有清晰中文提示。
- 全部重试失败后抛错并提示可手动再点"安装组件"，且安装按钮确实可再次点击。
- 重试前清理上次残留的 `chromium-*` 目录。
- `app.py` 调用接口不变；全部既有测试经等价迁移后继续通过。
