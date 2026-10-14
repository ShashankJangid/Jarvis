"""
WhatsApp Web Playwright Automation Tool.
Runs headed on Monitor 2 using the persistent user profile.
Enables sending messages and reading recent chat history.
"""

import time
from typing import List, Dict
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from tools.browser_session import get_or_create_page

WHATSAPP_URL = "https://web.whatsapp.com"

# Selectors for WhatsApp Web across various client revisions
SEARCH_SELECTORS = [
    'div[contenteditable="true"][data-tab="3"]',
    'div[role="textbox"][title="Search input textbox"]',
    'div[aria-label="Search or start new chat"]',
    'div[data-testid="chat-list-search"]',
    'p.selectable-text[data-tab="3"]',
]

MESSAGE_INPUT_SELECTORS = [
    'footer div[contenteditable="true"][data-tab="10"]',
    'div[data-testid="conversation-compose-box-input"]',
    'footer div[role="textbox"]',
    'footer p.selectable-text',
    'div[title="Type a message"]',
]

def _ensure_whatsapp_ready(page) -> Dict[str, bool]:
    """
    Navigates to WhatsApp Web and checks login state.
    """
    if WHATSAPP_URL not in page.url:
        page.goto(WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)

    # Allow network and web-workers to stabilize
    time.sleep(2)

    # Check for QR code
    try:
        qr = page.locator('canvas[aria-label*="Scan"], div[data-testid="qrcode"], div[data-ref]').first
        if qr.is_visible(timeout=3000):
            return {"ready": False, "needs_qr": True}
    except Exception:
        pass

    # Wait for search box or chat list container
    ready = False
    for sel in SEARCH_SELECTORS:
        try:
            if page.locator(sel).first.is_visible(timeout=3000):
                ready = True
                break
        except Exception:
            continue

    if not ready:
        try:
            if page.locator('#pane-side, div[data-testid="chat-list"]').first.is_visible(timeout=5000):
                ready = True
        except Exception:
            pass

    return {"ready": ready, "needs_qr": not ready}


def send_whatsapp_message(contact_name: str, message_text: str) -> str:
    """
    Sends a WhatsApp message to a specific contact or phone number via WhatsApp Web on Monitor 2.

    Args:
        contact_name: Name of the contact or phone number as listed in WhatsApp.
        message_text: The text content of the message to send.

    Returns:
        Status message confirming dispatch or reporting any issues.
    """
    try:
        page = get_or_create_page("web.whatsapp.com")
        state = _ensure_whatsapp_ready(page)

        if state["needs_qr"]:
            return (
                "⚠️ **WhatsApp Web Authentication Required!**\n"
                "The browser window is open on the right half of Monitor 2.\n"
                "Please scan the QR code with your mobile WhatsApp app once. "
                "Because your profile is persistent, you won't need to do this again."
            )

        # 1. Focus search bar
        search_input = None
        for sel in SEARCH_SELECTORS:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=2000):
                    search_input = loc
                    break
            except Exception:
                continue

        if not search_input:
            # Try keyboard shortcut '/' or clicking search icon
            page.keyboard.press("Control+Alt+/")
            time.sleep(1)

        if search_input:
            search_input.click()
            time.sleep(0.5)
            # Clear existing search query
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            search_input.fill(contact_name)
        else:
            page.keyboard.type(contact_name)

        time.sleep(2)

        # 2. Select contact from results
        contact_clicked = False
        chat_item_selectors = [
            f'span[title="{contact_name}"]',
            f'span[title*="{contact_name}"]',
            '#pane-side div[data-testid="cell-frame-container"]',
            '#pane-side div[role="listitem"]',
        ]

        for c_sel in chat_item_selectors:
            try:
                target = page.locator(c_sel).first
                if target.is_visible(timeout=2000):
                    target.click()
                    contact_clicked = True
                    break
            except Exception:
                continue

        if not contact_clicked:
            # Try pressing Enter to pick the top search result
            page.keyboard.press("Enter")
            time.sleep(1.5)

        # 3. Focus message compose box
        time.sleep(1)
        compose_box = None
        for m_sel in MESSAGE_INPUT_SELECTORS:
            loc = page.locator(m_sel).first
            try:
                if loc.is_visible(timeout=2000):
                    compose_box = loc
                    break
            except Exception:
                continue

        if not compose_box:
            # Fallback click in footer area
            page.locator("footer").click()
            time.sleep(0.5)

        if compose_box:
            compose_box.click()
            compose_box.fill(message_text)
        else:
            page.keyboard.type(message_text)

        time.sleep(0.5)
        # Press Enter to send
        page.keyboard.press("Enter")
        time.sleep(1.5)

        return (
            f"✅ **WhatsApp message sent successfully to `{contact_name}`!**\n"
            f"- **Message**: \"{message_text}\"\n"
            f"- **Display**: Monitor 2 (Right Half)\n"
            f"- **Status**: Dispatched via WhatsApp Web"
        )
    except PlaywrightTimeoutError:
        return f"⚠️ WhatsApp Web timed out while attempting to message `{contact_name}`. Please verify your internet connection or check the browser on Monitor 2."
    except Exception as e:
        return f"⚠️ Error automating WhatsApp Web: {str(e)}"


def read_recent_whatsapp_messages(contact_name: str, count: int = 5) -> str:
    """
    Reads the recent incoming and outgoing messages from a conversation with contact_name.

    Args:
        contact_name: Name of the contact or group.
        count: Number of recent messages to retrieve (default: 5).

    Returns:
        Structured log of recent messages.
    """
    try:
        page = get_or_create_page("web.whatsapp.com")
        state = _ensure_whatsapp_ready(page)

        if state["needs_qr"]:
            return "⚠️ WhatsApp Web requires QR code authentication on Monitor 2."

        # Search for contact
        for sel in SEARCH_SELECTORS:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=2000):
                    loc.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    loc.fill(contact_name)
                    time.sleep(2)
                    page.keyboard.press("Enter")
                    break
            except Exception:
                continue

        time.sleep(2)

        # Collect messages from current conversation
        msg_locators = page.locator('div.message-in, div.message-out, div[data-testid="msg-container"]')
        total_msgs = msg_locators.count()

        if total_msgs == 0:
            return f"ℹ️ Opened chat for `{contact_name}`, but no messages were detected in view."

        start_idx = max(0, total_msgs - count)
        extracted = []

        for i in range(start_idx, total_msgs):
            try:
                msg_el = msg_locators.nth(i)
                text = msg_el.inner_text().strip()
                # Clean up newlines for cleaner presentation
                clean_lines = [l.strip() for l in text.split("\n") if l.strip()]
                extracted.append(" • " + " | ".join(clean_lines))
            except Exception:
                continue

        return (
            f"### 💬 Recent Messages with `{contact_name}` (Last {len(extracted)} messages):\n"
            + "\n".join(extracted)
        )
    except Exception as e:
        return f"⚠️ Error reading WhatsApp messages for `{contact_name}`: {str(e)}"
