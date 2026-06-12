from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Page

import page_logic


def launch_context(
    pw, profile_dir: Path, browser: str = "chromium", channel: str | None = None
) -> BrowserContext:
    browser_type = getattr(pw, browser)
    kwargs = dict(
        headless=False,
        viewport=None,  # 用真实窗口尺寸，配合 --start-maximized
        args=[
            "--start-maximized",
            # 反自动化检测：隐藏 navigator.webdriver、去掉“受自动化控制”横幅
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
    )
    if channel:
        # 用系统安装的 Chrome / Edge（更像普通用户浏览器，反检测更彻底）
        kwargs["channel"] = channel
    context = browser_type.launch_persistent_context(str(profile_dir), **kwargs)
    # 进一步抹掉 webdriver 痕迹：每个新页面注入脚本
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return context


def body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=2000)
    except Exception:
        return ""


def is_logged_in(page: Page, login_keywords: list[str]) -> bool:
    if "personcenter" not in page.url:
        return False
    return page_logic.contains_any(body_text(page), login_keywords)
