# 自动看课助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个带 Tkinter 图形界面的本机工具，打开浏览器让用户手动登录一次，随后自动遍历 zjzx.ah.cn 上"未学习"的课程、按正常速度播放视频、自动点掉挂机弹窗、自动翻节，遇到答题则暂停并提醒用户手动完成。

**Architecture:** GUI（`app.py`）在工作线程里运行调度器（`assistant.py`）；调度器用 `browser.py` 启动持久化 Chromium，用 `page_actions.py` 操作页面；`page_actions.py` 的所有判定逻辑下沉到纯函数模块 `page_logic.py`（可单元测试），DOM 操作本身靠调试模式 + 真实网站手动验证。提醒由 `notifier.py` 发声。配置集中在 `config.json`。

**Tech Stack:** Python 3.10+、Playwright（同步 API，Chromium）、Tkinter（标准库 GUI）、pytest（单元测试）、winsound（标准库提示音）。

> **注意：** 本目录已有一份同名的原型文件（`app.py`/`config.json`/`README.md` 等，未纳入 git）。本计划按"从零开始"重写这些文件，会覆盖原型内容——这是用户已确认的。

---

## 文件结构

| 文件 | 职责 | 可单元测试 |
|---|---|---|
| `config.json` | 全部可调配置：start_url、关键字列表、轮询间隔、调试开关 | — |
| `page_logic.py` | 纯判定函数：关键字匹配、进度解析、答题/完成/需人工判定 | ✅ TDD |
| `page_actions.py` | Playwright DOM 操作：找课程、播放视频、点弹窗、翻节、读进度、调试导出 | 手动验证 |
| `browser.py` | 浏览器生命周期：启动持久化 Chromium、登录检测 | 手动验证 |
| `notifier.py` | 提示音 | 手动验证 |
| `assistant.py` | 总调度循环，串联以上模块 | 手动验证 |
| `app.py` | Tkinter 界面 + 工作线程 + 事件队列 | 手动验证 |
| `requirements.txt` | 依赖声明 | — |
| `tests/test_page_logic.py` | `page_logic` 的单元测试 | — |
| `README.md` | 安装与使用说明 | — |

**测试边界：** 只有 `page_logic.py` 做严格 TDD（纯函数、无浏览器依赖）。DOM/GUI 模块无法可靠单测，按计划里的"手动验证步骤"对真实网站验证。

---

## Task 0: 项目环境与测试骨架

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: 写 requirements.txt**

```
playwright>=1.52,<2
pytest>=8,<9
```

- [ ] **Step 2: 写 pytest.ini（让 pytest 找到根目录模块）**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: 建空的 tests 包**

`tests/__init__.py` 内容为空文件即可。

- [ ] **Step 4: 安装依赖与浏览器内核**

Run:
```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```
Expected: 依赖安装成功；Chromium 下载完成（首次较慢）。

- [ ] **Step 5: 验证 pytest 可运行**

Run: `python -m pytest -q`
Expected: `no tests ran`（0 个测试，无错误）。

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py
git commit -m "chore: 初始化项目依赖与测试骨架"
```

---

## Task 1: 配置文件 config.json

**Files:**
- Create: `config.json`

- [ ] **Step 1: 写 config.json**

```json
{
  "start_url": "https://www.zjzx.ah.cn/personcenter?type=train",
  "browser": "chromium",
  "profile_dir": ".browser-profile",
  "poll_seconds": 5,
  "stuck_minutes": 5,
  "debug": false,
  "login_keywords": ["培训", "课程", "学习"],
  "course_keywords": ["未学习", "未完成", "继续学习", "开始学习", "去学习"],
  "completed_keywords": ["已完成", "100%"],
  "quiz_keywords": ["答题", "测验", "试题", "提交答案", "单选题", "多选题", "请选择正确答案"],
  "idle_popup_keywords": ["你还在吗", "继续学习", "我知道了", "继续观看", "确定"],
  "human_keywords": ["验证码", "人脸", "活体", "拖动滑块", "确认本人"],
  "next_section_keywords": ["下一节", "下一章", "继续学习"]
}
```

- [ ] **Step 2: 验证 JSON 合法**

Run: `python -c "import json,pathlib; json.loads(pathlib.Path('config.json').read_text(encoding='utf-8')); print('ok')"`
Expected: 打印 `ok`。

- [ ] **Step 3: Commit**

```bash
git add config.json
git commit -m "feat: 新增 config.json 配置"
```

---

## Task 2: 纯判定逻辑 page_logic.py（TDD）

**Files:**
- Create: `page_logic.py`
- Test: `tests/test_page_logic.py`

- [ ] **Step 1: 写失败测试 — contains_any**

`tests/test_page_logic.py`:
```python
import page_logic


def test_contains_any_found():
    assert page_logic.contains_any("这门课未学习", ["未学习", "去学习"]) is True


def test_contains_any_not_found():
    assert page_logic.contains_any("已完成", ["未学习", "去学习"]) is False
```

- [ ] **Step 2: 运行，确认失败**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'page_logic'`。

- [ ] **Step 3: 写最小实现**

`page_logic.py`:
```python
from __future__ import annotations


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
```

- [ ] **Step 4: 运行，确认通过**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: 2 passed。

- [ ] **Step 5: 追加失败测试 — parse_progress**

在 `tests/test_page_logic.py` 末尾追加：
```python
def test_parse_progress_finds_percent_line():
    text = "课程名称\n学习进度 30%\n讲师介绍很长很长的一段文字" + "x" * 60
    assert page_logic.parse_progress(text) == "学习进度 30%"


def test_parse_progress_ignores_long_lines():
    text = "这是一段超过五十个字符并且包含百分号 50% 的很长很长很长很长很长很长的描述文字"
    assert page_logic.parse_progress(text) is None


def test_parse_progress_returns_none_without_percent():
    assert page_logic.parse_progress("课程名称\n讲师介绍") is None
```

- [ ] **Step 6: 运行，确认新测试失败**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: FAIL，`AttributeError: module 'page_logic' has no attribute 'parse_progress'`。

- [ ] **Step 7: 实现 parse_progress**

在 `page_logic.py` 追加：
```python
def parse_progress(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if "%" in line and len(line) < 50:
            return line
    return None
```

- [ ] **Step 8: 运行，确认全部通过**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: 5 passed。

- [ ] **Step 9: 追加失败测试 — 三个委托判定**

在 `tests/test_page_logic.py` 末尾追加：
```python
def test_is_completed():
    assert page_logic.is_completed("状态：已完成", ["已完成", "100%"]) is True
    assert page_logic.is_completed("状态：未学习", ["已完成", "100%"]) is False


def test_is_quiz():
    assert page_logic.is_quiz("请完成本节单选题", ["单选题", "测验"]) is True
    assert page_logic.is_quiz("正在播放视频", ["单选题", "测验"]) is False


def test_needs_human():
    assert page_logic.needs_human("请输入验证码", ["验证码", "人脸"]) is True
    assert page_logic.needs_human("正常播放中", ["验证码", "人脸"]) is False
```

- [ ] **Step 10: 运行，确认失败**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: FAIL，缺少 `is_completed` 等属性。

- [ ] **Step 11: 实现三个委托函数**

在 `page_logic.py` 追加：
```python
def is_completed(text: str, completed_keywords: list[str]) -> bool:
    return contains_any(text, completed_keywords)


def is_quiz(text: str, quiz_keywords: list[str]) -> bool:
    return contains_any(text, quiz_keywords)


def needs_human(text: str, human_keywords: list[str]) -> bool:
    return contains_any(text, human_keywords)
```

- [ ] **Step 12: 运行，确认全部通过**

Run: `python -m pytest tests/test_page_logic.py -q`
Expected: 8 passed。

- [ ] **Step 13: Commit**

```bash
git add page_logic.py tests/test_page_logic.py
git commit -m "feat: 新增 page_logic 纯判定逻辑及单元测试"
```

---

## Task 3: 提示音 notifier.py

**Files:**
- Create: `notifier.py`

- [ ] **Step 1: 写实现**

`notifier.py`:
```python
from __future__ import annotations


def play_alert() -> None:
    """答题等需人工处理时发出提示音。Windows 用 winsound，其它平台静默降级。"""
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        # 非 Windows 或无声卡：忽略，提醒仍会通过界面横幅显示
        pass
```

- [ ] **Step 2: 验证导入与调用不报错**

Run: `python -c "import notifier; notifier.play_alert(); print('ok')"`
Expected: 打印 `ok`（可能听到一声提示音）。

- [ ] **Step 3: Commit**

```bash
git add notifier.py
git commit -m "feat: 新增 notifier 提示音"
```

---

## Task 4: 浏览器生命周期 browser.py

**Files:**
- Create: `browser.py`

- [ ] **Step 1: 写实现**

`browser.py`:
```python
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Page

import page_logic


def launch_context(pw, profile_dir: Path, browser: str = "chromium") -> BrowserContext:
    browser_type = getattr(pw, browser)
    return browser_type.launch_persistent_context(
        str(profile_dir),
        headless=False,
        viewport={"width": 1380, "height": 900},
        args=["--start-maximized"],
    )


def body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=2000)
    except Exception:
        return ""


def is_logged_in(page: Page, login_keywords: list[str]) -> bool:
    if "personcenter" not in page.url:
        return False
    return page_logic.contains_any(body_text(page), login_keywords)
```

- [ ] **Step 2: 验证导入**

Run: `python -c "import browser; print(hasattr(browser, 'launch_context'), hasattr(browser, 'is_logged_in'))"`
Expected: 打印 `True True`。

- [ ] **Step 3: Commit**

```bash
git add browser.py
git commit -m "feat: 新增 browser 浏览器生命周期与登录检测"
```

---

## Task 5: 页面操作 page_actions.py

**Files:**
- Create: `page_actions.py`

- [ ] **Step 1: 写实现**

`page_actions.py`:
```python
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeoutError

import page_logic
from browser import body_text


def find_unwatched_course(page: Page, config: dict):
    """在列表页找一个未完成课程的可点击入口，找不到返回 None。"""
    completed = config["completed_keywords"]
    candidates = page.locator("a, button, [role=button]")
    for keyword in config["course_keywords"]:
        matches = candidates.filter(has_text=keyword)
        for index in range(matches.count()):
            item = matches.nth(index)
            try:
                ancestor = item.locator(
                    "xpath=ancestor::*[self::li or self::tr or contains(@class,'course')][1]"
                )
                surrounding = (
                    ancestor.inner_text(timeout=500)
                    if ancestor.count()
                    else item.inner_text()
                )
                if item.is_visible() and not page_logic.contains_any(surrounding, completed):
                    return item
            except PWTimeoutError:
                continue
    return None


def play_videos(page: Page) -> None:
    """把页面内所有 frame 中暂停且未结束的 video 播放起来。"""
    for frame in page.frames:
        try:
            frame.locator("video").evaluate_all(
                "vs => vs.filter(v => v.paused && !v.ended).forEach(v => v.play())"
            )
        except Exception:
            pass


def dismiss_idle_popup(page: Page, config: dict) -> bool:
    """检测并点掉挂机弹窗的确认按钮，点掉返回 True。"""
    for label in config["idle_popup_keywords"]:
        button = _visible_with_text(page, label)
        if button is not None:
            try:
                button.click(timeout=1000)
                return True
            except Exception:
                continue
    return False


def go_next_section(page: Page, config: dict) -> bool:
    """点击"下一节"等按钮，成功返回 True。"""
    for label in config["next_section_keywords"]:
        button = _visible_with_text(page, label)
        if button is not None:
            try:
                button.click(timeout=1000)
                return True
            except Exception:
                continue
    return False


def videos_finished(page: Page) -> bool:
    """页面里存在 video 且全部 ended 才返回 True；没有 video 返回 False。"""
    found = False
    for frame in page.frames:
        try:
            states = frame.locator("video").evaluate_all("vs => vs.map(v => v.ended)")
            if states:
                found = True
                if not all(states):
                    return False
        except Exception:
            pass
    return found


def dump_debug(page: Page, root: Path, log) -> None:
    """调试模式：把候选元素与当前页 HTML 写出，供调选择器。"""
    log(f"[调试] URL: {page.url}")
    candidates = page.locator("a, button, [role=button]")
    count = min(candidates.count(), 40)
    for i in range(count):
        item = candidates.nth(i)
        try:
            if item.is_visible():
                text = (item.inner_text(timeout=300) or "").strip().replace("\n", " ")
                if text:
                    log(f"[调试] 可点元素: {text[:40]}")
        except Exception:
            pass
    try:
        html_path = root / f"debug-page-{int(time.time())}.html"
        html_path.write_text(page.content(), encoding="utf-8")
        log(f"[调试] 已导出页面 HTML: {html_path.name}")
    except Exception as exc:
        log(f"[调试] 导出 HTML 失败: {exc}")


def _visible_with_text(page: Page, label: str):
    items = page.locator("a, button, [role=button]").filter(has_text=label)
    for i in range(items.count()):
        try:
            if items.nth(i).is_visible():
                return items.nth(i)
        except Exception:
            continue
    return None
```

- [ ] **Step 2: 验证导入与函数齐全**

Run:
```bash
python -c "import page_actions as p; print(all(hasattr(p,n) for n in ['find_unwatched_course','play_videos','dismiss_idle_popup','go_next_section','videos_finished','dump_debug']))"
```
Expected: 打印 `True`。

- [ ] **Step 3: Commit**

```bash
git add page_actions.py
git commit -m "feat: 新增 page_actions 页面操作与调试导出"
```

---

## Task 6: 调度器 assistant.py

**Files:**
- Create: `assistant.py`

- [ ] **Step 1: 写实现**

`assistant.py`:
```python
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


class Assistant:
    def __init__(self, root: Path, log, status):
        self.root = root
        self.log = log
        self.status = status
        self.stop_event = threading.Event()
        self.config = json.loads((root / "config.json").read_text(encoding="utf-8"))

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        self.stop_event.clear()
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
        self.status("等待登录")
        while not self.stop_event.is_set():
            if browser.is_logged_in(page, self.config["login_keywords"]):
                self.log("已进入个人中心，开始查找未完成课程。")
                return
            time.sleep(2)

    def _study_loop(self, context, list_page) -> None:
        while not self.stop_event.is_set():
            self.status("查找未完成课程")
            list_page.bring_to_front()
            list_page.goto(self.config["start_url"], wait_until="domcontentloaded")
            list_page.wait_for_timeout(1500)

            if self.config.get("debug"):
                page_actions.dump_debug(list_page, self.root, self.log)

            target = page_actions.find_unwatched_course(list_page, self.config)
            if target is None:
                self.log("没有找到未完成课程。可能已全部看完，或不在培训课程列表。")
                self.status("未找到待学课程")
                return

            label = (target.inner_text() or "课程").strip().replace("\n", " ")
            self.log(f"打开：{label[:40]}")
            old_pages = set(context.pages)
            target.click()
            list_page.wait_for_timeout(1500)
            new_pages = [p for p in context.pages if p not in old_pages]
            course_page = new_pages[-1] if new_pages else list_page
            course_page.wait_for_load_state("domcontentloaded")

            self._watch_course(course_page)

            if course_page is not list_page and not course_page.is_closed():
                course_page.close()

    def _watch_course(self, page) -> None:
        self.status("正在学习")
        self.log("课程页面已打开，将按网站正常速度播放。")
        last_progress = ""
        last_change = time.time()
        poll = self.config["poll_seconds"]

        while not self.stop_event.is_set() and not page.is_closed():
            text = browser.body_text(page)

            if page_logic.needs_human(text, self.config["human_keywords"]):
                self.status("等待人工处理")
                self.log("检测到验证码/人脸等需本人处理，请在浏览器完成。")
                notifier.play_alert()
                time.sleep(poll)
                continue

            if page_logic.is_quiz(text, self.config["quiz_keywords"]):
                self.status("等待答题")
                self.log("检测到答题，请到浏览器手动作答。答完后将自动继续。")
                notifier.play_alert()
                page.bring_to_front()
                time.sleep(poll)
                continue

            if self.config.get("debug"):
                page_actions.dump_debug(page, self.root, self.log)

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
```

- [ ] **Step 2: 验证导入**

Run: `python -c "import assistant; print(hasattr(assistant, 'Assistant'))"`
Expected: 打印 `True`。

- [ ] **Step 3: Commit**

```bash
git add assistant.py
git commit -m "feat: 新增 assistant 总调度循环"
```

---

## Task 7: 图形界面 app.py

**Files:**
- Create: `app.py`

- [ ] **Step 1: 写实现**

`app.py`:
```python
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

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
            container, text="", fg="white", bg="#c0392b",
            font=("Microsoft YaHei UI", 12, "bold"), pady=6,
        )
        # 横幅默认隐藏，需要答题时显示

        row = ttk.Frame(container)
        row.pack(fill="x")
        self.start_button = ttk.Button(row, text="打开并开始", command=self.start)
        self.start_button.pack(side="left")
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
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _run(self):
        try:
            self.assistant.run()
        except Exception as exc:
            self.log(f"运行失败：{exc}")
            self.set_status("运行失败")
        finally:
            self.events.put(("buttons", None))

    def stop(self):
        self.assistant.stop()
        self.set_status("正在停止")

    def log(self, message):
        self.events.put(("log", message))

    def set_status(self, message):
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
        self.assistant.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
```

- [ ] **Step 2: 验证界面能起来（手动）**

Run: `python app.py`
Expected: 弹出"自动看课助手"窗口，有"打开并开始/停止/打开配置"按钮和日志框。**先不要点开始**，确认界面正常后关闭窗口。

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: 新增 Tkinter 图形界面"
```

---

## Task 8: 真实网站联调（路线 C 调试 + 端到端验证）

**Files:**
- Modify: `config.json`（按调试结果调整关键字/选择器，按需）
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: 写 .gitignore（避免提交浏览器资料与调试产物）**

`.gitignore`:
```
.browser-profile/
debug-page-*.html
__pycache__/
*.pyc
```

- [ ] **Step 2: 开启调试模式跑一次列表页**

把 `config.json` 的 `"debug"` 改成 `true`，运行 `python app.py`，点"打开并开始"，在浏览器手动登录。
观察日志里的 `[调试] 可点元素:` 输出和导出的 `debug-page-*.html`。
Expected: 能在日志/HTML 里看到课程列表真实的按钮文字与结构。

- [ ] **Step 3: 按真实结构校准 config.json**

对照调试输出，确认/修正 `course_keywords`、`completed_keywords`、`idle_popup_keywords`、`quiz_keywords`、`next_section_keywords` 是否与网站真实文案一致；不一致则改 `config.json`。
若纯关键字无法定位（路线 B），在 `page_actions.py` 对应函数里改用精确选择器（针对调试 HTML 里观察到的 class/结构）。

- [ ] **Step 4: 端到端验证一门课**

把 `"debug"` 改回 `false`，重新运行，点"打开并开始"。
Expected：软件自动打开一门未学课程、视频开始播放；出现挂机弹窗能自动点掉；出现答题时界面顶部显示红色横幅"⚠ 等待答题"、响提示音、浏览器被提到最前；手动答完后软件自动继续；一节结束后自动进下一节。
逐条核对以上行为，不符的回到 Step 3 调整。

- [ ] **Step 5: 验证"全部看完"与"停止"**

确认：所有未学课程处理完后日志提示"没有找到未完成课程"并停止；运行中点"停止"能正常停下、浏览器关闭。

- [ ] **Step 6: 写 README.md**

`README.md`:
```markdown
# 自动看课助手

带图形界面的本机工具：打开浏览器、由你手动登录一次，之后自动播放未学习的培训课程、点掉挂机弹窗、自动翻节。遇到答题会暂停并提醒，由你手动作答。

## 安装

1. 安装 Python 3.10+（勾选 Add Python to PATH）。
2. 命令行执行：
   ```
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```

## 使用

1. 运行 `python app.py`。
2. 点"打开并开始"，首次在弹出的浏览器中手动登录（验证码/短信都由你完成）。
3. 保持浏览器打开。软件会自动查找并播放未完成课程。
4. 出现答题时，界面会显示红色横幅并响提示音，请到浏览器手动作答，答完后自动继续。

## 配置

编辑 `config.json`：
- `course_keywords` / `completed_keywords`：未完成、已完成的文案。
- `idle_popup_keywords`：挂机弹窗确认按钮文案。
- `quiz_keywords`：判定"出现答题"的文案。
- `poll_seconds`：检查间隔。
- `debug`：设为 `true` 会把页面候选元素与 HTML 写到日志/文件，用于排查选择器。

登录数据存在 `.browser-profile`，请勿分享。登录异常时关闭软件并删除该目录后重登。

## 边界

本工具不替你答题、不绕过验证码/人脸/风控、按网站正常速度播放、不伪造进度、不保存密码。请实际参与课程学习。
```

- [ ] **Step 7: 全量测试与提交**

Run: `python -m pytest -q`
Expected: 8 passed。

```bash
git add .gitignore README.md config.json page_actions.py
git commit -m "docs: 新增 README 与 gitignore，按真实网站校准配置"
```

---

## Self-Review 结果

- **Spec 覆盖：** 登录(Task 4/6)、找未学课程(Task 5/6)、播放(Task 5)、挂机弹窗自动点(Task 5/6)、答题暂停提醒(Task 3/6/7)、翻节(Task 5/6)、出错与卡死重试(Task 6)、调试模式(Task 5/6 + Task 8)、纯逻辑单测(Task 2)、运行说明(Task 8)、边界声明(README) —— 均有对应任务。
- **占位符：** 无 TBD/TODO；所有代码步骤含完整代码。
- **类型/命名一致性：** `Assistant(root, log, status)`、`browser.launch_context/body_text/is_logged_in`、`page_actions.find_unwatched_course/play_videos/dismiss_idle_popup/go_next_section/videos_finished/dump_debug`、`page_logic.contains_any/parse_progress/is_completed/is_quiz/needs_human` 在各任务间签名一致。
- **DOM/GUI 不做假单测：** 仅 `page_logic` 走 TDD，其余按手动验证步骤——与 spec 测试策略一致。
