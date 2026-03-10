"""Info screen plugin — self-contained."""

from __future__ import annotations

from actions import click_continue, find_continue_candidates
from plugins.context import PluginContext
from utils import visible_count


class InfoPlugin:
    name = "info"
    priority = 400

    def can_handle(self, page) -> bool:
        if visible_count(page.locator("input[type='email']")) > 0:
            return False

        form_like = page.locator(
            "input[type='text'], input[type='number'], input[type='tel'], "
            "input[inputmode='numeric'], input[inputmode='text'], input[inputmode='decimal'], "
            "input:not([type]), input[type='range'], textarea, select"
        )
        if visible_count(form_like, max_items=15) > 0:
            return False

        option_like = page.locator(
            "input[type='radio'], [role='radio'], [role='option'], [class*='option' i]"
        )
        if visible_count(option_like, max_items=15) >= 2:
            return False

        candidates = find_continue_candidates(page)
        if not candidates:
            return False
        for btn in candidates[:3]:
            try:
                if btn.is_enabled(timeout=300):
                    return True
            except Exception:
                return True
        return False

    def execute(self, page) -> bool:
        click_continue(page)
        return True


def create_plugin(ctx: PluginContext) -> InfoPlugin:
    _ = ctx
    return InfoPlugin()
