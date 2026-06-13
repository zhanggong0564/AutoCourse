# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from playwright._impl._driver import compute_driver_executable, get_driver_env

STALL_TIMEOUT = 60
MAX_ATTEMPTS = 3
RETRY_DELAYS = (2, 4)
assert len(RETRY_DELAYS) == MAX_ATTEMPTS - 1


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) if bundle_root else Path(__file__).resolve().parent


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "AutoCourseWatcher"
    return Path(__file__).resolve().parent


def prepare_application_root(resource_dir: Path, application_dir: Path) -> None:
    application_dir.mkdir(parents=True, exist_ok=True)
    config_path = application_dir / "config.json"
    if not config_path.exists():
        shutil.copy2(resource_dir / "config.json", config_path)


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


def _clear_partial_download(browser_dir: Path) -> None:
    for path in browser_dir.glob("chromium-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


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
            try:
                on_progress(segment)
            except Exception:
                pass

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
    browser_dir: Path,
    on_progress: Callable[[str], None] | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    def report(message: str) -> None:
        if on_progress is not None:
            try:
                on_progress(message)
            except Exception:
                pass

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            report("清理未完成的下载文件…")
            _clear_partial_download(browser_dir)
            delay = RETRY_DELAYS[attempt - 2]
            report(f"等待 {delay} 秒后进行第 {attempt} 次重试…")
            sleep(delay)
        try:
            return _install_chromium_once(browser_dir, on_progress)
        except RuntimeError as exc:
            last_error = exc
            report(f"第 {attempt} 次下载失败：{exc}")
    raise RuntimeError(
        f'已重试 {MAX_ATTEMPTS} 次仍失败，可重新点击“安装组件”再试。最后错误：{last_error}'
    )


def _playwright_cli_command() -> list[str]:
    node_path, cli_path = compute_driver_executable()
    return [node_path, cli_path, "install", "chromium"]
