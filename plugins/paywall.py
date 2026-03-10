"""Paywall screen plugin — self-contained."""

from __future__ import annotations

import re

from plugins.context import PluginContext
from utils import safe_body_text, visible_count

_PAYWALL_CLASS_SELECTOR = (
    "[class*='price' i],"
    "[class*='pricing' i],"
    "[class*='subscription' i],"
    "[class*='paywall' i],"
    "[class*='billing' i],"
    "[class*='payment' i]"
)

_PAYWALL_STRONG: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:per month|per week|per year|billed|free trial|subscription)\b", re.IGNORECASE),
    re.compile(r"/(?:mo|month|week|wk|year|yr)\b", re.IGNORECASE),
    re.compile(r"\b(?:checkout|purchase|buy now|add to cart|payment method)\b", re.IGNORECASE),
)

_PAYWALL_WEAK: tuple[re.Pattern[str], ...] = (
    re.compile(r"[$€£]\s?\d{1,4}(?:[.,]\d{1,2})?"),
    re.compile(r"\b\d{1,4}(?:[.,]\d{1,2})?\s?(?:usd|eur|gbp)\b", re.IGNORECASE),
)


class PaywallPlugin:
    name = "paywall"
    priority = 900

    def can_handle(self, page) -> bool:
        class_hits = visible_count(page.locator(_PAYWALL_CLASS_SELECTOR), max_items=16)
        body_text = safe_body_text(page)

        strong_hits = sum(1 for p in _PAYWALL_STRONG if p.search(body_text))
        weak_hits = sum(1 for p in _PAYWALL_WEAK if p.search(body_text))
        currency_hits = len(re.findall(r"[$€£]", body_text))

        if class_hits > 0 and (strong_hits > 0 or weak_hits > 0):
            return True
        if strong_hits >= 2:
            return True
        if strong_hits >= 1 and currency_hits >= 2:
            return True
        return False

    def execute(self, page) -> bool:
        return False


def create_plugin(ctx: PluginContext) -> PaywallPlugin:
    _ = ctx
    return PaywallPlugin()
