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
