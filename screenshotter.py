"""Screenshot and logging utilities for funnel runs."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from config import RESULTS_DIR


class Screenshotter:
    def __init__(self, results_dir: str = RESULTS_DIR) -> None:
        self.results_dir = Path(results_dir)
        self.classified_dir = self.results_dir / "_classified"

    def ensure_base_dirs(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.classified_dir.mkdir(parents=True, exist_ok=True)

    def ensure_funnel_dir(self, funnel_key: str) -> Path:
        path = self.results_dir / funnel_key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def funnel_key(self, url: str) -> str:
        parsed = urlparse(url)
        domain = (parsed.netloc or "unknown").lower()
        path = parsed.path.strip("/").lower()

        raw = domain if not path else f"{domain}-{path.replace('/', '-')}"
        safe = re.sub(r"[^a-z0-9._-]+", "-", raw)
        safe = re.sub(r"-{2,}", "-", safe).strip("-")
        return safe or "funnel"

    def save_step(self, page, funnel_key: str, step: int, screen_type: str) -> str:
        funnel_dir = self.ensure_funnel_dir(funnel_key)

        filename = f"{step:02d}_{screen_type}.png"
        screenshot_path = funnel_dir / filename
        page.screenshot(path=str(screenshot_path), full_page=True)

        classified_type_dir = self.classified_dir / screen_type
        classified_type_dir.mkdir(parents=True, exist_ok=True)

        classified_name = f"{funnel_key}_{step:02d}_{screen_type}.png"
        shutil.copy2(screenshot_path, classified_type_dir / classified_name)

        return filename

    def write_log(
        self,
        funnel_url: str,
        funnel_key: str,
        steps: list[dict],
        stop_reason: str | None,
    ) -> None:
        funnel_dir = self.ensure_funnel_dir(funnel_key)
        log_path = funnel_dir / "log.txt"

        lines: list[str] = [
            f"Funnel: {funnel_url}",
            f"Total steps: {len(steps)}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 40,
            "",
        ]

        for entry in steps:
            lines.append(
                f"Step {entry['step']:02d}: [{entry['type']}] {entry['file']}"
            )
            lines.append(f"  URL: {entry['url']}")
            lines.append("")

        if stop_reason:
            lines.append(f"=> Stopped: {stop_reason}")

        log_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
