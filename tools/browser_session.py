"""
Browser Session Manager for Jarvis.
Maintains a shared, persistent Chromium instance pinned to Monitor 2
to allow WhatsApp Web, Colab, Kaggle, and Web forms to run in headed mode
without profile lock collisions.
"""

import time
import threading
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page
import config

_lock = threading.Lock()
_playwright_instance: Optional[Playwright] = None
_browser_context: Optional[BrowserContext] = None

def get_browser_context() -> BrowserContext:
    """
    Returns the persistent Chromium browser context pinned to Monitor 2.
    Launches it if not already active.
    """
    global _playwright_instance, _browser_context

    with _lock:
        if _browser_context is not None:
            try:
                # Check if context is still alive
                if len(_browser_context.pages) >= 0:
                    return _browser_context
            except Exception:
                _browser_context = None

        if _playwright_instance is None:
            _playwright_instance = sync_playwright().start()

        # Headed launch pinned to right half of Monitor 2
        launch_args = [
            f"--window-position={config.BROWSER_WINDOW_X},{config.BROWSER_WINDOW_Y}",
            f"--window-size={config.BROWSER_WINDOW_WIDTH},{config.BROWSER_WINDOW_HEIGHT}",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
        ]

        try:
            _browser_context = _playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(config.CHROME_PROFILE_DIR),
                headless=False,
                viewport={"width": config.BROWSER_WINDOW_WIDTH, "height": config.BROWSER_WINDOW_HEIGHT},
                args=launch_args,
                ignore_default_args=["--enable-automation"],
            )
        except Exception as e:
            # If persistent lock fails, retry with clean handle or propagate
            raise RuntimeError(
                f"Failed to launch persistent Chromium on Monitor 2: {e}. "
                f"Ensure no other standalone Chrome instance is locking {config.CHROME_PROFILE_DIR}"
            ) from e

        return _browser_context


def get_or_create_page(url_substring: str = "") -> Page:
    """
    Finds an existing page whose URL contains `url_substring`,
    or creates/returns a page.
    """
    context = get_browser_context()
    if url_substring:
        for page in context.pages:
            try:
                if url_substring in page.url:
                    page.bring_to_front()
                    return page
            except Exception:
                continue

    if context.pages:
        # If the first page is blank about:blank, use it
        first_page = context.pages[0]
        try:
            if first_page.url in ("about:blank", ""):
                first_page.bring_to_front()
                return first_page
        except Exception:
            pass

    new_page = context.new_page()
    new_page.bring_to_front()
    return new_page


def close_browser():
    """Gracefully closes the browser context and stops Playwright."""
    global _playwright_instance, _browser_context
    with _lock:
        if _browser_context:
            try:
                _browser_context.close()
            except Exception:
                pass
            _browser_context = None
        if _playwright_instance:
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = None
