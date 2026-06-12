# EXE Runtime Installer Design

## Goal

Allow a packaged Windows EXE to prepare its Playwright Chromium runtime on a new, internet-connected computer without requiring Python, Miniconda, or manual command-line setup.

## Packaging Boundary

- Package Python modules, Playwright, Tkinter, and application code into the EXE with PyInstaller.
- Do not run `pip install` from the packaged application.
- Download only the Playwright Chromium browser runtime after installation.
- Store Chromium in an application-owned writable directory next to user data, not inside PyInstaller's temporary extraction directory.

## User Experience

- On application startup, check whether the required Chromium executable exists.
- If Chromium is available, enable `打开并开始` immediately.
- If Chromium is missing, disable course startup and show an `安装浏览器组件` button.
- Clicking the button starts installation in a background thread and streams progress into the existing log panel.
- On success, update the status and enable course startup.
- On failure, show the error, retain the install button, and allow retry.

## Components

- Add a focused runtime module that resolves the browser directory, detects Chromium, and invokes Playwright's bundled driver installation command.
- Keep subprocess and filesystem work outside the Tk event thread.
- Route installer output through the existing event queue and persistent application log.
- Configure `PLAYWRIGHT_BROWSERS_PATH` before launching Playwright so detection, installation, and browser launch use the same directory.

## Error Handling

- Treat missing network access, download failure, antivirus blocking, and insufficient write permissions as recoverable installation failures.
- Preserve the full subprocess output in `logs/app.log`.
- Never mark the runtime installed solely because the installer command exited; verify that Playwright can resolve a Chromium executable afterward.

## Testing

- Unit-test installed and missing runtime detection.
- Unit-test installer command construction and environment propagation without downloading Chromium.
- Unit-test GUI state transitions through focused, non-network helper behavior.
- Run the existing full test suite and Python compilation checks.

## Build Output

- Add a reproducible PyInstaller build configuration and documentation.
- Include Playwright's Python package and driver resources in the packaged application.
- The produced EXE remains internet-dependent only for the first Chromium installation.
