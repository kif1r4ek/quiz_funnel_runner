"""Core runner for passing a single quiz funnel."""

from __future__ import annotations

import time
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config import (
    LLM_ENABLED,
    LLM_PRIMARY,
    MAX_STEPS,
    OLLAMA_BASE_URL,
    OLLAMA_ENABLED,
    OLLAMA_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    STEP_DELAY,
    STUCK_LIMIT,
    TIMEOUT,
)
from llm_fallback import LLMFallback
from popup_handler import close_popups
from utils import safe_body_text


def _normalized_snapshot(text: str) -> str:
    return " ".join(text.split())[:5000]


def _save_error_screenshot(page, screenshotter, funnel_key: str, step: int) -> None:
    try:
        funnel_dir = screenshotter.ensure_funnel_dir(funnel_key)
        path = funnel_dir / f"{step:02d}_error.png"
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        return


_llm: LLMFallback | None = None


def _get_llm() -> LLMFallback:
    """Return singleton LLMFallback (initialised once per process)."""
    global _llm
    if _llm is None:
        _llm = LLMFallback(
            openrouter_api_key=OPENROUTER_API_KEY or None,
            openrouter_model=OPENROUTER_MODEL,
            ollama_model=OLLAMA_MODEL,
            ollama_base_url=OLLAMA_BASE_URL,
            ollama_enabled=OLLAMA_ENABLED,
            enabled=LLM_ENABLED,
        )
    return _llm


def run_funnel(url: str, browser, device_config: dict, registry, screenshotter) -> dict:
    """Run one funnel end-to-end and return an execution summary dict."""

    funnel_key = screenshotter.funnel_key(url)
    steps: list[dict] = []
    stop_reason: str | None = None
    error: str | None = None

    context = None
    page = None
    started_at = time.time()

    try:
        context = browser.new_context(**device_config)
        context.set_default_timeout(TIMEOUT)
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=max(30_000, TIMEOUT * 3))

        initial_host = urlparse(url).netloc
        final_host = urlparse(page.url).netloc
        if initial_host and final_host and initial_host != final_host:
            print(f"  [runner] redirect: {initial_host} -> {final_host}")

        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(STEP_DELAY)

        for _ in range(10):
            if _normalized_snapshot(safe_body_text(page)):
                break
            page.wait_for_timeout(1_000)

        prev_snapshot = ""
        stuck_count = 0

        for step in range(1, MAX_STEPS + 1):
            close_popups(page)
            page.wait_for_timeout(300)

            strategy = registry.resolve(page)
            screen_type = strategy.name

            filename = screenshotter.save_step(page, funnel_key, step, screen_type)
            step_record = {
                "step": step,
                "type": screen_type,
                "file": filename,
                "url": page.url,
            }
            steps.append(step_record)

            print(f"  Step {step:02d}: [{screen_type:<8}] {page.url}")

            should_continue = True

            if LLM_PRIMARY and LLM_ENABLED:
                should_stop, llm_acted = _get_llm().execute_and_decide(page)
                if should_stop:
                    stop_reason = "paywall reached"
                    break
                if not llm_acted:
                    print(f"  [runner] LLM gave no action ({screen_type}), using DOM")
                    try:
                        should_continue = strategy.execute(page)
                    except Exception as exc:
                        error = f"strategy '{screen_type}' execute failed: {exc}"
                        stop_reason = f"error in {screen_type}: {exc}"
                        _save_error_screenshot(page, screenshotter, funnel_key, step)
                        break
            else:
                try:
                    should_continue = strategy.execute(page)
                except Exception as exc:
                    error = f"strategy '{screen_type}' execute failed: {exc}"
                    stop_reason = f"error in {screen_type}: {exc}"
                    _save_error_screenshot(page, screenshotter, funnel_key, step)
                    break

            if not should_continue:
                stop_reason = f"{screen_type} reached"
                break

            page.wait_for_timeout(STEP_DELAY)
            try:
                page.wait_for_load_state("networkidle", timeout=TIMEOUT // 2)
            except PlaywrightTimeoutError:
                pass

            snapshot = _normalized_snapshot(safe_body_text(page))
            if snapshot and snapshot == prev_snapshot:
                stuck_count += 1
            else:
                stuck_count = 0
            prev_snapshot = snapshot

            if not LLM_PRIMARY and LLM_ENABLED and stuck_count == STUCK_LIMIT - 1:
                print(f"  [runner] stuck {stuck_count}x — asking LLM")
                llm_acted = _get_llm().execute_on_page(page)
                if llm_acted:
                    stuck_count = 0
                    prev_snapshot = ""
                    page.wait_for_timeout(STEP_DELAY)
                    try:
                        page.wait_for_load_state("networkidle", timeout=TIMEOUT // 2)
                    except PlaywrightTimeoutError:
                        pass

            if stuck_count >= STUCK_LIMIT:
                stop_reason = "stuck: content unchanged for 3 consecutive steps"
                break
        else:
            stop_reason = "max steps reached"

    except PlaywrightTimeoutError as exc:
        error = f"timeout: {exc}"
        stop_reason = "timeout"
        if page is not None:
            _save_error_screenshot(page, screenshotter, funnel_key, len(steps) + 1)

    except Exception as exc:
        error = str(exc)
        stop_reason = f"error: {exc}"
        if page is not None:
            _save_error_screenshot(page, screenshotter, funnel_key, len(steps) + 1)

    finally:
        screenshotter.write_log(url, funnel_key, steps, stop_reason)
        if context is not None:
            context.close()

    _terminal_reasons = {"paywall reached", "checkout reached"}
    return {
        "url": url,
        "funnel_key": funnel_key,
        "steps": len(steps),
        "stop_reason": stop_reason or "completed",
        "paywall_reached": (stop_reason in _terminal_reasons),
        "error": error,
        "duration_sec": round(time.time() - started_at, 2),
    }
