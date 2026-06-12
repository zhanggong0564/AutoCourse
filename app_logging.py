from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def create_app_logger(root: Path) -> logging.Logger:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"auto_course_watcher.{root.resolve()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    for old_log in log_dir.iterdir():
        if old_log.is_file():
            try:
                old_log.unlink()
            except PermissionError:
                pass
    for old_html in root.glob("debug-*.html"):
        try:
            old_html.unlink()
        except PermissionError:
            pass

    handler = RotatingFileHandler(
        log_dir / "app.log",
        mode="w",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s")
    )
    logger.addHandler(handler)
    return logger
