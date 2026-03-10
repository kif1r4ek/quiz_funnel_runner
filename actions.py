"""Actions used by strategies: continue-button detection, input filling, range/select helpers."""

from __future__ import annotations


CONTINUE_SELECTORS: tuple[str, ...] = (
    "[data-testid='quiz-submit-btn']:not([disabled])",
    "[data-testid='quiz-validate-btn']:not([disabled])",
    "button:has-text('Continue')",
    "button:has-text('Next')",
    "button:has-text('Start')",
    "button:has-text('Begin')",
    "button:has-text('Get started')",
    "button:has-text('Got it')",
    "button:has-text('Submit')",
    "button:has-text('Proceed')",
    "button:has-text('Confirm')",
    'button:has-text("Let\'s Do It")',
    "button:has-text('Let\\'s do it')",
    'button:has-text("Let\'s go")',
    "button:has-text('Get my plan')",
    "button:has-text('Get my results')",
    "button:has-text('Show my results')",
    'button:has-text("I\'m ready")',
    "button:has-text('See my plan')",
    "button:has-text('View my plan')",
    'button:has-text("YES, I\'M IN")',
    "button:has-text('Take the quiz')",
    "button:has-text('Find out')",
    "button:has-text('Discover')",
    "button:has-text('Далее')",
    "button:has-text('Продолжить')",
    "button:has-text('Поехали')",
    "button:has-text('Я готов')",
    "a:has-text('Continue')",
    "a:has-text('Next')",
    'a:has-text("Let\'s Do It")',
    "a:has-text('Let\\'s do it')",
    'a:has-text("YES, I\'M IN")',
    "a:has-text('Далее')",
    "a:has-text('Продолжить')",
    "[class*='continue' i]",
    "[class*='btn-next' i]",
    "button[type='submit']",
    "input[type='submit']",
)

_SKIP_INPUT_TYPES = {"hidden", "submit", "button", "checkbox", "radio", "file"}

_FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "email": ("email", "e-mail", "mail"),
    "name": ("name", "first name", "your name", "full name"),
    "phone": ("phone", "mobile", "tel", "telephone", "cell", "телефон"),
    "height": ("height", "cm", "ft", "inch", "рост"),
    "weight": ("weight", "kg", "lbs", "вес"),
    "age": ("age", "years", "лет", "возраст"),
    "dob": ("dateofbirth", "date of birth", "birth", "dob", "birthday"),
}


def _safe_attr(locator, name: str) -> str:
    try:
        value = locator.get_attribute(name)
    except Exception:
        value = None
    return (value or "").strip().lower()


def _safe_eval(locator, script: str) -> str:
    try:
        value = locator.evaluate(script)
    except Exception:
        value = ""
    return str(value or "").strip().lower()


def _infer_field_key(locator) -> str | None:
    input_type = _safe_attr(locator, "type")
    if input_type == "email":
        return "email"

    parts = [
        _safe_attr(locator, "name"),
        _safe_attr(locator, "id"),
        _safe_attr(locator, "placeholder"),
        _safe_attr(locator, "aria-label"),
        _safe_attr(locator, "inputmode"),
        _safe_eval(
            locator,
            "el => {"
            "const own = (el.labels && el.labels[0] ? el.labels[0].innerText : '');"
            "const parentLabel = el.closest('label') ? el.closest('label').innerText : '';"
            "const parent = el.parentElement ? el.parentElement.innerText : '';"
            "const grand = (el.parentElement && el.parentElement.parentElement"
            "  ? el.parentElement.parentElement.innerText : '');"
            "return (own + ' ' + parentLabel + ' ' + parent + ' ' + grand).slice(0, 300);"
            "}",
        ),
    ]

    haystack = " ".join(part for part in parts if part)
    for key, keywords in _FIELD_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return key

    if input_type in {"number", "tel"} or "numeric" in haystack:
        return "age"

    return None


def _iter_visible(locator, max_items: int = 12):
    try:
        total = min(locator.count(), max_items)
    except Exception:
        total = 0

    for idx in range(total):
        item = locator.nth(idx)
        try:
            if item.is_visible(timeout=200):
                yield item
        except Exception:
            continue


_CONSENT_KEYWORDS = ("terms", "privacy", "agree", "consent", "policy", "condition")


def check_consent_boxes(page) -> int:
    """Check any unchecked consent/terms/privacy checkboxes on the page."""
    checked = 0
    locator = page.locator("input[type='checkbox']")
    try:
        total = min(locator.count(), 10)
    except Exception:
        return 0
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
                "return (l + ' ' + p + ' ' + n).toLowerCase().slice(0, 400);"
                "}"
            ) or ""
            if any(kw in label_text for kw in _CONSENT_KEYWORDS):
                cb.check(force=True, timeout=1_000)
                checked += 1
        except Exception:
            continue
    return checked


def find_continue_candidates(page) -> list:
    """Return visible continue-button candidates, deduplicated by bounding box."""
    seen: set[tuple] = set()
    candidates = []
    for selector in CONTINUE_SELECTORS:
        locator = page.locator(selector)
        for item in _iter_visible(locator, max_items=8):
            try:
                box = item.bounding_box()
                key = (
                    round(box["x"]) if box else None,
                    round(box["y"]) if box else None,
                )
            except Exception:
                key = None
            if key not in seen:
                seen.add(key)
                candidates.append(item)
    return candidates


def click_continue(page) -> bool:
    for candidate in find_continue_candidates(page):
        try:
            candidate.click(timeout=1_000)
            page.wait_for_timeout(300)
            return True
        except Exception:
            continue
    return False


def set_range_value(page, locator, value: str) -> bool:
    try:
        locator.evaluate(
            """
            (el, val) => {
                const normalized = String(val);
                el.value = normalized;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """,
            value,
        )
        page.wait_for_timeout(150)
        return True
    except Exception:
        return False


def _set_select_value(locator, value: str) -> bool:
    try:
        changed = locator.evaluate(
            """
            (el, preferred) => {
                const options = Array.from(el.options || []);
                if (!options.length) {
                    return false;
                }

                const byValue = options.find((o) => o.value === preferred);
                const byText = options.find((o) =>
                    o.textContent && o.textContent.toLowerCase().includes(String(preferred).toLowerCase())
                );
                const fallback = options.find((o) => o.value && !o.disabled) || options[0];
                const target = byValue || byText || fallback;
                if (!target) {
                    return false;
                }

                el.value = target.value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
            """,
            value,
        )
        return bool(changed)
    except Exception:
        return False


def fill_detected_inputs(page, defaults: dict[str, str]) -> int:
    """Fill all detected input fields using inferred field keys and default values."""
    filled_count = 0
    locator = page.locator("input, textarea, select")

    for field in _iter_visible(locator, max_items=30):
        tag_name = _safe_eval(field, "el => el.tagName")
        input_type = _safe_attr(field, "type")

        if tag_name == "select":
            key = _infer_field_key(field) or "age"
            value = defaults.get(key, defaults.get("age", "30"))
            if _set_select_value(field, value):
                filled_count += 1
            continue

        if input_type in _SKIP_INPUT_TYPES:
            continue

        if input_type == "range":
            key = _infer_field_key(field) or "height"
            value = defaults.get(key, defaults.get("height", "170"))
            if set_range_value(page, field, value):
                filled_count += 1
            continue

        key = _infer_field_key(field)
        if key is None:
            key = "name" if input_type in {"text", "search", ""} else "age"

        value = defaults.get(key, defaults.get("name", "John"))

        # DOB inputs use input masks — type digits sequentially so the mask formats them
        if key == "dob":
            try:
                field.click(timeout=500)
                field.fill("", timeout=500)
                digits = "".join(c for c in value if c.isdigit())
                field.press_sequentially(digits, delay=80)
                filled_count += 1
            except Exception:
                pass
            continue

        try:
            field.fill(value, timeout=1_000)
            field.evaluate(
                "(el, v) => {"
                "  try {"
                "    const setter = Object.getOwnPropertyDescriptor("
                "      Object.getPrototypeOf(el), 'value'"
                "    );"
                "    if (setter && setter.set) setter.set.call(el, v);"
                "  } catch(e) {}"
                "  el.dispatchEvent(new Event('input', {bubbles: true}));"
                "  el.dispatchEvent(new Event('change', {bubbles: true}));"
                "}",
                value,
            )
            filled_count += 1
        except Exception:
            continue

    return filled_count
