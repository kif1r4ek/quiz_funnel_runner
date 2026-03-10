"""Question screen plugin — self-contained."""

from __future__ import annotations

import random

from actions import click_continue, find_continue_candidates
from plugins.context import PluginContext
from utils import visible_count

_OPTION_SELECTORS: tuple[str, ...] = (
    "[data-testid*='quiz-choice']",
    "[data-testid*='choice']",
    "input[type='radio']",
    "[role='radio']",
    "[role='option']",
    "[class*='option' i]",
    "[class*='answer' i]",
    "[class*='choice' i]",
    "[class*='variant' i]",
    "[class*='quiz-option' i]",
    "[class*='quiz-answer' i]",
    "button[class*='option' i]",
    "[class*='card' i]",
    "[class*='tile' i]",
    "button[class*='item' i]",
    "label:has(input[type='checkbox'])",
    "label:has(input[type='radio'])",
)

_OPTION_ROLES = {"button", "option", "radio", "menuitem", "treeitem", "tab"}

_JS_COUNT_LARGE_BUTTONS = """() => {
    let count = 0;
    const els = document.querySelectorAll('button, a, div, li, span');
    for (const el of els) {
        const r = el.getBoundingClientRect();
        if (r.width > 40 && r.height > 30 && r.top > 60 && r.top < 1200) {
            if (window.getComputedStyle(el).cursor === 'pointer') {
                count++;
                if (count >= 2) return count;
            }
        }
    }
    return count;
}"""

_JS_CLICK_NTH_LARGE = """(n) => {
    const vh = window.innerHeight;
    let count = 0;
    const els = document.querySelectorAll('button, a, div, li, span');
    for (const el of els) {
        const r = el.getBoundingClientRect();
        if (r.width > 30 && r.height > 30 && r.top > 60 && r.top < vh * 0.85) {
            if (window.getComputedStyle(el).cursor === 'pointer') {
                if (count === n) { el.click(); return true; }
                count++;
            }
        }
    }
    return false;
}"""

_JS_COLLECT_LARGE = """() => {
    const vh = window.innerHeight;
    let count = 0;
    const els = document.querySelectorAll('button, a, div, li, span');
    for (const el of els) {
        const r = el.getBoundingClientRect();
        if (r.width > 40 && r.height > 30 && r.top > 60 && r.top < vh * 0.85) {
            if (window.getComputedStyle(el).cursor === 'pointer') {
                count++;
                if (count >= 6) break;
            }
        }
    }
    return count;
}"""


def _walk_a11y(node: dict, roles: set[str], result: list, limit: int = 30) -> None:
    if len(result) >= limit:
        return
    if node.get("role") in roles and node.get("name", "").strip():
        result.append(node)
    for child in node.get("children", []):
        _walk_a11y(child, roles, result, limit)


def _count_accessible_options(page) -> int:
    try:
        snapshot = page.accessibility.snapshot()
        if not snapshot:
            return 0
        found: list = []
        _walk_a11y(snapshot, _OPTION_ROLES, found, limit=20)
        return len(found)
    except Exception:
        return 0


def _click_via_accessibility(page) -> bool:
    for role in ("option", "radio"):
        try:
            candidates = page.get_by_role(role)
            total = min(candidates.count(), 10)
            for idx in range(total):
                item = candidates.nth(idx)
                try:
                    box = item.bounding_box()
                    if box and box["y"] > 60:
                        item.click(timeout=1_000)
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    try:
        candidates = page.get_by_role("button")
        total = min(candidates.count(), 20)
        for idx in range(total):
            item = candidates.nth(idx)
            try:
                box = item.bounding_box()
                if box and box["y"] > 60 and box["height"] > 35:
                    item.click(timeout=1_000)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def _auto_check_terms(page) -> int:
    keywords = ("terms", "privacy", "agree", "consent", "policy", "condition")
    checked = 0

    locator = page.locator("input[type='checkbox']")
    try:
        total = min(locator.count(), 10)
    except Exception:
        total = 0

    for idx in range(total):
        cb = locator.nth(idx)
        try:
            if cb.is_checked():
                continue
            label_text: str = cb.evaluate(
                "el => {"
                "const l = el.labels && el.labels[0] ? el.labels[0].innerText : '';"
                "const p = el.closest('label') ? el.closest('label').innerText : '';"
                "const n = el.parentElement ? el.parentElement.innerText : '';"
                "const s = el.nextElementSibling ? el.nextElementSibling.innerText : '';"
                "return (l + ' ' + p + ' ' + n + ' ' + s).toLowerCase().slice(0, 400);"
                "}"
            ) or ""
            if any(kw in label_text for kw in keywords):
                try:
                    cb.check(force=True, timeout=1_000)
                    checked += 1
                    continue
                except Exception:
                    pass
                try:
                    label = page.locator(f"label[for='{cb.get_attribute('id')}']").first
                    if label.count():
                        label.click(timeout=500)
                        checked += 1
                        continue
                except Exception:
                    pass
        except Exception:
            continue

    if checked == 0:
        for kw in keywords:
            try:
                label = page.locator(f"label:has-text('{kw}')").first
                if label.count() and label.is_visible(timeout=200):
                    state = label.get_attribute("aria-checked") or ""
                    cls = label.get_attribute("class") or ""
                    if state == "true" or "checked" in cls.lower():
                        break
                    label.click(timeout=500)
                    page.wait_for_timeout(150)
                    checked += 1
                    break
            except Exception:
                continue

    if checked:
        page.wait_for_timeout(300)
    return checked


_JS_CLICK_RADIO_IN_LABEL = (
    "el => {"
    "  const root = el.tagName === 'LABEL' ? el : el.closest('label');"
    "  const inp = root && root.querySelector('input[type=\"radio\"],input[type=\"checkbox\"]');"
    "  if (!inp) return false;"
    "  if (inp.type === 'checkbox') {"
    "    root.click();"
    "    return true;"
    "  }"
    "  const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked');"
    "  if (desc && desc.set) desc.set.call(inp, true);"
    "  ['mousedown','mouseup','click'].forEach(t =>"
    "    inp.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true})));"
    "  inp.dispatchEvent(new Event('change', {bubbles:true}));"
    "  return true;"
    "}"
)


def _click_item(item) -> bool:
    try:
        tag = item.evaluate("el => el.tagName.toLowerCase()")
    except Exception:
        tag = ""

    if tag == "label":
        try:
            clicked = item.evaluate(_JS_CLICK_RADIO_IN_LABEL)
            if clicked:
                return True
        except Exception:
            pass

    try:
        item.click(timeout=1_000)
        return True
    except Exception:
        pass
    try:
        input_type = (item.get_attribute("type") or "").lower()
        if tag == "input" and input_type == "radio":
            clicked = item.evaluate(
                "el => {"
                "  const lbl = el.closest('label') || (el.id && document.querySelector('label[for=\"'+el.id+'\"]'));"
                "  if (lbl) { lbl.click(); return true; }"
                "  return false;"
                "}"
            )
            if clicked:
                return True
    except Exception:
        pass
    try:
        item.evaluate("el => el.click()")
        return True
    except Exception:
        pass
    try:
        child = item.locator("button, a, [role='button']").first
        if child.is_visible(timeout=200):
            child.click(timeout=500)
            return True
    except Exception:
        pass
    return False


def _click_random_visible(page, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        try:
            total = min(locator.count(), 15)
        except Exception:
            continue

        visible = []
        for idx in range(total):
            item = locator.nth(idx)
            try:
                if item.is_visible(timeout=300):
                    visible.append(item)
            except Exception:
                continue

        if visible:
            choice = random.choice(visible[:min(4, len(visible))])
            if _click_item(choice):
                return True

    return False


def _click_more_if_required(page, max_extra: int = 9) -> None:
    try:
        candidates = find_continue_candidates(page)
        if not candidates:
            return
        for extra_idx in range(1, max_extra + 1):
            try:
                if candidates[0].is_enabled(timeout=200):
                    return
            except Exception:
                return
            try:
                page.evaluate(_JS_CLICK_NTH_LARGE, extra_idx)
                page.wait_for_timeout(200)
            except Exception:
                break
    except Exception:
        pass


class QuestionPlugin:
    name = "question"
    priority = 600

    def can_handle(self, page) -> bool:
        radio_like = page.locator("input[type='radio'], [role='radio'], [role='option']")
        if visible_count(radio_like, max_items=10) >= 2:
            return True

        testid_like = page.locator("[data-testid*='quiz-choice'], [data-testid*='quiz-answer']")
        if visible_count(testid_like, max_items=10) >= 2:
            return True

        selector_labels = page.locator(
            "label:has(input[type='radio']), label:has(input[type='checkbox'])"
        )
        if visible_count(selector_labels, max_items=10) >= 2:
            return True

        option_like = page.locator(", ".join(_OPTION_SELECTORS[5:12]))
        if visible_count(option_like, max_items=18) >= 2:
            return True

        card_like = page.locator("[class*='card' i], [class*='tile' i]")
        if visible_count(card_like, max_items=12) >= 3:
            return True

        try:
            if page.evaluate(_JS_COUNT_LARGE_BUTTONS) >= 2:
                return True
        except Exception:
            pass

        if _count_accessible_options(page) >= 2:
            return True

        return False

    def execute(self, page) -> bool:
        _auto_check_terms(page)

        clicked = _click_random_visible(page, _OPTION_SELECTORS)

        if not clicked:
            try:
                total = page.evaluate(_JS_COLLECT_LARGE)
                if total > 0:
                    n = random.randint(0, min(total - 1, 3))
                    clicked = bool(page.evaluate(_JS_CLICK_NTH_LARGE, n))
            except Exception:
                pass

        if not clicked:
            clicked = _click_via_accessibility(page)

        if clicked:
            url_before = page.url
            try:
                page.wait_for_load_state("networkidle", timeout=3_000)
            except Exception:
                page.wait_for_timeout(700)
            page.wait_for_timeout(400)

            if page.url == url_before:
                _click_more_if_required(page)
                click_continue(page)
        else:
            click_continue(page)
        return True


def create_plugin(ctx: PluginContext) -> QuestionPlugin:
    _ = ctx
    return QuestionPlugin()
