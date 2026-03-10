"""Checkout screen plugin — self-contained."""

from __future__ import annotations

from plugins.context import PluginContext


class CheckoutPlugin:
    name = "checkout"
    priority = 1000

    def can_handle(self, page) -> bool:
        selectors = (
            "input[autocomplete='cc-number'], "
            "input[name*='card' i], input[placeholder*='card number' i], "
            "[class*='checkout' i], [class*='payment-form' i]"
        )
        locator = page.locator(selectors)

        try:
            total = min(locator.count(), 10)
        except Exception:
            total = 0

        for idx in range(total):
            item = locator.nth(idx)
            try:
                if item.is_visible(timeout=200):
                    return True
            except Exception:
                continue

        try:
            body_text = (page.inner_text("body") or "").lower()
        except Exception:
            body_text = ""

        checkout_markers = ("pay now", "complete order", "card number", "billing address")
        return any(marker in body_text for marker in checkout_markers)

    def execute(self, page) -> bool:
        return False


def create_plugin(ctx: PluginContext) -> CheckoutPlugin:
    _ = ctx
    return CheckoutPlugin()
