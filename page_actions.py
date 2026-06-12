from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeoutError

import page_logic


def find_unwatched_course(page: Page, config: dict, attempted: set[str] | None = None):
    """优先找视频学习入口，排除考试/答题/测验入口，跳过本会话已尝试过的课程行。

    返回 (元素, 课程行键) 元组；找不到返回 None。
    键取所在行（课程名等）的文字而非按钮文字——所有按钮都叫“去学习”，按钮文字没法区分课程。
    """
    attempted = attempted or set()
    completed = config["completed_keywords"]
    preferred = config.get(
        "video_entry_keywords", ["视频", "播放", "课件", "学习"]
    )
    excluded = config.get(
        "excluded_entry_keywords", ["考试", "答题", "测验", "考核"]
    )
    candidates = page.locator("a, button, [role=button]")
    ranked = []
    for index in range(candidates.count()):
        item = candidates.nth(index)
        try:
            if not item.is_visible():
                continue
            label = (item.inner_text(timeout=500) or "").strip()
            priority = page_logic.course_candidate_priority(
                label,
                config["course_keywords"],
                preferred,
                excluded,
            )
            if priority is None:
                continue
            ancestor = item.locator(
                "xpath=ancestor::*[self::li or self::tr or contains(@class,'course')][1]"
            )
            surrounding = (
                ancestor.inner_text(timeout=500) if ancestor.count() else label
            )
            key = " ".join(surrounding.split())[:60]
            if key in attempted:
                continue
            if not page_logic.contains_any(surrounding, completed):
                ranked.append((priority, index, item, key))
        except PWTimeoutError:
            continue
    if not ranked:
        return None
    best = min(ranked, key=lambda entry: (entry[0], entry[1]))
    return best[2], best[3]


def has_video(page: Page) -> bool:
    """页面任一 frame 内存在 <video> 元素则返回 True。"""
    for frame in page.frames:
        try:
            if frame.locator("video").count() > 0:
                return True
        except Exception:
            pass
    return False


def play_videos(page: Page) -> None:
    """确保视频在播放：已在播则什么都不做；暂停则 play()；没有 video 才点启动按钮。

    关键：视频播放中绝不去点控制栏按钮，否则会把它暂停、反复抖动并触发平台报错。
    """
    for frame in page.frames:
        try:
            playing = frame.locator("video").evaluate_all(
                "vs => vs.some(v => !v.paused && !v.ended && v.readyState > 2)"
            )
        except Exception:
            playing = False
        if playing:
            continue

        try:
            resumed = frame.locator("video").evaluate_all(
                "vs => { let n = 0; vs.forEach(v => { if (v.paused && !v.ended) { v.play(); n++; } }); return n; }"
            )
        except Exception:
            resumed = 0
        if resumed:
            continue

        # 没有可播放的 video：点 xgplayer 中央大播放按钮启动（它点击后才创建 <video>）
        for selector in (".xgplayer-start", ".vjs-big-play-button"):
            try:
                btn = frame.locator(selector).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=1000)
                    break
            except Exception:
                continue


def video_current_time(page: Page) -> float:
    """返回所有 frame 中 video 的最大 currentTime（秒）；没有 video 返回 0。

    用于判断视频是否真的在推进——比页面显示的百分比可靠（后者每 300 秒才更新）。
    """
    best = 0.0
    for frame in page.frames:
        try:
            value = frame.locator("video").evaluate_all(
                "vs => vs.length ? Math.max(...vs.map(v => v.currentTime || 0)) : 0"
            )
            if isinstance(value, (int, float)):
                best = max(best, float(value))
        except Exception:
            pass
    return best


def read_player_error(page: Page) -> str:
    """读取 xgplayer / video.js 错误层的文字，没有则返回空串（用于诊断播放失败）。"""
    for frame in page.frames:
        for selector in (".xgplayer-error", ".xgplayer-enter-tips", ".vjs-error-display"):
            try:
                el = frame.locator(selector).first
                if el.count() and el.is_visible():
                    text = (el.inner_text(timeout=500) or "").strip()
                    if text:
                        return " ".join(text.split())
            except Exception:
                continue
    return ""


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
    """点击“下一节”等按钮，成功返回 True。"""
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


def dump_debug(page: Page, root: Path, log, config: dict | None = None) -> None:
    """逐个 frame 把候选元素与 HTML 写出，供调试选择器（课程常嵌在 iframe）。"""
    frames = page.frames
    log(f"[调试] URL: {page.url}  共 {len(frames)} 个 frame")
    ts = int(time.time())
    course_keywords = (config or {}).get("course_keywords", [])
    for fi, frame in enumerate(frames):
        # 输出课程入口元素的真实形态（标签/href/target/class），用于确定点击方式
        for keyword in course_keywords:
            try:
                details = frame.evaluate(
                    "(kw) => Array.from(document.querySelectorAll('a,button,[role=button]'))"
                    ".filter(e => e.innerText && e.innerText.includes(kw))"
                    ".slice(0, 5)"
                    ".map(e => ({tag: e.tagName, href: e.getAttribute('href'),"
                    " target: e.getAttribute('target'), cls: (e.className || '').slice(0, 60)}))",
                    keyword,
                )
                for d in details:
                    log(
                        f"[调试] 入口[{keyword}]: <{d['tag']}> href={d['href']} "
                        f"target={d['target']} class={d['cls']}"
                    )
            except Exception:
                pass
    for fi, frame in enumerate(frames):
        try:
            furl = frame.url
        except Exception:
            furl = "?"
        log(f"[调试] frame#{fi}: {furl}")
        shown = 0
        try:
            candidates = frame.locator("a, button, [role=button]")
            count = min(candidates.count(), 30)
            for index in range(count):
                item = candidates.nth(index)
                try:
                    if item.is_visible():
                        text = (item.inner_text(timeout=300) or "").strip().replace("\n", " ")
                        if text:
                            log(f"[调试]   frame#{fi} 可点: {text[:40]}")
                            shown += 1
                except Exception:
                    pass
        except Exception as exc:
            log(f"[调试]   frame#{fi} 扫描失败: {exc}")
        if shown == 0:
            log(f"[调试]   frame#{fi} 无可见可点元素")
        try:
            suffix = "page" if frame is page.main_frame else f"frame{fi}"
            (root / f"debug-{suffix}-{ts}.html").write_text(frame.content(), encoding="utf-8")
        except Exception:
            pass
    log(f"[调试] 已导出各 frame HTML（时间戳 {ts}）")


def _visible_with_text(page: Page, label: str):
    items = page.locator("a, button, [role=button]").filter(has_text=label)
    for index in range(items.count()):
        try:
            if items.nth(index).is_visible():
                return items.nth(index)
        except Exception:
            continue
    return None
