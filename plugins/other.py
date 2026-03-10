"""Fallback screen plugin — self-contained."""

from __future__ import annotations

from actions import click_continue
from plugins.context import PluginContext

_NAV_KEYWORDS = ("menu", "navigation", "nav", "toggle", "sidebar", "drawer", "hamburger")


def _is_nav_element(item) -> bool:
    try:
        tag = item.evaluate("el => el.tagName.toLowerCase()")
        if tag == "a":
            href = (item.get_attribute("href") or "").strip().rstrip("/")
            if href in ("", "#") or (href.startswith("http") and href.rstrip("/").count("/") <= 2):
                return True
    except Exception:
        pass
    try:
        label = (item.get_attribute("aria-label") or "").lower()
        title = (item.get_attribute("title") or "").lower()
        role = (item.get_attribute("role") or "").lower()
        combined = f"{label} {title} {role}"
        if any(kw in combined for kw in _NAV_KEYWORDS):
            return True
        box = item.bounding_box()
        if box and box["height"] < 50 and box["width"] < 50 and box["y"] < 100:
            return True
    except Exception:
        pass
    return False


class OtherPlugin:
    name = "other"
    priority = 0

    def can_handle(self, page) -> bool:
        return True

    def execute(self, page) -> bool:
        if click_continue(page):
            return True

        fallback = page.locator("button, a, input[type='submit'], input[type='button']")
        try:
            total = min(fallback.count(), 15)
        except Exception:
            return True

        for idx in range(total):
            item = fallback.nth(idx)
            try:
                if item.is_visible(timeout=200) and not _is_nav_element(item):
                    item.click(timeout=1_000)
                    page.wait_for_timeout(400)
                    break
            except Exception:
                continue

        return True


def create_plugin(ctx: PluginContext) -> OtherPlugin:
    _ = ctx
    return OtherPlugin()
