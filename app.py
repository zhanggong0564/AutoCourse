from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import app_logging
import runtime_installer
from assistant import Assistant

RESOURCE_ROOT = runtime_installer.resource_root()
ROOT = runtime_installer.application_root()
runtime_installer.prepare_application_root(RESOURCE_ROOT, ROOT)
CONFIG_PATH = ROOT / "config.json"


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
        self.geometry("780x540")
        self.minsize(700, 460)
        self.events = queue.Queue()
        self.worker = None
        self.runtime_worker = None
        self.browser_dir = runtime_installer.configure_browser_path(ROOT)
        self.runtime_installed = runtime_installer.chromium_is_installed(
            self.browser_dir
        )
        self.runtime_installing = False
        self.logger = app_logging.create_app_logger(ROOT)
        self.logger.info("应用启动")
        self.assistant = Assistant(ROOT, self.log, self.set_status)
        self._build()
        self._apply_runtime_state()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        container = ttk.Frame(self, padding=18)
        container.pack(fill="both", expand=True)
        ttk.Label(
            container, text="自动看课助手", font=("Microsoft YaHei UI", 18, "bold")
        ).pack(anchor="w")
        ttk.Label(
            container,
            text="首次启动请在浏览器中手动登录。遇到答题会暂停并提醒，请到浏览器手动作答。",
            wraplength=720,
        ).pack(anchor="w", pady=(6, 12))

        self.banner = tk.Label(
            container,
            text="",
            fg="white",
            bg="#c0392b",
            font=("Microsoft YaHei UI", 12, "bold"),
            pady=6,
        )

        row = ttk.Frame(container)
        row.pack(fill="x")
        self.start_button = ttk.Button(row, text="打开并开始", command=self.start)
        self.start_button.pack(side="left")
        self.login_button = ttk.Button(
            row, text="我已登录", command=self.confirm_login, state="disabled"
        )
        self.login_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(row, text="停止", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(row, text="打开配置", command=self.open_config).pack(side="left")
        self.install_button = ttk.Button(
            row, text="安装浏览器组件", command=self.install_runtime
        )
        self.install_button.pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(row, textvariable=self.status_var).pack(side="right")

        self.log_box = tk.Text(container, height=20, state="disabled", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, pady=(14, 0))

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.login_button.configure(state="normal")
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
                self.log_box.configure(state="normal")
                self.log_box.insert("end", time.strftime("[%H:%M:%S] ") + value + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind == "status":
                self.status_var.set(value)
                self._update_banner(value)
            elif kind == "buttons":
                self._apply_runtime_state()
                self.stop_button.configure(state="disabled")
                self.login_button.configure(state="disabled")
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
            self.banner.configure(text=f"⚠ {status}：请到浏览器手动处理")
            self.banner.pack(fill="x", pady=(0, 8), before=self.log_box)
        else:
            self.banner.pack_forget()

    def open_config(self):
        os.startfile(CONFIG_PATH)

    def _close(self):
        self.logger.info("应用关闭")
        self.assistant.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
