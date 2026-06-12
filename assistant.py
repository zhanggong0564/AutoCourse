from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser
import notifier
import page_actions
import page_logic
import runtime_installer


class Assistant:
    def __init__(self, root: Path, log, status):
        self.root = root
        self.browser_dir = runtime_installer.configure_browser_path(root)
        self.log = log
        self.status = status
        self.stop_event = threading.Event()
        self.login_event = threading.Event()
        self.config = json.loads((root / "config.json").read_text(encoding="utf-8"))

    def stop(self) -> None:
        self.stop_event.set()

    def confirm_login(self) -> None:
        """界面点“我已登录”时调用，解除等待登录的阻塞。"""
        self.login_event.set()

    def run(self) -> None:
        self.stop_event.clear()
        self.login_event.clear()
        profile_dir = self.root / self.config["profile_dir"]
        profile_dir.mkdir(exist_ok=True)
        self.status("正在启动浏览器")

        with sync_playwright() as pw:
            context = browser.launch_context(pw, profile_dir, self.config["browser"])
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(self.config["start_url"], wait_until="domcontentloaded")
                self.log("浏览器已打开。首次使用请在网页中手动登录。")
                self._wait_for_login(page)
                if not self.stop_event.is_set():
                    self._study_loop(context, page)
            finally:
                self.status("已停止")
                context.close()

    def _wait_for_login(self, page) -> None:
        self.status("等待登录：登录后请点界面上的“我已登录”")
        self.log("请在浏览器中登录并进入培训课程列表，然后点界面上的“我已登录”按钮。")
        while not self.stop_event.is_set():
            if self.login_event.is_set():
                self.log("已确认登录，开始查找未完成课程。")
                return
            time.sleep(0.5)

    def _study_loop(self, context, list_page) -> None:
        # 以用户点“我已登录”时所在的页面作为课程列表页；看完课后回到这里，
        # 不再强制跳回仪表盘 start_url（那只是个人主页，不含课程列表）。
        list_url = list_page.url
        self.log(f"课程列表页：{list_url}")
        attempted: set[str] = set()
        while not self.stop_event.is_set():
            self.status("查找未完成课程")
            list_page.bring_to_front()
            if list_page.url != list_url:
                list_page.goto(list_url, wait_until="domcontentloaded")
            list_page.wait_for_timeout(1500)

            if self.config.get("debug"):
                page_actions.dump_debug(list_page, self.root, self.log, self.config)

            found = self._find_course_with_wait(list_page, attempted)
            if found is None:
                self.log("没有找到可处理的未完成课程。可能已全部看完，或入口需手动点。")
                self.status("未找到待学课程")
                return

            target, key = found
            attempted.add(key)
            self.log(f"打开课程：{key}")

            old_pages = set(context.pages)
            before_url = list_page.url
            before_text = browser.body_text(list_page)
            target.click()
            list_page.wait_for_timeout(2500)
            new_pages = [page for page in context.pages if page not in old_pages]

            if new_pages:
                course_page = new_pages[-1]
                self.log(f"课程在新标签打开：{course_page.url}")
            elif list_page.url != before_url:
                course_page = list_page
                self.log(f"课程在当前标签打开：{list_page.url}")
            elif self._content_changed(list_page, before_text):
                # 单页应用：URL 不变但页面内容已切换（出现视频或文本大幅变化）
                course_page = list_page
                self.log("课程在当前页面内打开（单页应用，URL 未变）。")
            else:
                self.log("点击后页面无变化（可能没点中真正的课程入口），跳过该项。")
                continue

            course_page.wait_for_load_state("domcontentloaded")
            self._watch_course(course_page)

            if course_page is not list_page and not course_page.is_closed():
                course_page.close()
            elif course_page is list_page:
                # 课程在列表页内打开过，返回列表需要重新加载
                list_page.goto(list_url, wait_until="domcontentloaded")

    def _content_changed(self, page, before_text: str) -> bool:
        if page_actions.has_video(page):
            return True
        after_text = browser.body_text(page)
        if not before_text:
            return bool(after_text)
        ratio = len(after_text) / max(len(before_text), 1)
        return ratio < 0.7 or ratio > 1.3

    def _find_course_with_wait(self, page, attempted=None, attempts=10, delay_ms=1500):
        for attempt in range(attempts):
            target = page_actions.find_unwatched_course(page, self.config, attempted)
            if target is not None:
                return target
            if attempt < attempts - 1:
                page.wait_for_timeout(delay_ms)
        return None

    def _watch_course(self, page) -> None:
        self.status("正在学习")
        self.log("课程页面已打开，将按网站正常速度播放。")
        last_progress = ""
        last_change = time.time()
        poll = self.config["poll_seconds"]

        # 调试模式下，课程页一打开就先导出结构（在答题判断之前，避免误判后再也抓不到）。
        if self.config.get("debug"):
            page.wait_for_timeout(2000)
            page_actions.dump_debug(page, self.root, self.log, self.config)

        while not self.stop_event.is_set() and not page.is_closed():
            text = browser.body_text(page)

            if page_logic.needs_human(text, self.config["human_keywords"]):
                self.status("等待人工处理")
                self.log("检测到验证码/人脸等需本人处理，请在浏览器完成。")
                notifier.play_alert()
                time.sleep(poll)
                continue

            # 仅当“页面没有视频可播”时才把答题字样当作需人工作答，
            # 否则有视频就先播，避免侧栏出现“测验”二字就误判卡死。
            if page_logic.is_quiz(text, self.config["quiz_keywords"]) and not page_actions.has_video(page):
                self.status("等待答题")
                self.log("检测到答题且页面无视频，请到浏览器手动作答。答完后将自动继续。")
                notifier.play_alert()
                page.bring_to_front()
                time.sleep(poll)
                continue

            self.status("正在学习")

            if page_actions.dismiss_idle_popup(page, self.config):
                self.log("已自动关闭挂机检测弹窗。")

            page_actions.play_videos(page)

            progress = page_logic.parse_progress(text)
            if progress and progress != last_progress:
                self.log(f"当前进度：{progress}")
                last_progress = progress
                last_change = time.time()

            if page_logic.is_completed(text, self.config["completed_keywords"]):
                self.log("当前内容显示已完成。")
                if not page_actions.go_next_section(page, self.config):
                    self.log("没有下一节，本门课程结束。")
                    return
                page.wait_for_timeout(1500)
                last_change = time.time()
                continue

            if page_actions.videos_finished(page):
                if page_actions.go_next_section(page, self.config):
                    self.log("本节播放结束，进入下一节。")
                    page.wait_for_timeout(1500)
                    last_change = time.time()
                    continue

            if time.time() - last_change > self.config["stuck_minutes"] * 60:
                self.log("长时间无进度，刷新页面重试。")
                try:
                    page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                last_change = time.time()

            time.sleep(poll)
