# 经典桌面界面实施计划

> **执行要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行本计划。各步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 在保留全部看课自动化行为的前提下，将当前朴素的 Tkinter 布局替换为已确认的紧凑型 Windows 桌面工具界面。

**架构：** 继续由 `App` 负责 GUI 控制，并保留现有后台线程和事件队列。增加小型纯函数描述状态的颜色与文字，使其无需创建 Tk 窗口即可测试；随后只围绕这些函数重构 `_build`、提示横幅和日志显示逻辑。

**技术栈：** Python 3、Tkinter/ttk、pytest

---

## 文件结构

- 修改 `app.py`：增加展示辅助函数、ttk 样式、菜单与工具栏、概览面板、可折叠日志面板和状态栏。
- 修改 `tests/test_app_runtime.py`：在现有运行时按钮行为测试之外，覆盖状态展示和日志切换文字。
- 修改 `README.md`：说明紧凑工具栏和日志折叠交互。

### 任务 1：测试界面展示模型

**涉及文件：**
- 修改：`tests/test_app_runtime.py`
- 修改：`app.py`

- [ ] **步骤 1：编写失败的状态展示测试**

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

- [ ] **步骤 2：运行测试并确认处于红灯阶段**

运行：`python -m pytest tests/test_app_runtime.py -v`

预期：测试收集失败，因为 `status_presentation` 和 `log_toggle_text` 尚不存在。

- [ ] **步骤 3：实现最小化纯辅助函数**

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

- [ ] **步骤 4：运行专项测试并确认处于绿灯阶段**

运行：`python -m pytest tests/test_app_runtime.py -v`

预期：该文件中的全部测试通过。

- [ ] **步骤 5：提交界面展示模型**

```powershell
git add -- app.py tests/test_app_runtime.py
git commit -m "feat(service): 添加界面状态展示模型"
```

### 任务 2：构建经典桌面界面框架

**涉及文件：**
- 修改：`app.py`

- [ ] **步骤 1：配置紧凑型 ttk 样式**

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

- [ ] **步骤 2：增加菜单栏**

创建 `_build_menu`，包含文件、运行、工具和帮助菜单。菜单命令连接到现有的 `start`、`confirm_login`、`stop`、`open_config` 和 `install_runtime` 方法。增加 `open_log_folder`，通过 `os.startfile(ROOT / "logs")` 打开日志目录；打开前使用 `mkdir(parents=True, exist_ok=True)` 创建目录。

- [ ] **步骤 3：用桌面工具区域重构 `_build`**

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

- [ ] **步骤 4：增加运行概览与状态字段**

Use `StringVar` values for current status, component state, and current task. Display the status in a colored `tk.Label` and update it from `_apply_status_presentation`. Keep `status_var` as the source of truth for compatibility with the existing event loop.

- [ ] **步骤 5：运行语法检查和专项回归测试**

运行：

```powershell
python -m py_compile app.py
python -m pytest tests/test_app_runtime.py -v
```

预期：编译成功，专项测试全部通过。

- [ ] **步骤 6：提交桌面界面框架**

```powershell
git add -- app.py
git commit -m "feat(service): 重构经典桌面工具界面"
```

### 任务 3：增加可折叠日志和状态配色

**涉及文件：**
- 修改：`app.py`

- [ ] **步骤 1：初始化日志折叠状态**

Set `self.log_visible = False` before `_build`. Place `log_box` inside `self.log_body`, but do not pack `log_body` during initial construction.

- [ ] **步骤 2：实现日志展开和收起行为**

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

- [ ] **步骤 3：根据展示模型应用状态配色**

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

- [ ] **步骤 4：重做人工处理提示横幅样式**

Keep `_update_banner` conditions unchanged. Use a pale red background and dark red text instead of a full red strip. Pack it above the overview panel, and hide it for all other states.

- [ ] **步骤 5：验证专项行为**

运行：

```powershell
python -m py_compile app.py
python -m pytest tests/test_app_runtime.py -v
```

预期：编译成功，全部专项测试通过。

- [ ] **步骤 6：提交日志折叠和状态配色**

```powershell
git add -- app.py
git commit -m "feat(service): 增加折叠日志与状态配色"
```

### 任务 4：补充文档并验证最终界面

**涉及文件：**
- 修改：`README.md`

- [ ] **步骤 1：更新使用说明**

Add a short interface section explaining:

```markdown
## 界面

- 顶部工具栏提供开始、确认登录、停止、配置和浏览器组件安装操作。
- 运行概览显示当前状态、浏览器组件状态和当前任务。
- 详细日志默认折叠，点击“显示详细日志”可展开查看，不影响日志文件记录。
- 底部状态栏持续显示运行状态和日志位置。
```

- [ ] **步骤 2：运行完整测试套件**

运行：`python -m pytest -v`

预期：全部测试通过，失败数为零。

- [ ] **步骤 3：启动应用并进行视觉验证**

运行：`python app.py`

Verify manually:

- Window opens without an exception.
- Menu and compact toolbar render correctly.
- Start and install buttons reflect the current Chromium state.
- Log panel starts collapsed and toggles in both directions.
- Resizing the window expands the log text area when visible.
- Waiting-answer status shows the pale red banner.

- [ ] **步骤 4：提交使用文档**

```powershell
git add -- README.md
git commit -m "docs(docs): 更新桌面界面使用说明"
```

- [ ] **步骤 5：检查最终仓库状态**

运行：

```powershell
git status --short
git log -6 --oneline
```

预期：没有非预期改动，每个提交只包含一个范围和一项职责。
