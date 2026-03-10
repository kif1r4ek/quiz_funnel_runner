"""Shared DOM helpers used across plugins."""

from __future__ import annotations


def visible_count(locator, max_items: int = 15) -> int:
    """Count how many elements in *locator* are currently visible."""
    try:
        total = min(locator.count(), max_items)
    except Exception:
        return 0

    count = 0
    for idx in range(total):
        item = locator.nth(idx)
        try:
            if item.is_visible(timeout=200):
                count += 1
        except Exception:
            continue
    return count


def safe_body_text(page) -> str:
    """Return the visible text of <body>, or '' on any error."""
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""
