# Classic Desktop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current plain Tkinter layout with the approved compact Windows desktop-tool interface while preserving all course automation behavior.

**Architecture:** Keep `App` as the GUI controller and retain its existing worker threads and event queue. Add small pure functions for status presentation so color and text behavior can be tested without creating a Tk window, then rebuild only `_build`, banner presentation, and log visibility around those functions.

**Tech Stack:** Python 3, Tkinter/ttk, pytest

---

## File Structure

- Modify `app.py`: add presentation helpers, ttk styles, menu/toolbar, overview panel, collapsible log panel, and status bar.
- Modify `tests/test_app_runtime.py`: cover status presentation and log toggle text in addition to existing runtime button behavior.
- Modify `README.md`: describe the compact toolbar and collapsible log interaction.

### Task 1: Test the UI presentation model

**Files:**
- Modify: `tests/test_app_runtime.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing status presentation tests**

Add imports and tests:

```python
from app import log_toggle_text, status_presentation


def test_status_presentation_for_ready_state():
    assert status_presentation("就绪") == ("success", "● 就绪")


def test_status_presentation_for_manual_action():
    assert status_presentation("等待答题") == ("danger", "● 等待答题")


def test_status_presentation_for_processing_and_failure():
    assert status_presentation("正在停止") == ("info", "● 正在停止")
    assert status_presentation("运行失败") == ("danger", "● 运行失败")


def test_log_toggle_text_matches_visibility():
    assert log_toggle_text(False) == "显示详细日志 ▼"
    assert log_toggle_text(True) == "隐藏详细日志 ▲"
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_app_runtime.py -v`

Expected: collection fails because `status_presentation` and `log_toggle_text` do not exist.

- [ ] **Step 3: Implement the minimal pure helpers**

Add near `runtime_button_state` in `app.py`:

```python
def status_presentation(status: str):
    if status in ("等待答题", "等待人工处理", "运行失败"):
        return "danger", f"● {status}"
    if status in ("就绪", "运行正常"):
        return "success", f"● {status}"
    if "登录" in status:
        return "warning", f"● {status}"
    return "info", f"● {status}"


def log_toggle_text(visible: bool):
    return "隐藏详细日志 ▲" if visible else "显示详细日志 ▼"
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_app_runtime.py -v`

Expected: all tests in the file pass.

- [ ] **Step 5: Commit the presentation model**

```powershell
git add -- app.py tests/test_app_runtime.py
git commit -m "feat(service): 添加界面状态展示模型"
```

### Task 2: Build the classic desktop shell

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Configure compact ttk styles**

Add `_configure_styles` and call it before `_build`:

```python
def _configure_styles(self):
    style = ttk.Style(self)
    style.theme_use("vista" if "vista" in style.theme_names() else "clam")
    style.configure("Toolbar.TFrame", background="#e7eff8")
    style.configure("Primary.TButton", padding=(10, 4))
    style.configure("Tool.TButton", padding=(8, 4))
    style.configure("Panel.TLabelframe", background="#ffffff")
    style.configure("Panel.TLabelframe.Label", foreground="#294967")
```

- [ ] **Step 2: Add the menu bar**

Create `_build_menu` with File, Run, Tools, and Help menus. Wire commands to existing `start`, `confirm_login`, `stop`, `open_config`, and `install_runtime` methods. Add `open_log_folder` using `os.startfile(ROOT / "logs")`; create the logs directory first with `mkdir(parents=True, exist_ok=True)`.

- [ ] **Step 3: Replace `_build` with desktop regions**

Construct these widgets in order:

```python
self.toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 6))
self.toolbar.pack(fill="x")

self.main = ttk.Frame(self, padding=(14, 12, 14, 8))
self.main.pack(fill="both", expand=True)

self.overview = ttk.LabelFrame(
    self.main, text="运行概览", style="Panel.TLabelframe", padding=(12, 10)
)
self.overview.pack(fill="x")

self.log_panel = ttk.LabelFrame(
    self.main, text="运行日志", style="Panel.TLabelframe", padding=(8, 6)
)
self.log_panel.pack(fill="both", expand=True, pady=(10, 0))

self.status_bar = tk.Frame(self, bg="#dce5ee", height=26)
self.status_bar.pack(fill="x", side="bottom")
```

Use a compact horizontal toolbar. Keep references to all existing buttons so runtime and worker-state methods continue to configure them.

- [ ] **Step 4: Add overview and status fields**

Use `StringVar` values for current status, component state, and current task. Display the status in a colored `tk.Label` and update it from `_apply_status_presentation`. Keep `status_var` as the source of truth for compatibility with the existing event loop.

- [ ] **Step 5: Run syntax and focused regression checks**

Run:

```powershell
python -m py_compile app.py
python -m pytest tests/test_app_runtime.py -v
```

Expected: compilation succeeds and focused tests pass.

- [ ] **Step 6: Commit the desktop shell**

```powershell
git add -- app.py
git commit -m "feat(service): 重构经典桌面工具界面"
```

### Task 3: Add collapsible logs and state colors

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Initialize collapsed log state**

Set `self.log_visible = False` before `_build`. Place `log_box` inside `self.log_body`, but do not pack `log_body` during initial construction.

- [ ] **Step 2: Implement the toggle behavior**

```python
def toggle_log(self):
    self.log_visible = not self.log_visible
    if self.log_visible:
        self.log_body.pack(fill="both", expand=True, pady=(6, 0))
    else:
        self.log_body.pack_forget()
    self.log_toggle_button.configure(text=log_toggle_text(self.log_visible))
```

Keep inserting every log event into `log_box` even when `log_body` is hidden. Update a `last_activity_var` with the newest log line.

- [ ] **Step 3: Apply state colors from the presentation model**

Add a palette:

```python
STATUS_COLORS = {
    "success": ("#e6f4ec", "#18734b", "#b9dfca"),
    "info": ("#e8f1fb", "#295f96", "#bfd2e8"),
    "warning": ("#fff8e6", "#715b20", "#e6d29b"),
    "danger": ("#fbeceb", "#a13a32", "#e3b9b6"),
}
```

`_apply_status_presentation` must set the status label text, foreground, background, and highlight color, and mirror the text to the bottom status bar.

- [ ] **Step 4: Restyle the manual-action banner**

Keep `_update_banner` conditions unchanged. Use a pale red background and dark red text instead of a full red strip. Pack it above the overview panel, and hide it for all other states.

- [ ] **Step 5: Verify focused behavior**

Run:

```powershell
python -m py_compile app.py
python -m pytest tests/test_app_runtime.py -v
```

Expected: compilation succeeds and all focused tests pass.

- [ ] **Step 6: Commit log and color behavior**

```powershell
git add -- app.py
git commit -m "feat(service): 增加折叠日志与状态配色"
```

### Task 4: Document and verify the finished interface

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update usage documentation**

Add a short interface section explaining:

```markdown
## 界面

- 顶部工具栏提供开始、确认登录、停止、配置和浏览器组件安装操作。
- 运行概览显示当前状态、浏览器组件状态和当前任务。
- 详细日志默认折叠，点击“显示详细日志”可展开查看，不影响日志文件记录。
- 底部状态栏持续显示运行状态和日志位置。
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -v`

Expected: all tests pass with zero failures.

- [ ] **Step 3: Launch the application for visual verification**

Run: `python app.py`

Verify manually:

- Window opens without an exception.
- Menu and compact toolbar render correctly.
- Start and install buttons reflect the current Chromium state.
- Log panel starts collapsed and toggles in both directions.
- Resizing the window expands the log text area when visible.
- Waiting-answer status shows the pale red banner.

- [ ] **Step 4: Commit documentation**

```powershell
git add -- README.md
git commit -m "docs(docs): 更新桌面界面使用说明"
```

- [ ] **Step 5: Inspect final repository state**

Run:

```powershell
git status --short
git log -6 --oneline
```

Expected: no unintended changes; commits each contain one scope and responsibility.
