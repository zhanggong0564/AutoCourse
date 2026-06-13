# Chromium 下载自动重试 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `runtime_installer.install_chromium` 在下载失败或长时间卡住时自动重试（最多 3 次、递增延迟、重试前清理残留），全部失败后保留手动再点击能力。

**Architecture:** `_pump_output` 按字符读输出并标记活动；`_install_chromium_once` 单次下载并带停滞看门狗（无进展超时则杀进程抛错）；`_clear_partial_download` 清理 `chromium-*` 残留；`install_chromium` 作为重试包装器。仅改 `runtime_installer.py` 与其测试，`app.py` 调用接口不变。

**Tech Stack:** Python 标准库（subprocess、threading、time、shutil、io、pathlib），pytest，Playwright CLI。

**测试命令：** 仓库根目录运行 `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py -v`（PATH 上的裸 `python` 缺 playwright，跑不了收集）。

**提交规范：** 遵循 `<type>(<scope>): <subject>`，scope 用 `service`；实现与对应测试同 commit。**不加 Co-Authored-By 或任何 trailer。**

---

### Task 1: 带停滞检测的单次下载 `_install_chromium_once`

把单次下载逻辑收进 `_install_chromium_once`，输出读取抽成 `_pump_output`，加停滞看门狗；`install_chromium` 暂作薄包装（下一任务才加重试），保证每次 commit 后 `app.py` 仍可用。迁移既有 3 个安装测试到新接口。

**Files:**
- Modify: `runtime_installer.py`
- Test: `tests/test_runtime_installer.py`

- [ ] **Step 1: 写/迁移测试**

把 `tests/test_runtime_installer.py` 顶部的 import 区：

```python
import os
import sys

import pytest

import runtime_installer
```

替换为（新增 `io`、`threading`，并加一个复用的假进程）：

```python
import io
import os
import sys
import threading

import pytest

import runtime_installer


class _FakeProcess:
    def __init__(self, text, returncode=0):
        self.stdout = io.StringIO(text)
        self._returncode = returncode
        self.killed = False

    def poll(self):
        return self._returncode

    def wait(self):
        return self._returncode

    def kill(self):
        self.killed = True
```

然后把原有的这三个测试函数（连同函数体）整体替换：

原：
```python
def test_install_chromium_runs_bundled_playwright_driver(tmp_path, monkeypatch):
```
```python
def test_install_chromium_raises_with_installer_output(tmp_path, monkeypatch):
```
```python
def test_install_chromium_reports_progress_lines(tmp_path, monkeypatch):
```

替换为下面五个测试（三个迁移 + `_pump_output` + 停滞）：

```python
def test_install_chromium_once_runs_bundled_playwright_driver(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )
    monkeypatch.setattr(
        runtime_installer.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs))
        or _FakeProcess("download complete\n"),
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    output = runtime_installer._install_chromium_once(browser_dir)

    assert output == "download complete"
    assert calls[0][0] == ["node.exe", "cli.js", "install", "chromium"]
    assert calls[0][1]["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(browser_dir)


def test_install_chromium_once_raises_with_installer_output(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )
    monkeypatch.setattr(
        runtime_installer.subprocess,
        "Popen",
        lambda *a, **k: _FakeProcess("network unavailable\n", returncode=1),
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)

    with pytest.raises(RuntimeError, match="network unavailable"):
        runtime_installer._install_chromium_once(browser_dir)


def test_install_chromium_once_reports_progress_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )
    monkeypatch.setattr(
        runtime_installer.subprocess,
        "Popen",
        lambda *a, **k: _FakeProcess("downloading\ninstalled\n"),
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    progress = []

    output = runtime_installer._install_chromium_once(browser_dir, progress.append)

    assert progress == ["downloading", "installed"]
    assert output == "downloading\ninstalled"


def test_pump_output_splits_on_cr_and_lf_and_marks_each_char():
    raw = "downloading\r 50% \rdone\n"
    stream = io.StringIO(raw)
    segments = []
    marks = []

    runtime_installer._pump_output(stream, segments.append, lambda: marks.append(1))

    assert segments == ["downloading", "50%", "done"]
    assert len(marks) == len(raw)


def test_install_chromium_once_aborts_when_download_stalls(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_installer, "_playwright_cli_command", lambda: ["x"])
    stop = threading.Event()

    class StallStream:
        def __init__(self):
            self._chars = list("downloading\r")

        def read(self, _n):
            if self._chars:
                return self._chars.pop(0)
            stop.wait(2.0)
            return ""

    class StallProcess:
        def __init__(self):
            self.stdout = StallStream()
            self.killed = False

        def poll(self):
            return None if not self.killed else -9

        def wait(self):
            return -9

        def kill(self):
            self.killed = True
            stop.set()

    monkeypatch.setattr(
        runtime_installer.subprocess, "Popen", lambda *a, **k: StallProcess()
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)

    with pytest.raises(RuntimeError, match="卡住"):
        runtime_installer._install_chromium_once(browser_dir, stall_timeout=0.1)
```

- [ ] **Step 2: 运行确认失败**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py -v`
Expected: `_once`/`_pump_output` 相关用例 FAIL，`AttributeError: module 'runtime_installer' has no attribute '_pump_output'`（或 `_install_chromium_once`）

- [ ] **Step 3: 实现**

在 `runtime_installer.py` 顶部 import 区：

```python
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable
```

改为：

```python
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable
```

在 `from playwright._impl._driver import compute_driver_executable, get_driver_env` 之后加一行常量：

```python
STALL_TIMEOUT = 60
```

把现有的整个 `install_chromium` 函数（从 `def install_chromium(` 到 `return output`）替换为下面三个定义：

```python
def _pump_output(
    stream,
    on_segment: Callable[[str], None],
    mark_activity: Callable[[], None],
) -> None:
    buffer = ""
    while True:
        chunk = stream.read(1)
        if not chunk:
            break
        mark_activity()
        if chunk in ("\r", "\n"):
            segment = buffer.strip()
            if segment:
                on_segment(segment)
            buffer = ""
        else:
            buffer += chunk
    segment = buffer.strip()
    if segment:
        on_segment(segment)


def _install_chromium_once(
    browser_dir: Path,
    on_progress: Callable[[str], None] | None = None,
    *,
    stall_timeout: float = STALL_TIMEOUT,
    monotonic: Callable[[], float] = time.monotonic,
) -> str:
    env = get_driver_env()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_dir)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        _playwright_cli_command(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    lines: list[str] = []
    last_activity = monotonic()
    activity_lock = threading.Lock()

    def mark_activity() -> None:
        nonlocal last_activity
        with activity_lock:
            last_activity = monotonic()

    def collect(segment: str) -> None:
        lines.append(segment)
        if on_progress is not None:
            on_progress(segment)

    reader = threading.Thread(
        target=_pump_output,
        args=(process.stdout, collect, mark_activity),
        daemon=True,
    )
    reader.start()

    stalled = False
    while True:
        reader.join(timeout=min(1.0, stall_timeout))
        if not reader.is_alive():
            break
        with activity_lock:
            idle = monotonic() - last_activity
        if idle >= stall_timeout and process.poll() is None:
            stalled = True
            process.kill()
            break

    returncode = process.wait()
    reader.join(timeout=5.0)
    output = "\n".join(lines)
    if stalled:
        prefix = output.strip()
        notice = f"下载超过 {stall_timeout:g} 秒无进展（疑似卡住），已中止本次尝试"
        raise RuntimeError(f"{prefix}\n{notice}" if prefix else notice)
    if returncode != 0:
        raise RuntimeError(output.strip() or "Chromium 安装失败")
    if not chromium_is_installed(browser_dir):
        raise RuntimeError("安装命令已结束，但未找到 Chromium 浏览器文件")
    return output


def install_chromium(
    browser_dir: Path, on_progress: Callable[[str], None] | None = None
) -> str:
    return _install_chromium_once(browser_dir, on_progress)
```

- [ ] **Step 4: 运行确认通过**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py -v`
Expected: 全部 PASS（9 个）

- [ ] **Step 5: 提交**

```bash
git add runtime_installer.py tests/test_runtime_installer.py
git commit -m "feat(service): 单次 Chromium 下载支持卡住超时中止"
```

---

### Task 2: 清理残留下载的 `_clear_partial_download`

**Files:**
- Modify: `runtime_installer.py`
- Test: `tests/test_runtime_installer.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_runtime_installer.py` 末尾追加：

```python
def test_clear_partial_download_removes_chromium_dirs(tmp_path):
    browser_dir = tmp_path / "ms-playwright"
    partial = browser_dir / "chromium-1234" / "chrome-win"
    partial.mkdir(parents=True)
    (partial / "partial.bin").write_bytes(b"x")
    (browser_dir / "chromium-9999").mkdir()
    keep = browser_dir / "firefox-1"
    keep.mkdir()

    runtime_installer._clear_partial_download(browser_dir)

    assert not list(browser_dir.glob("chromium-*"))
    assert keep.is_dir()


def test_clear_partial_download_safe_when_empty(tmp_path):
    browser_dir = tmp_path / "ms-playwright"
    browser_dir.mkdir()

    runtime_installer._clear_partial_download(browser_dir)

    assert browser_dir.is_dir()
```

- [ ] **Step 2: 运行确认失败**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py::test_clear_partial_download_removes_chromium_dirs -v`
Expected: FAIL，`AttributeError: module 'runtime_installer' has no attribute '_clear_partial_download'`

- [ ] **Step 3: 实现**

在 `runtime_installer.py` 中 `_install_chromium_once` 之后、`install_chromium` 之前加：

```python
def _clear_partial_download(browser_dir: Path) -> None:
    for path in browser_dir.glob("chromium-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
```

（`shutil` 已在文件顶部导入，无需新增。）

- [ ] **Step 4: 运行确认通过**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py -v`
Expected: 全部 PASS（11 个）

- [ ] **Step 5: 提交**

```bash
git add runtime_installer.py tests/test_runtime_installer.py
git commit -m "feat(service): 增加清理残留 Chromium 下载的辅助函数"
```

---

### Task 3: `install_chromium` 重试包装器

**Files:**
- Modify: `runtime_installer.py`
- Test: `tests/test_runtime_installer.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_runtime_installer.py` 末尾追加：

```python
def test_install_chromium_succeeds_on_second_attempt(tmp_path, monkeypatch):
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    attempts = []

    def fake_once(bd, on_progress=None):
        attempts.append(bd)
        if len(attempts) == 1:
            raise RuntimeError("network reset")
        return "download complete"

    monkeypatch.setattr(runtime_installer, "_install_chromium_once", fake_once)
    slept = []
    progress = []

    output = runtime_installer.install_chromium(
        browser_dir, progress.append, sleep=slept.append
    )

    assert output == "download complete"
    assert len(attempts) == 2
    assert slept == [2]
    assert "第 1 次下载失败：network reset" in progress
    assert any("第 2 次重试" in line for line in progress)


def test_install_chromium_raises_after_all_attempts_fail(tmp_path, monkeypatch):
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    calls = []

    def always_fail(bd, on_progress=None):
        calls.append(bd)
        raise RuntimeError("timeout")

    monkeypatch.setattr(runtime_installer, "_install_chromium_once", always_fail)
    slept = []

    with pytest.raises(RuntimeError, match="已重试 3 次") as excinfo:
        runtime_installer.install_chromium(browser_dir, sleep=slept.append)

    assert "timeout" in str(excinfo.value)
    assert len(calls) == 3
    assert slept == [2, 4]


def test_install_chromium_clears_partial_download_before_retry(tmp_path, monkeypatch):
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    (browser_dir / "chromium-1234").mkdir(parents=True)
    seen_partial = []

    def fake_once(bd, on_progress=None):
        seen_partial.append((bd / "chromium-1234").exists())
        if len(seen_partial) == 1:
            raise RuntimeError("corrupt")
        return "ok"

    monkeypatch.setattr(runtime_installer, "_install_chromium_once", fake_once)

    output = runtime_installer.install_chromium(browser_dir, sleep=lambda _delay: None)

    assert output == "ok"
    assert seen_partial == [True, False]
```

- [ ] **Step 2: 运行确认失败**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py::test_install_chromium_succeeds_on_second_attempt -v`
Expected: FAIL，`TypeError`（`install_chromium` 还不接受 `sleep` 关键字参数）

- [ ] **Step 3: 实现重试包装器**

在 `runtime_installer.py` 的 `STALL_TIMEOUT = 60` 那一行后面补两个常量：

```python
STALL_TIMEOUT = 60
MAX_ATTEMPTS = 3
RETRY_DELAYS = (2, 4)
```

把 Task 1 写入的薄包装：

```python
def install_chromium(
    browser_dir: Path, on_progress: Callable[[str], None] | None = None
) -> str:
    return _install_chromium_once(browser_dir, on_progress)
```

替换为：

```python
def install_chromium(
    browser_dir: Path,
    on_progress: Callable[[str], None] | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            if on_progress is not None:
                on_progress("清理未完成的下载文件…")
            _clear_partial_download(browser_dir)
            delay = RETRY_DELAYS[attempt - 2]
            if on_progress is not None:
                on_progress(f"{delay} 秒后进行第 {attempt} 次重试…")
            sleep(delay)
        try:
            return _install_chromium_once(browser_dir, on_progress)
        except RuntimeError as exc:
            last_error = exc
            if on_progress is not None:
                on_progress(f"第 {attempt} 次下载失败：{exc}")
    raise RuntimeError(
        f"已重试 {MAX_ATTEMPTS} 次仍失败，可重新点击“安装组件”再试。最后错误：{last_error}"
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/test_runtime_installer.py -v`
Expected: 全部 PASS（14 个）

- [ ] **Step 5: 提交**

```bash
git add runtime_installer.py tests/test_runtime_installer.py
git commit -m "feat(service): Chromium 下载失败或卡住自动重试"
```

---

### Task 4: 全量回归

**Files:** 无新改动。

- [ ] **Step 1: 全量测试**

Run: `D:\software\Miniconda3\python.exe -m pytest tests/ -v`
Expected: 全部 PASS（49 个）

- [ ] **Step 2: 导入冒烟**

Run: `D:\software\Miniconda3\python.exe -c "import app; import runtime_installer; print('ok')"`
Expected: 输出 `ok`，无异常（确认 `app.py` 对 `install_chromium` 的调用仍兼容）。
