from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import app_logging
import runtime_installer
from assistant import Assistant

RESOURCE_ROOT = runtime_installer.resource_root()
ROOT = runtime_installer.application_root()
runtime_installer.prepare_application_root(RESOURCE_ROOT, ROOT)
CONFIG_PATH = ROOT / "config.json"

APP_ICON_PNGS = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAN0lEQVR42mNggALL6v3/ScEMyIBUzSiGkKsZbsgwNwAGKDYAnyFEG4DLIPq4YLinA4ozE6XZGQDQdGvd6ZELaQAAAABJRU5ErkJggg==",
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAa0lEQVR42mNgwAIsq/f/pwVmwAdoZSlRjqG35RiOGNkOGCjL4Y4YdcCoA8jRBAID7gAYGHAHUOoIqjiAEodQ1QHkOILqDiDVITRzALEOGX4hMDJzwcgsCUer41EHDIuW8WjHZPB0Tgeyew4AglrT/kuv/40AAAAASUVORK5CYII=",
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAA0ElEQVR42u3bwQ2DMAwF0KzV2TocoxX10F5QKxAksfGzlAH+E4LEwa3trMdzeWVa7WxlC3wZyN2CH4K4e/i/CFXC/0QoDVAt/AYBAIDCAFXDfxEAAAAAAAAAAAB6rneVB/hUeYBoENMAoiBMBYgAEQJgJkIYgFkQ4QBGI4QEGAkRGmAEQniA3hBpAHohpALoAZES4EoIT4B3gK+AfYCdoLOA06B+gI6QnqCusHsBN0PuBgEAAAAAAAD/C/tbHAAAc0OmxswOmh6tF97wdMHx+RUoDcDKtVxVKQAAAABJRU5ErkJggg==",
)

STATUS_COLORS = {
    "success": ("#e6f4ec", "#18734b", "#b9dfca"),
    "info": ("#e8f1fb", "#295f96", "#bfd2e8"),
    "warning": ("#fff8e6", "#715b20", "#e6d29b"),
    "danger": ("#fbeceb", "#a13a32", "#e3b9b6"),
}

LOG_MAX_LINES = 1000
LOG_LINE_COLORS = {"error": "#a13a32", "warning": "#8a6d1f"}


def log_line_kind(message: str) -> str:
    if any(word in message for word in ("失败", "错误", "异常", "报错")):
        return "error"
    if any(word in message for word in ("等待", "暂停", "请")):
        return "warning"
    return "info"


def log_overflow(total_lines: int, max_lines: int = LOG_MAX_LINES) -> int:
    return max(total_lines - max_lines, 0)


def enable_dpi_awareness():
    """启用 Windows DPI 感知，高分屏下界面不再发虚；失败时静默降级。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def scaled_size(width: int, height: int, factor: float):
    factor = max(1.0, min(factor, 3.0))
    return round(width * factor), round(height * factor)


def centered_geometry(width: int, height: int, screen_width: int, screen_height: int):
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) * 2 // 5, 0)
    return f"{width}x{height}+{x}+{y}"


def runtime_button_state(installed: bool, installing: bool):
    if installing:
        return "disabled", "disabled", "正在安装浏览器组件"
    if installed:
        return "normal", "disabled", "就绪"
    return "disabled", "normal", "需要安装浏览器组件"


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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("自动看课助手")
        dpi = self.winfo_fpixels("1i")
        self.tk.call("tk", "scaling", dpi / 72.0)
        self._ui_scale = dpi / 96.0
        width, height = scaled_size(780, 500, self._ui_scale)
        self.geometry(
            centered_geometry(
                width, height, self.winfo_screenwidth(), self.winfo_screenheight()
            )
        )
        self._icon_images = [tk.PhotoImage(data=png) for png in APP_ICON_PNGS]
        self.iconphoto(True, *self._icon_images)
        self.minsize(*scaled_size(720, 430, self._ui_scale))
        self.configure(bg="#eef2f6")
        self.events = queue.Queue()
        self.worker = None
        self.runtime_worker = None
        self.log_visible = False
        self.browser_dir = runtime_installer.configure_browser_path(ROOT)
        self.runtime_installed = runtime_installer.chromium_is_installed(
            self.browser_dir
        )
        self.runtime_installing = False
        self.logger = app_logging.create_app_logger(ROOT)
        self.logger.info("应用启动")
        self.assistant = Assistant(ROOT, self.log, self.set_status)
        self._configure_styles()
        self._build()
        self._apply_runtime_state()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#eef2f6")
        style.configure("Toolbar.TFrame", background="#e7eff8")
        style.configure(
            "Primary.TButton",
            background="#397bbf",
            foreground="white",
            bordercolor="#356ca8",
            padding=(10, 4),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#2f6faa"), ("disabled", "#aab7c5")],
            foreground=[("disabled", "#eef2f6")],
        )
        style.configure(
            "Tool.TButton",
            background="#e7eff8",
            foreground="#273b53",
            bordercolor="#e7eff8",
            padding=(8, 4),
            font=("Microsoft YaHei UI", 9),
        )
        style.map(
            "Tool.TButton",
            background=[("active", "#d4e2f0"), ("disabled", "#e7eff8")],
            foreground=[("disabled", "#8792a0")],
        )
        style.configure(
            "Panel.TLabelframe",
            background="#ffffff",
            bordercolor="#c7d1dd",
            relief="solid",
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background="#dce8f4",
            foreground="#294967",
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(7, 3),
        )
        style.configure("Link.TButton", padding=(4, 1), foreground="#326da8")

    def _build(self):
        self._build_menu()
        self._build_toolbar()

        self.main = ttk.Frame(self, style="App.TFrame", padding=(14, 12, 14, 8))
        self.main.pack(fill="both", expand=True)

        self.banner_wrap = tk.Frame(self.main, bg="#c0453c")
        self.banner = tk.Label(
            self.banner_wrap,
            text="",
            fg="#8f2f27",
            bg="#fbeceb",
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=10,
            pady=8,
            anchor="w",
        )
        self.banner.pack(fill="x", padx=(4, 1), pady=1)

        self._build_overview()

        hint_wrap = tk.Frame(self.main, bg="#d8b54a")
        self.hint_label = tk.Label(
            hint_wrap,
            text="提示：首次启动后，请在浏览器中手动登录。遇到答题时程序会暂停并提醒。",
            fg="#715b20",
            bg="#fff8e6",
            font=("Microsoft YaHei UI", 9),
            padx=10,
            pady=7,
            anchor="w",
        )
        self.hint_label.pack(fill="x", padx=(4, 1), pady=1)
        hint_wrap.pack(fill="x", pady=(10, 0))

        self._build_log_panel()
        self._build_status_bar()
        self._apply_status_presentation("就绪")

    def _build_menu(self):
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开配置", command=self.open_config)
        file_menu.add_command(label="打开日志目录", command=self.open_log_folder)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._close)
        menu.add_cascade(label="文件(F)", menu=file_menu)

        run_menu = tk.Menu(menu, tearoff=False)
        run_menu.add_command(label="开始", command=self.start)
        run_menu.add_command(label="确认已登录", command=self.confirm_login)
        run_menu.add_command(label="停止", command=self.stop)
        menu.add_cascade(label="运行(R)", menu=run_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(label="安装浏览器组件", command=self.install_runtime)
        tools_menu.add_command(label="打开日志目录", command=self.open_log_folder)
        menu.add_cascade(label="工具(T)", menu=tools_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="关于", command=self.show_about)
        menu.add_cascade(label="帮助(H)", menu=help_menu)
        self.configure(menu=menu)

    def _build_toolbar(self):
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(10, 6))
        toolbar.pack(fill="x")

        self.start_button = ttk.Button(
            toolbar, text="▶  开始", command=self.start, style="Primary.TButton"
        )
        self.start_button.pack(side="left")
        self.login_button = ttk.Button(
            toolbar,
            text="✓  已登录",
            command=self.confirm_login,
            state="disabled",
            style="Tool.TButton",
        )
        self.login_button.pack(side="left", padx=(4, 0))
        self.stop_button = ttk.Button(
            toolbar,
            text="■  停止",
            command=self.stop,
            state="disabled",
            style="Tool.TButton",
        )
        self.stop_button.pack(side="left", padx=(4, 0))

        ttk.Separator(toolbar, orient="vertical").pack(
            side="left", fill="y", padx=7, pady=2
        )
        ttk.Button(
            toolbar, text="⚙  配置", command=self.open_config, style="Tool.TButton"
        ).pack(side="left")
        self.install_button = ttk.Button(
            toolbar,
            text="↓  安装组件",
            command=self.install_runtime,
            style="Tool.TButton",
        )
        self.install_button.pack(side="left", padx=(4, 0))

    def _build_overview(self):
        self.overview = ttk.LabelFrame(
            self.main, text="运行概览", style="Panel.TLabelframe", padding=(12, 10)
        )
        self.overview.pack(fill="x")
        self.overview.columnconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="就绪")
        self.component_var = tk.StringVar(value="正在检查")
        self.task_var = tk.StringVar(value="等待开始")

        labels = (("当前状态：", 0), ("浏览器组件：", 1), ("当前任务：", 2))
        for text, row in labels:
            ttk.Label(self.overview, text=text, background="#ffffff").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=4
            )

        self.status_badge = tk.Label(
            self.overview,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=8,
            pady=2,
            anchor="w",
        )
        self.status_badge.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(
            self.overview, textvariable=self.component_var, background="#ffffff"
        ).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(
            self.overview, textvariable=self.task_var, background="#ffffff"
        ).grid(row=2, column=1, sticky="w", pady=4)

    def _build_log_panel(self):
        self.log_panel = ttk.LabelFrame(
            self.main, text="运行日志", style="Panel.TLabelframe", padding=(12, 8)
        )
        self.log_panel.pack(fill="x", pady=(10, 0))

        header = ttk.Frame(self.log_panel)
        header.pack(fill="x")
        self.last_activity_var = tk.StringVar(value="最近活动：暂无")
        ttk.Label(header, textvariable=self.last_activity_var).pack(side="left")
        self.log_toggle_button = ttk.Button(
            header,
            text=log_toggle_text(False),
            command=self.toggle_log,
            style="Link.TButton",
        )
        self.log_toggle_button.pack(side="right")

        self.log_body = ttk.Frame(self.log_panel)
        scrollbar = ttk.Scrollbar(self.log_body, orient="vertical")
        self.log_box = tk.Text(
            self.log_body,
            height=12,
            state="disabled",
            font=("Consolas", 10),
            bg="#fbfcfd",
            fg="#243244",
            relief="solid",
            borderwidth=1,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=self.log_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_box.pack(side="left", fill="both", expand=True)
        for tag, color in LOG_LINE_COLORS.items():
            self.log_box.tag_configure(tag, foreground=color)

        self.log_menu = tk.Menu(self.log_box, tearoff=False)
        self.log_menu.add_command(label="复制", command=self.copy_log)
        self.log_menu.add_command(label="全选", command=self.select_all_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="清空日志", command=self.clear_log)
        self.log_box.bind("<Button-3>", self._show_log_menu)

    def _build_status_bar(self):
        bar = tk.Frame(self, bg="#dce5ee", height=26, highlightthickness=0)
        bar.pack(fill="x", side="bottom")
        self.footer_status_var = tk.StringVar(value="● 就绪")
        self.footer_component_var = tk.StringVar(value="浏览器组件正在检查")
        tk.Label(
            bar,
            textvariable=self.footer_status_var,
            bg="#dce5ee",
            fg="#18734b",
            padx=10,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left", fill="y")
        tk.Frame(bar, bg="#b7c3cf", width=1).pack(side="left", fill="y")
        tk.Label(
            bar,
            textvariable=self.footer_component_var,
            bg="#dce5ee",
            fg="#33475c",
            padx=10,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", fill="y")
        tk.Label(
            bar,
            text="日志：app.log",
            bg="#dce5ee",
            fg="#33475c",
            padx=10,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="right", fill="y")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.login_button.configure(state="normal")
        self.task_var.set("启动浏览器并准备课程")
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def confirm_login(self):
        self.assistant.confirm_login()
        self.login_button.configure(state="disabled")

    def _run(self):
        try:
            self.assistant.run()
        except Exception as exc:
            self.logger.exception("后台任务运行失败")
            self.log(f"运行失败：{exc}")
            self.set_status("运行失败")
        finally:
            self.events.put(("buttons", None))

    def stop(self):
        self.assistant.stop()
        self.set_status("正在停止")

    def install_runtime(self):
        if self.runtime_worker and self.runtime_worker.is_alive():
            return
        self.runtime_installing = True
        self._apply_runtime_state()
        self.runtime_worker = threading.Thread(
            target=self._install_runtime_worker, daemon=True
        )
        self.runtime_worker.start()

    def _install_runtime_worker(self):
        try:
            self.log("开始下载 Chromium 浏览器组件，请保持网络连接。")
            runtime_installer.install_chromium(self.browser_dir, self.log)
            self.events.put(("runtime_ready", None))
        except Exception as exc:
            self.logger.exception("浏览器组件安装失败")
            self.events.put(("runtime_failed", str(exc)))

    def _apply_runtime_state(self):
        start_state, install_state, status = runtime_button_state(
            self.runtime_installed, self.runtime_installing
        )
        self.start_button.configure(state=start_state)
        self.install_button.configure(state=install_state)
        self.status_var.set(status)
        if self.runtime_installing:
            component = "正在安装 Chromium"
        elif self.runtime_installed:
            component = "Chromium 已安装"
        else:
            component = "需要安装 Chromium"
        self.component_var.set(component)
        self.footer_component_var.set(component)
        self._apply_status_presentation(status)

    def _append_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert(
            "end",
            time.strftime("[%H:%M:%S] ") + message + "\n",
            log_line_kind(message),
        )
        total_lines = int(self.log_box.index("end-1c").split(".")[0]) - 1
        overflow = log_overflow(total_lines)
        if overflow:
            self.log_box.delete("1.0", f"{overflow + 1}.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def log(self, message):
        self.logger.info(message)
        self.events.put(("log", message))

    def set_status(self, message):
        self.logger.info("状态：%s", message)
        self.events.put(("status", message))

    def _drain_events(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(value)
                self.last_activity_var.set(f"最近活动：{value}")
            elif kind == "status":
                self.status_var.set(value)
                self.task_var.set(value)
                self._apply_status_presentation(value)
                self._update_banner(value)
            elif kind == "buttons":
                self._apply_runtime_state()
                self.stop_button.configure(state="disabled")
                self.login_button.configure(state="disabled")
                self.task_var.set("等待开始")
            elif kind == "runtime_ready":
                self.runtime_installing = False
                self.runtime_installed = True
                self.log("浏览器组件安装完成。")
                self._apply_runtime_state()
            elif kind == "runtime_failed":
                self.runtime_installing = False
                self.runtime_installed = False
                self.log(f"浏览器组件安装失败：{value}")
                self._apply_runtime_state()
        self.after(100, self._drain_events)

    def _update_banner(self, status):
        if status in ("等待答题", "等待人工处理"):
            self.banner.configure(text=f"⚠  {status}：请到浏览器手动处理")
            self.banner_wrap.pack(fill="x", pady=(0, 10), before=self.overview)
        else:
            self.banner_wrap.pack_forget()

    def _apply_status_presentation(self, status):
        kind, text = status_presentation(status)
        background, foreground, border = STATUS_COLORS[kind]
        self.status_badge.configure(
            text=text,
            bg=background,
            fg=foreground,
            highlightbackground=border,
            highlightthickness=1,
        )
        self.footer_status_var.set(text)

    def _show_log_menu(self, event):
        try:
            self.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_menu.grab_release()

    def copy_log(self):
        try:
            text = self.log_box.get("sel.first", "sel.last")
        except tk.TclError:
            text = self.log_box.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def select_all_log(self):
        self.log_box.focus_set()
        self.log_box.tag_add("sel", "1.0", "end-1c")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.last_activity_var.set("最近活动：暂无")

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_panel.pack_configure(fill="both", expand=True)
            self.log_body.pack(fill="both", expand=True, pady=(6, 0))
        else:
            self.log_body.pack_forget()
            self.log_panel.pack_configure(fill="x", expand=False)
        self.log_toggle_button.configure(text=log_toggle_text(self.log_visible))

    def open_config(self):
        os.startfile(CONFIG_PATH)

    def open_log_folder(self):
        log_dir = ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)

    def show_about(self):
        messagebox.showinfo(
            "关于自动看课助手",
            "自动看课助手\n\n用于自动播放未完成课程，遇到答题时会暂停并提醒。",
            parent=self,
        )

    def _close(self):
        self.logger.info("应用关闭")
        self.assistant.stop()
        self.destroy()


if __name__ == "__main__":
    enable_dpi_awareness()
    App().mainloop()
