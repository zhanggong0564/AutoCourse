# Persistent Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist GUI activity and complete failure tracebacks in rotating local log files.

**Architecture:** A focused logging module configures one application logger with a UTF-8 rotating file handler. The Tk application forwards user-facing messages and status changes to that logger while preserving its existing event queue behavior.

**Tech Stack:** Python standard library `logging`, `RotatingFileHandler`, pytest

---

### Task 1: Logging Configuration

**Files:**
- Create: `app_logging.py`
- Create: `tests/test_app_logging.py`

- [ ] Write a failing test that expects a dated UTF-8 log file and a 5 MB/five-backup rotating handler.
- [ ] Run `python -m pytest tests/test_app_logging.py -q` and confirm it fails because `app_logging` does not exist.
- [ ] Implement `create_app_logger(root)` with the required handler and format.
- [ ] Run the focused test and confirm it passes.

### Task 2: Application Integration

**Files:**
- Modify: `app.py`
- Modify: `.gitignore`

- [ ] Initialize the logger before constructing `Assistant`.
- [ ] Send GUI messages and status transitions to the logger.
- [ ] Replace the top-level worker error message with `logger.exception` so the traceback is retained.
- [ ] Ignore `logs/` in Git.
- [ ] Run `python -m pytest -q` and `python -m py_compile app.py app_logging.py assistant.py browser.py notifier.py page_actions.py page_logic.py`.
