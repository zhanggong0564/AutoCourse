from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import app_logging
from assistant import Assistant

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("自动看课助手")
        self.geometry("780x540")
        self.minsize(700, 460)
        self.events = queue.Queue()
        self.worker = None
        self.logger = app_logging.create_app_logger(ROOT)
        self.logger.info("应用启动")
        self.assistant = Assistant(ROOT, self.log, self.set_status)
        self._build()
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
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.login_button.configure(state="disabled")
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
