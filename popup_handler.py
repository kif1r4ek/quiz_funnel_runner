"""Popup and cookie banner handling."""

from __future__ import annotations

from config import POPUP_TIMEOUT

POPUP_SELECTORS: tuple[str, ...] = (
    "button:has-text('Accept')",
    "button:has-text('Accept all')",
    "button:has-text('Accept All')",
    "button:has-text('Accept cookies')",
    "button:has-text('Accept & Continue')",
    "button:has-text('I Accept')",
    "button:has-text('Agree')",
    "button:has-text('I agree')",
    "button:has-text('Allow')",
    "button:has-text('Allow all')",
    "button:has-text('Allow All')",
    "button:has-text('OK')",
    "button:has-text('Okay')",
    "button:has-text('Dismiss')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Zustimmen')",
    "button:has-text('Einverstanden')",
    "button:has-text('Accepter')",
    "button:has-text('Tout accepter')",
    "button:has-text('Закрыть')",
    "button:has-text('Принять')",
    "button:has-text('Согласен')",
    "#truste-consent-button",
    "[id*='truste' i] button",
    "[class*='truste' i] button",
    "#onetrust-accept-btn-handler",
    "[id*='onetrust' i] [class*='accept' i]",
    "#CybotCookiebotDialogBodyButtonAccept",
    "[aria-label='Close']",
    "[aria-label='close']",
    "[aria-label='Закрыть']",
    "[class*='cookie' i] button",
    "[class*='consent' i] button",
    "[class*='gdpr' i] button",
    "[class*='cookie-close' i]",
    "[class*='banner-close' i]",
    "[class*='modal-close' i]",
    "[class*='overlay-close' i]",
    "[class*='popup-close' i]",
)


def _try_selectors_in_frame(frame, page, selectors) -> int:
    closed = 0
    for _ in range(3):
        closed_this_pass = 0
        for selector in selectors:
            try:
                locator = frame.locator(selector)
                total = min(locator.count(), 8)
            except Exception:
                total = 0
            for idx in range(total):
                element = locator.nth(idx)
                try:
                    if element.is_visible(timeout=200):
                        element.click(timeout=POPUP_TIMEOUT)
                        page.wait_for_timeout(250)
                        closed += 1
                        closed_this_pass += 1
                except Exception:
                    continue
        if closed_this_pass == 0:
            break
    return closed


def close_popups(page) -> int:
    """Try to close all known popups in main frame and sub-frames."""
    closed_total = 0
    targets = page.frames
    for frame in targets:
        closed_total += _try_selectors_in_frame(frame, page, POPUP_SELECTORS)
    return closed_total
