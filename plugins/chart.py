"""Chart screen plugin — self-contained."""

from __future__ import annotations

from actions import click_continue, find_continue_candidates
from plugins.context import PluginContext
from utils import visible_count


def _has_large_svg(page) -> bool:
    """Return True if the page has a large SVG element (actual data chart, not emoji icons)."""
    try:
        return page.evaluate(
            "() => Array.from(document.querySelectorAll('svg')).some("
            "  svg => { const r = svg.getBoundingClientRect();"
            "    return r.width > 150 && r.height > 100; })"
        )
    except Exception:
        return False


class ChartPlugin:
    name = "chart"
    priority = 500

    def can_handle(self, page) -> bool:
        has_continue = len(find_continue_candidates(page)) > 0

        chart_locator = page.locator(
            "canvas, [class*='chart' i], [class*='graph' i], [class*='progress-chart' i]"
        )
        if visible_count(chart_locator) > 0 and has_continue:
            return True

        if _has_large_svg(page) and has_continue:
            return True

        return False

    def execute(self, page) -> bool:
        if not click_continue(page):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(400)
            except Exception:
                pass
            click_continue(page)
        return True


def create_plugin(ctx: PluginContext) -> ChartPlugin:
    _ = ctx
    return ChartPlugin()
