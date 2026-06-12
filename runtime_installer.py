from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from playwright._impl._driver import compute_driver_executable, get_driver_env


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


def install_chromium(
    browser_dir: Path, on_progress: Callable[[str], None] | None = None
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
    lines = []
    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if line:
                lines.append(line)
                if on_progress is not None:
                    on_progress(line)
    returncode = process.wait()
    output = "\n".join(lines)
    if returncode != 0:
        raise RuntimeError(output.strip() or "Chromium 安装失败")
    if not chromium_is_installed(browser_dir):
        raise RuntimeError("安装命令已结束，但未找到 Chromium 浏览器文件")
    return output


def _playwright_cli_command() -> list[str]:
    node_path, cli_path = compute_driver_executable()
    return [node_path, cli_path, "install", "chromium"]
