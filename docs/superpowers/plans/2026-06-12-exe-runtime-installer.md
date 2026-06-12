# EXE Runtime Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the packaged Windows application detect and install Playwright Chromium from the GUI on a new internet-connected computer.

**Architecture:** A new `runtime_installer.py` module owns the application browser directory, installation detection, environment configuration, and Playwright driver subprocess. The Tk application calls it from background threads and communicates through the existing event queue. PyInstaller bundles Python code and Playwright driver resources, while Chromium is downloaded on first use.

**Tech Stack:** Python 3.10, Tkinter, Playwright, subprocess, PyInstaller, pytest

---

### Task 1: Browser Runtime Detection and Installation

**Files:**
- Create: `runtime_installer.py`
- Create: `tests/test_runtime_installer.py`

- [ ] **Step 1: Write failing runtime path and detection tests**

```python
from pathlib import Path

import runtime_installer


def test_configure_browser_path_uses_application_runtime_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    assert browser_dir == tmp_path / "runtime" / "ms-playwright"
    assert browser_dir.is_dir()
    assert runtime_installer.os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browser_dir)


def test_chromium_is_installed_requires_executable(tmp_path):
    browser_dir = tmp_path / "runtime" / "ms-playwright"
    assert runtime_installer.chromium_is_installed(browser_dir) is False
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    assert runtime_installer.chromium_is_installed(browser_dir) is True
```

- [ ] **Step 2: Run tests and verify missing module failure**

Run: `python -m pytest tests/test_runtime_installer.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'runtime_installer'`.

- [ ] **Step 3: Implement browser path and detection**

```python
from __future__ import annotations

import os
from pathlib import Path


def configure_browser_path(root: Path) -> Path:
    browser_dir = root / "runtime" / "ms-playwright"
    browser_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_dir)
    return browser_dir


def chromium_is_installed(browser_dir: Path) -> bool:
    patterns = (
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome-win64/chrome.exe",
    )
    return any(any(browser_dir.glob(pattern)) for pattern in patterns)
```

- [ ] **Step 4: Write failing installer command test**

```python
def test_install_chromium_runs_bundled_playwright_driver(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["driver.exe", "install", "chromium"],
    )

    class Result:
        returncode = 0
        stdout = "download complete"

    monkeypatch.setattr(
        runtime_installer.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or Result(),
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    output = runtime_installer.install_chromium(browser_dir)

    assert output == "download complete"
    assert calls[0][0] == ["driver.exe", "install", "chromium"]
    assert calls[0][1]["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(browser_dir)
```

- [ ] **Step 5: Implement subprocess installation and post-check**

Use Playwright's bundled driver executable and CLI JavaScript from the installed package. Run the command with `CREATE_NO_WINDOW` on Windows, capture combined stdout/stderr as UTF-8 text, raise `RuntimeError` for a nonzero return code, and raise if `chromium_is_installed()` remains false after a successful command.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_runtime_installer.py -q`

Expected: all runtime installer tests pass without downloading Chromium.

- [ ] **Step 7: Commit**

```powershell
git add runtime_installer.py tests/test_runtime_installer.py
git commit -m "feat(service): 添加 Chromium 运行时安装器"
```

### Task 2: GUI Installation Workflow

**Files:**
- Modify: `app.py`
- Create: `tests/test_app_runtime.py`

- [ ] **Step 1: Write failing state helper tests**

Create a small pure helper `runtime_button_state(installed: bool, installing: bool)` returning the start-button state, install-button state, and status text. Test these cases:

```python
def test_runtime_state_when_missing():
    assert runtime_button_state(False, False) == (
        "disabled",
        "normal",
        "需要安装浏览器组件",
    )


def test_runtime_state_while_installing():
    assert runtime_button_state(False, True) == (
        "disabled",
        "disabled",
        "正在安装浏览器组件",
    )


def test_runtime_state_when_installed():
    assert runtime_button_state(True, False) == ("normal", "disabled", "就绪")
```

- [ ] **Step 2: Verify the tests fail because the helper is missing**

Run: `python -m pytest tests/test_app_runtime.py -q`

Expected: import failure for `runtime_button_state`.

- [ ] **Step 3: Add runtime controls to the Tk application**

In `App.__init__`, call `configure_browser_path(ROOT)` before creating `Assistant`, detect Chromium, and initialize button states. Add an `安装浏览器组件` button beside `打开配置`. Keep `打开并开始` disabled while Chromium is unavailable or installation is running.

- [ ] **Step 4: Add background installation**

Implement `install_runtime()` to start one daemon thread. The worker calls `install_chromium()`, logs captured installer output, posts a `runtime_ready` event on success, and posts a `runtime_failed` event containing the exception text on failure. Extend `_drain_events()` to update buttons and status on the Tk thread.

- [ ] **Step 5: Verify focused and full tests**

Run: `python -m pytest tests/test_app_runtime.py -q`

Expected: all GUI state tests pass.

Run: `python -m pytest -q`

Expected: complete suite passes.

- [ ] **Step 6: Commit**

```powershell
git add app.py tests/test_app_runtime.py
git commit -m "feat(service): 增加浏览器组件安装入口"
```

### Task 3: Shared Browser Path at Launch

**Files:**
- Modify: `browser.py`
- Modify: `assistant.py`
- Modify: `tests/test_assistant.py`

- [ ] **Step 1: Write a failing environment propagation test**

Test that constructing `Assistant` after `configure_browser_path(root)` leaves `PLAYWRIGHT_BROWSERS_PATH` pointing at `root/runtime/ms-playwright`, and that `Assistant.run()` does not replace it.

- [ ] **Step 2: Run the test and verify expected failure**

Run: `python -m pytest tests/test_assistant.py -q`

Expected: the new path assertion fails until launch setup uses the shared runtime configuration.

- [ ] **Step 3: Configure the path before Playwright starts**

Ensure `PLAYWRIGHT_BROWSERS_PATH` is configured before entering `sync_playwright()`. Keep `browser.launch_context()` unchanged except for clearer `FileNotFoundError` translation if Chromium disappears after startup detection.

- [ ] **Step 4: Run tests and compilation**

Run: `python -m pytest -q`

Expected: complete suite passes.

Run: `python -m py_compile app.py runtime_installer.py assistant.py browser.py`

Expected: exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add assistant.py browser.py tests/test_assistant.py
git commit -m "fix(service): 统一 Chromium 安装与启动路径"
```

### Task 4: PyInstaller Build and Documentation

**Files:**
- Create: `auto-course-watcher.spec`
- Create: `build.ps1`
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] **Step 1: Add PyInstaller dependency**

Append `pyinstaller>=6,<7` to `requirements.txt`.

- [ ] **Step 2: Create the PyInstaller spec**

Use `collect_data_files("playwright")` and `collect_submodules("playwright")`, include `config.json`, build a windowed executable named `自动看课助手`, and keep runtime data outside `_MEIPASS` by resolving writable paths from the executable directory.

- [ ] **Step 3: Create the build command**

```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m PyInstaller --noconfirm --clean auto-course-watcher.spec
Write-Host "构建完成：dist\\自动看课助手.exe" -ForegroundColor Green
```

- [ ] **Step 4: Document development, build, and first-run flows**

Update README with:

```powershell
conda activate base
python -m pip install -r requirements.txt
.\build.ps1
```

Document that a new computer runs the EXE directly, clicks `安装浏览器组件` once while online, and then uses `打开并开始`.

- [ ] **Step 5: Verify build configuration and tests**

Run: `python -m pytest -q`

Expected: complete suite passes.

Run: `python -m PyInstaller --noconfirm --clean auto-course-watcher.spec`

Expected: `dist/自动看课助手.exe` is created without missing-module errors.

- [ ] **Step 6: Commit**

```powershell
git add auto-course-watcher.spec build.ps1 requirements.txt README.md
git commit -m "chore(deps): 添加 Windows EXE 构建配置"
```
