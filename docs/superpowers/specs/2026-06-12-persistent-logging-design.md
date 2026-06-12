# Persistent Logging Design

## Goal

Persist application diagnostics locally so failures can be investigated without copying text from the GUI.

## Design

- Add `app_logging.py` as the single owner of file logging configuration.
- Write UTF-8 logs to `logs/app-YYYY-MM-DD.log`.
- Use a 5 MB rotating handler and retain five backup files.
- Keep the existing GUI log stream; `App.log()` sends each message to both destinations.
- Record status transitions and full exception tracebacks.
- Ignore generated logs in Git.

## Verification

- Unit-test file creation, Unicode messages, exception tracebacks, and rotation settings.
- Run the complete pytest suite and Python syntax compilation.
