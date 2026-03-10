"""Email screen plugin — self-contained, uses ctx.defaults."""

from __future__ import annotations

from actions import click_continue, fill_detected_inputs
from plugins.context import PluginContext

_REACT_JS = (
    "(el, v) => {"
    "  try {"
    "    const s = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');"
    "    if (s && s.set) s.set.call(el, v);"
    "  } catch(e) {}"
    "  el.dispatchEvent(new Event('input', {bubbles:true}));"
    "  el.dispatchEvent(new Event('change', {bubbles:true}));"
    "}"
)

_REACT_CHECK_JS = (
    "(el) => {"
    "  try {"
    "    if (el.checked) return;"
    "    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked');"
    "    if (s && s.set) s.set.call(el, true);"
    "    el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));"
    "    el.dispatchEvent(new Event('change', {bubbles:true}));"
    "    el.dispatchEvent(new Event('input',  {bubbles:true}));"
    "  } catch(e) {}"
    "  try {"
    "    const lbl = el.closest('label');"
    "    if (lbl && !el.checked) lbl.click();"
    "  } catch(e) {}"
    "}"
)

_CONSENT_KEYWORDS = ("privacy", "terms", "consent", "agree", "policy", "accept", "read")


def _has_consent_error(page) -> bool:
    try:
        banner = page.locator(
            "text=accept our Privacy Policy, "
            "text=please accept, "
            "text=consent required, "
            "text=accept the Privacy"
        )
        return banner.count() > 0
    except Exception:
        return False


def _check_consent_boxes(page) -> None:
    try:
        custom = page.locator("[data-testid='checkbox']")
        total = min(custom.count(), 6)
        for idx in range(total):
            cb = custom.nth(idx)
            try:
                if not cb.is_visible(timeout=200):
                    continue
                text = (cb.inner_text() or "").lower()
                if text and not any(kw in text for kw in _CONSENT_KEYWORDS):
                    continue
                cb.click(force=True, timeout=500)
                page.wait_for_timeout(150)
            except Exception:
                continue
    except Exception:
        pass

    try:
        page.evaluate(
            "() => {"
            "  const kws = ['privacy', 'terms', 'consent', 'agree', 'policy'];"
            "  document.querySelectorAll('[class*=\"cursor-pointer\"]').forEach(el => {"
            "    if (el.closest('[data-testid=\"checkbox\"]')) return;"
            "    const r = el.getBoundingClientRect();"
            "    if (r.width < 10 || r.width > 80 || r.height < 10 || r.height > 80) return;"
            "    const ctx = (el.closest('[data-testid]') || el.parentElement || el);"
            "    const txt = (ctx.innerText || '').toLowerCase();"
            "    if (kws.some(kw => txt.includes(kw))) { el.click(); }"
            "  });"
            "}"
        )
        page.wait_for_timeout(200)
    except Exception:
        pass

    locator = page.locator("input[type='checkbox']")
    try:
        total = min(locator.count(), 12)
    except Exception:
        total = 0

    for idx in range(total):
        cb = locator.nth(idx)
        try:
            try:
                if cb.is_checked():
                    continue
            except Exception:
                pass

            try:
                label_text = cb.evaluate(
                    "el => {"
                    "const l = el.labels && el.labels[0] ? el.labels[0].innerText : '';"
                    "const p = el.closest('label') ? el.closest('label').innerText : '';"
                    "const n = el.parentElement ? el.parentElement.innerText : '';"
                    "const f = el.id"
                    "  ? ((document.querySelector('label[for=\"'+el.id+'\"]') || {}).innerText || '')"
                    "  : '';"
                    "return (l+' '+p+' '+n+' '+f).toLowerCase().slice(0,400);"
                    "}"
                ) or ""
            except Exception:
                label_text = ""

            if label_text and not any(kw in label_text for kw in _CONSENT_KEYWORDS):
                continue

            try:
                cb.check(force=True, timeout=500)
                if cb.is_checked():
                    continue
            except Exception:
                pass

            try:
                page.evaluate(_REACT_CHECK_JS, cb)
                page.wait_for_timeout(150)
                if cb.is_checked():
                    continue
            except Exception:
                pass

            try:
                cb_id = cb.get_attribute("id") or ""
                if cb_id:
                    lbl = page.locator(f"label[for='{cb_id}']")
                    if lbl.count() > 0:
                        lbl.first.click(force=True, timeout=500)
                        continue
            except Exception:
                pass

            try:
                parent_tag = cb.evaluate("el => el.parentElement ? el.parentElement.tagName.toLowerCase() : ''")
                if parent_tag == "label":
                    cb.evaluate("el => el.parentElement.click()")
            except Exception:
                pass

        except Exception:
            continue

    try:
        consent_labels = page.locator(
            "label:has-text('Privacy'), label:has-text('Terms'),"
            " label:has-text('consent'), label:has-text('Policy')"
        )
        lbl_total = min(consent_labels.count(), 5)
        for idx in range(lbl_total):
            lbl = consent_labels.nth(idx)
            try:
                if not lbl.is_visible(timeout=200):
                    continue
                already_checked = False
                inner_cb = lbl.locator("input[type='checkbox']")
                if inner_cb.count() > 0:
                    try:
                        already_checked = inner_cb.first.is_checked()
                    except Exception:
                        pass
                if not already_checked:
                    try:
                        for_id = lbl.get_attribute("for") or ""
                        if for_id:
                            linked = page.locator(f"#{for_id}")
                            if linked.count() > 0:
                                already_checked = linked.first.is_checked()
                    except Exception:
                        pass
                if already_checked:
                    continue
                lbl.click(force=True, timeout=500)
            except Exception:
                continue
    except Exception:
        pass


class EmailPlugin:
    name = "email"
    priority = 800

    def __init__(self, defaults: dict[str, str]) -> None:
        self._defaults = defaults

    def can_handle(self, page) -> bool:
        locator = page.locator(
            "input[type='email'], input[name*='email' i], input[placeholder*='email' i], "
            "label:has-text('email')"
        )
        try:
            total = min(locator.count(), 8)
        except Exception:
            return False

        for idx in range(total):
            item = locator.nth(idx)
            try:
                if item.is_visible(timeout=200):
                    return True
            except Exception:
                continue

        return False

    def execute(self, page) -> bool:
        email = self._defaults.get("email", "test@gmail.com")
        email_filled = False
        email_inputs = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i]")
        try:
            total = min(email_inputs.count(), 6)
        except Exception:
            total = 0

        for idx in range(total):
            field = email_inputs.nth(idx)
            try:
                if field.is_visible(timeout=200):
                    field.fill(email, timeout=1_000)
                    field.evaluate(_REACT_JS, email)
                    email_filled = True
                    break
            except Exception:
                continue

        if not email_filled:
            fill_detected_inputs(page, self._defaults)

        page.wait_for_timeout(500)
        _check_consent_boxes(page)
        page.wait_for_timeout(400)
        click_continue(page)

        page.wait_for_timeout(600)
        if _has_consent_error(page):
            print("  [email] consent error — retrying checkboxes")
            _check_consent_boxes(page)
            page.wait_for_timeout(500)
            click_continue(page)

        return True


def create_plugin(ctx: PluginContext) -> EmailPlugin:
    return EmailPlugin(defaults=ctx.defaults)
