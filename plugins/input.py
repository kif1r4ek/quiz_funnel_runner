"""Input screen plugin — self-contained, uses ctx.defaults."""

from __future__ import annotations

from actions import check_consent_boxes, click_continue, fill_detected_inputs
from plugins.context import PluginContext


class InputPlugin:
    name = "input"
    priority = 700

    def __init__(self, defaults: dict[str, str]) -> None:
        self._defaults = defaults

    def can_handle(self, page) -> bool:
        email_like = page.locator(
            "input[type='email'], input[name*='email' i], input[placeholder*='email' i]"
        )
        try:
            total_email = min(email_like.count(), 8)
        except Exception:
            total_email = 0
        for idx in range(total_email):
            item = email_like.nth(idx)
            try:
                if item.is_visible(timeout=200):
                    return False
            except Exception:
                continue

        locator = page.locator(
            "input[type='text'], input[type='number'], input[type='tel'], "
            "input[inputmode='numeric'], input[inputmode='text'], input[inputmode='decimal'], "
            "input:not([type]), input[type='range'], textarea, select"
        )

        try:
            total = min(locator.count(), 20)
        except Exception:
            total = 0

        for idx in range(total):
            item = locator.nth(idx)
            try:
                if item.is_visible(timeout=200):
                    return True
            except Exception:
                continue

        return False

    def execute(self, page) -> bool:
        filled = fill_detected_inputs(page, self._defaults)
        check_consent_boxes(page)
        if filled:
            for _ in range(3):
                page.wait_for_timeout(500)
                if click_continue(page):
                    return True
        else:
            click_continue(page)
        return True


def create_plugin(ctx: PluginContext) -> InputPlugin:
    return InputPlugin(defaults=ctx.defaults)
