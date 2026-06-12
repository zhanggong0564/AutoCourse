import os

import pytest

import runtime_installer


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


def test_install_chromium_runs_bundled_playwright_driver(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )

    class Process:
        stdout = iter(["download complete\n"])

        def wait(self):
            return 0

    monkeypatch.setattr(
        runtime_installer.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs)) or Process(),
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    output = runtime_installer.install_chromium(browser_dir)

    assert output == "download complete"
    assert calls[0][0] == ["node.exe", "cli.js", "install", "chromium"]
    assert calls[0][1]["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(browser_dir)


def test_install_chromium_raises_with_installer_output(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )

    class Process:
        stdout = iter(["network unavailable\n"])

        def wait(self):
            return 1

    monkeypatch.setattr(runtime_installer.subprocess, "Popen", lambda *a, **k: Process())
    browser_dir = runtime_installer.configure_browser_path(tmp_path)

    with pytest.raises(RuntimeError, match="network unavailable"):
        runtime_installer.install_chromium(browser_dir)


def test_install_chromium_reports_progress_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime_installer,
        "_playwright_cli_command",
        lambda: ["node.exe", "cli.js", "install", "chromium"],
    )
    browser_dir = runtime_installer.configure_browser_path(tmp_path)
    executable = browser_dir / "chromium-1234" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    class Process:
        stdout = iter(["downloading\n", "installed\n"])

        def wait(self):
            return 0

    monkeypatch.setattr(runtime_installer.subprocess, "Popen", lambda *a, **k: Process())
    progress = []

    output = runtime_installer.install_chromium(browser_dir, progress.append)

    assert progress == ["downloading", "installed"]
    assert output == "downloading\ninstalled"
