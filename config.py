"""Project configuration for Quiz Funnel Runner."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

FUNNELS: list[str] = [
    "https://coursiv.io/dynamic?prc_id=1069",
    "https://coursiv.io/dynamic",
    "https://quiz.fitme.expert/intro-111",
    "https://madmuscles.com/funnel/default-uni-soft-new/step-one",
    "https://dance-bit.com/welcomeBellyRef",
]

DEFAULTS: dict[str, str] = {
    "name": "John",
    "height": "170",
    "weight": "65",
    "age": "30",
    "email": "test@gmail.com",
    "phone": "+7 323 838 98-12",
    "dob": "01011990",  # DD MM YYYY digits — mask formats as DD / MM / YYYY
}

DEVICE_NAME: str = "iPhone 12"
RESULTS_DIR: str = "results"
PLUGINS_DIR: str = "plugins"

MAX_STEPS: int = 120
TIMEOUT: int = 20_000
STEP_DELAY: int = 2_000

HEADLESS: bool = False
LOCALE: str = "en-US"
POPUP_TIMEOUT: int = 800
STUCK_LIMIT: int = 3

LLM_ENABLED: bool = True
LLM_PRIMARY: bool = False

OLLAMA_ENABLED: bool = True
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llava:7b")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-small-3.1-24b-instruct:free")
