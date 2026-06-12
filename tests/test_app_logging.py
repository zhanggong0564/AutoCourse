import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import app_logging


def test_create_app_logger_starts_with_fresh_log_and_debug_html(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app-2026-06-12.log").write_text("旧日志", encoding="utf-8")
    (log_dir / "app.log.1").write_text("旧备份", encoding="utf-8")
    old_html = tmp_path / "debug-page-old.html"
    old_html.write_text("旧页面", encoding="utf-8")

    logger = app_logging.create_app_logger(tmp_path)

    logger.info("应用启动")
    try:
        raise RuntimeError("测试异常")
    except RuntimeError:
        logger.exception("运行失败")

    handler = next(
        item for item in logger.handlers if isinstance(item, RotatingFileHandler)
    )
    handler.flush()

    log_files = list(log_dir.iterdir())
    assert [item.name for item in log_files] == ["app.log"]
    assert old_html.exists() is False
    content = (log_dir / "app.log").read_text(encoding="utf-8")
    assert "应用启动" in content
    assert "运行失败" in content
    assert "RuntimeError: 测试异常" in content
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 5


def test_create_app_logger_does_not_crash_when_old_file_is_locked(
    tmp_path, monkeypatch
):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    locked_log = log_dir / "old.log"
    locked_log.write_text("旧日志", encoding="utf-8")
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == locked_log:
            raise PermissionError("file is in use")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)

    logger = app_logging.create_app_logger(tmp_path)
    logger.info("新实例启动")
    for handler in logger.handlers:
        handler.flush()

    assert "新实例启动" in (log_dir / "app.log").read_text(encoding="utf-8")
