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


def test_application_root_uses_local_app_data_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert runtime_installer.application_root() == tmp_path / "AutoCourseWatcher"


def test_prepare_application_root_copies_default_config(tmp_path):
    resource_root = tmp_path / "resources"
    application_root = tmp_path / "data"
    resource_root.mkdir()
    (resource_root / "config.json").write_text('{"debug": false}', encoding="utf-8")

    runtime_installer.prepare_application_root(resource_root, application_root)

    assert (application_root / "config.json").read_text(encoding="utf-8") == (
        '{"debug": false}'
    )


def test_configure_browser_path_uses_application_runtime_directory(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    browser_dir = runtime_installer.configure_browser_path(tmp_path)

    assert browser_dir == tmp_path / "runtime" / "ms-playwright"
    assert browser_dir.is_dir()
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(browser_dir)


def test_chromium_is_installed_requires_executable(tmp_path):
    browser_dir = tmp_path / "runtime" / "ms-playwright"
    assert runtime_installer.chromium_is_installed(browser_dir) is False

    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    assert runtime_installer.chromium_is_installed(browser_dir) is True


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


def test_install_chromium_once_survives_progress_callback_errors(tmp_path, monkeypatch):
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

    def boom(_segment):
        raise RuntimeError("logging blew up")

    output = runtime_installer._install_chromium_once(browser_dir, boom)

    assert output == "downloading\ninstalled"


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
    assert any(line.startswith("等待") and "重试" in line for line in progress)


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


def test_install_chromium_retry_survives_progress_errors(tmp_path, monkeypatch):
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    attempts = []

    def fake_once(bd, on_progress=None):
        attempts.append(bd)
        if len(attempts) == 1:
            raise RuntimeError("network reset")
        return "ok"

    monkeypatch.setattr(runtime_installer, "_install_chromium_once", fake_once)

    def boom(_message):
        raise RuntimeError("logging blew up")

    output = runtime_installer.install_chromium(
        browser_dir, boom, sleep=lambda _delay: None
    )

    assert output == "ok"
    assert len(attempts) == 2
