"""LLM-based fallback for quiz funnel traversal.

Tries Ollama (local, free, unlimited) first, then OpenRouter (cloud, free tier).
Used as a last resort when heuristic strategies get stuck.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request

_SYSTEM_PROMPT = (
    "You are a quiz funnel automation assistant. "
    "Analyze the screenshot and return ONLY a valid JSON object — no markdown, no explanation.\n\n"
    "JSON schema:\n"
    '{\n'
    '  "screen_type": "question" | "input" | "info" | "paywall" | "other",\n'
    '  "action": "click" | "fill" | "scroll" | "none",\n'
    '  "target_text": "exact visible text of the element to interact with",\n'
    '  "fill_value": "value to type (null if action is not fill)",\n'
    '  "input_label": "label/placeholder text of the input field (for fill actions)",\n'
    '  "reasoning": "one sentence"\n'
    '}\n\n'
    "Rules (in priority order):\n"
    "1. PAYWALL: if you see pricing plans with /month /week /year, subscription, or payment form → screen_type=paywall, action=none\n"
    "2. INPUT FIELD: if there is a visible text/number input box (Name, Email, Phone, Height, Weight, Age, etc.) "
    "→ screen_type=input, action=fill, input_label=placeholder text, fill_value=realistic value. "
    "Examples: Name→'John', Email→'test@gmail.com', Phone→'+7 323 838 98-12', Height→'170', Weight→'65', Age→'30'\n"
    "3. QUESTION with image answers: if you see cards/images with labels (e.g. 'Far from my feet') "
    "→ screen_type=question, action=click, target_text=label text of the FIRST option\n"
    "4. QUESTION with text answers: click the FIRST answer option text\n"
    "5. INFO/CHART screen: if there is a Continue/Next/Get my plan button → action=click, target_text=button text\n"
    "6. CONSENT BANNER / COOKIE POPUP: action=click, target_text=accept button text\n"
    "7. If unsure: pick the most prominent clickable element in the content area\n"
    "\nIMPORTANT: If you see a checkbox labeled 'Terms', 'Privacy', 'By continuing' that is unchecked, "
    "set action=check, target_text=the checkbox label text. The checkbox must be checked before answering.\n"
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _parse_json(text: str) -> dict | None:
    """Extract and parse the first JSON object found in text."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return None


class OllamaVision:
    """Calls a local Ollama instance with a vision model."""

    def __init__(
        self,
        model: str = "llama3.2-vision",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                req = urllib.request.Request(f"{self.base_url}/api/tags")
                with urllib.request.urlopen(req, timeout=2):
                    self._available = True
            except Exception:
                self._available = False
        return self._available

    def analyze(self, screenshot_bytes: bytes) -> dict | None:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _SYSTEM_PROMPT + "\n\nAnalyze this quiz funnel screenshot:",
                    "images": [_b64(screenshot_bytes)],
                }
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode(errors="replace")[:300]
            except Exception:
                pass
            print(f"  [llm/ollama] HTTP {exc.code}: {body}")
            return None
        except TimeoutError:
            print("  [llm/ollama] timeout >120s — disabling Ollama for this session")
            self._available = False
            return None
        except Exception as exc:
            print(f"  [llm/ollama] error: {type(exc).__name__}: {exc}")
            return None

        if result.get("error"):
            print(f"  [llm/ollama] error: {result['error']}")
            return None
        text = (result.get("message") or {}).get("content", "")
        parsed = _parse_json(text)
        if not parsed:
            print(f"  [llm/ollama] JSON parse failed, raw: {text[:200]!r}")
        return parsed


class OpenRouterVision:
    """Calls OpenRouter API (OpenAI-compatible, free tier).

    Working free vision models (verified March 2026):
      - mistralai/mistral-small-3.1-24b-instruct:free  (recommended)
      - google/gemma-3-12b-it:free
      - nvidia/nemotron-nano-12b-v2-vl:free
    """

    _API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model: str = "mistralai/mistral-small-3.1-24b-instruct:free",
    ) -> None:
        self.api_key = api_key
        self.model = model

    def analyze(self, screenshot_bytes: bytes) -> dict | None:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{_b64(screenshot_bytes)}"
                            },
                        },
                        {"type": "text", "text": "Return JSON only:"},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 256,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/quiz-funnel-runner",
            },
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                text = result["choices"][0]["message"]["content"]
                parsed = _parse_json(text)
                if not parsed:
                    print(f"  [llm/openrouter] JSON parse failed, raw: {text[:200]!r}")
                return parsed
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode(errors="replace")[:300]
                except Exception:
                    pass
                print(f"  [llm/openrouter] HTTP {exc.code}: {body}")
                if exc.code == 429 and attempt == 0:
                    print("  [llm/openrouter] rate limited — retrying in 5s")
                    time.sleep(5)
                    continue
                return None
            except Exception as exc:
                print(f"  [llm/openrouter] request failed: {exc}")
                return None
        return None


class LLMFallback:
    """Tries backends in order: Ollama (local) → OpenRouter (cloud).

    Usage::

        fallback = LLMFallback(openrouter_api_key="sk-or-...")
        acted = fallback.execute_on_page(page)
    """

    def __init__(
        self,
        openrouter_api_key: str | None = None,
        openrouter_model: str = "mistralai/mistral-small-3.1-24b-instruct:free",
        ollama_model: str = "llava:7b",
        ollama_base_url: str = "http://localhost:11434",
        ollama_enabled: bool = False,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self._ollama = OllamaVision(model=ollama_model, base_url=ollama_base_url) if ollama_enabled else None
        self._openrouter = (
            OpenRouterVision(api_key=openrouter_api_key, model=openrouter_model)
            if openrouter_api_key
            else None
        )

        if self.enabled:
            parts = []
            if self._ollama:
                parts.append(f"Ollama({ollama_model} @ {ollama_base_url})")
            if self._openrouter:
                parts.append(f"OpenRouter({openrouter_model})")
            print(f"  [llm] backends: {' → '.join(parts) if parts else 'none configured'}")
        else:
            print("  [llm] disabled")

    _STOP_SCREENS = {"paywall", "checkout"}

    def _active_backends(self):
        if self._ollama and self._ollama.is_available():
            yield "ollama", self._ollama
        if self._openrouter:
            yield "openrouter", self._openrouter

    def execute_and_decide(self, page) -> tuple[bool, bool]:
        """Take screenshot → try each backend until one successfully acts.

        Returns (should_stop, acted):
          - should_stop=True  → funnel end detected (paywall/checkout), stop the loop
          - acted=True        → action was performed, continue normally
          - (False, False)    → all backends failed or gave no action → DOM fallback
        """
        if not self.enabled:
            return False, False

        try:
            screenshot_bytes: bytes = page.screenshot(full_page=False)
        except Exception:
            return False, False

        for name, backend in self._active_backends():
            print(f"  [llm/{name}] analyzing screenshot...")
            result = backend.analyze(screenshot_bytes)
            if not result:
                print(f"  [llm/{name}] no result — trying next backend")
                continue
            print(f"  [llm/{name}] response: {result}")
            screen_type = result.get("screen_type", "other")
            if screen_type in self._STOP_SCREENS:
                print(f"  [llm] detected {screen_type} → stopping funnel")
                return True, False
            acted = self._execute_result(page, result)
            if acted:
                return False, True
            action = result.get("action", "none")
            if action == "none":
                print(f"  [llm/{name}] gave action=none — trying next backend")
            else:
                print(f"  [llm/{name}] execution failed — trying next backend")

        print("  [llm] all backends gave no actionable result — falling back to DOM")
        return False, False

    def execute_on_page(self, page) -> bool:
        """Convenience wrapper: returns True if an action was performed."""
        _, acted = self.execute_and_decide(page)
        return acted

    def _execute_result(self, page, result: dict) -> bool:
        """Execute the action described in an LLM result dict."""
        action = result.get("action", "none")
        target_text = (result.get("target_text") or "").strip()
        fill_value = result.get("fill_value")
        input_label = (result.get("input_label") or "").strip()
        screen_type = result.get("screen_type", "?")
        reasoning = result.get("reasoning", "")

        print(
            f"  [llm] screen={screen_type} action={action}"
            + (f" target={target_text!r}" if target_text else "")
            + (f" | {reasoning}" if reasoning else "")
        )

        if action == "none":
            return False

        if action == "check":
            return self._try_check(page, target_text)

        if action == "click" and target_text:
            self._auto_check_consent(page)
            return self._try_click(page, target_text)

        if action == "fill":
            label = input_label or target_text
            filled = self._try_fill(page, label, fill_value)
            if filled:
                page.wait_for_timeout(300)
                self._try_click_continue(page)
            return filled

        if action == "scroll":
            try:
                page.mouse.wheel(0, 500)
                return True
            except Exception:
                return False

        return False

    @staticmethod
    def _auto_check_consent(page) -> None:
        try:
            for cb in page.locator("input[type='checkbox']").all():
                try:
                    if not cb.is_checked(timeout=300):
                        cb.check(force=True, timeout=500)
                except Exception:
                    pass
        except Exception:
            pass

    @staticmethod
    def _try_check(page, target_text: str) -> bool:
        """Check a checkbox by its label text."""
        try:
            cb = page.get_by_label(target_text, exact=False).first
            if cb.is_visible(timeout=1_000):
                cb.check(force=True, timeout=1_000)
                return True
        except Exception:
            pass
        try:
            cb = page.locator("input[type='checkbox']").first
            if not cb.is_checked():
                cb.check(force=True, timeout=500)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _try_click_continue(page) -> bool:
        """Click a Continue / Next / Submit button."""
        selectors = [
            "button:has-text('Next')", "button:has-text('Continue')",
            "button:has-text('Submit')", "button:has-text('Get')",
            "button:has-text('Start')", "button[type='submit']",
            "a:has-text('Next')", "a:has-text('Continue')",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=400) and el.is_enabled(timeout=400):
                    el.click(timeout=1_500)
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _try_click(page, target_text: str) -> bool:
        try:
            el = page.get_by_text(target_text, exact=False).first
            if el.is_visible(timeout=1_000):
                el.click(timeout=2_000)
                return True
        except Exception:
            pass

        try:
            el = page.locator(f"text={target_text}").first
            if el.is_visible(timeout=500):
                el.click(timeout=2_000)
                return True
        except Exception:
            pass

        words = target_text.split()[:3]
        for word in words:
            if len(word) < 3:
                continue
            try:
                el = page.locator(
                    f"button:has-text('{word}'), a:has-text('{word}'),"
                    f" div:has-text('{word}'), li:has-text('{word}')"
                ).first
                if el.is_visible(timeout=500):
                    el.click(timeout=2_000)
                    return True
            except Exception:
                continue

        try:
            clicked = page.evaluate(
                "(text) => {"
                "  const els = document.querySelectorAll('*');"
                "  for (const el of els) {"
                "    if (el.children.length > 3) continue;"
                "    if ((el.innerText || '').trim().startsWith(text.slice(0,20))) {"
                "      const s = window.getComputedStyle(el);"
                "      if (s.cursor === 'pointer') { el.click(); return true; }"
                "    }"
                "  }"
                "  return false;"
                "}",
                target_text,
            )
            if clicked:
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def _try_fill(page, label: str, value) -> bool:
        if value is None:
            return False
        value_str = str(value)

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

        if label:
            for locator in [
                page.get_by_label(label, exact=False),
                page.get_by_placeholder(label, exact=False),
            ]:
                try:
                    inp = locator.first
                    if inp.is_visible(timeout=500):
                        inp.fill(value_str, timeout=1_000)
                        inp.evaluate(_REACT_JS, value_str)
                        return True
                except Exception:
                    pass

        try:
            inp = page.locator(
                "input[type='text']:visible, input[type='number']:visible,"
                " input[type='tel']:visible, textarea:visible"
            ).first
            inp.fill(value_str, timeout=1_000)
            inp.evaluate(_REACT_JS, value_str)
            return True
        except Exception:
            return False
