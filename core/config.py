from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    ai_name: str
    wake_word: str
    voice: str
    base_dir: Path
    api_key: str

    genai_model: str = "gemini-2.0-flash"

    # STT
    stt_language: str = "ru-RU"

    # Hotword listen
    hotword_timeout: int = 3
    hotword_phrase_time_limit: float = 3.0
    hotword_pause_threshold: float = 0.85

    # Command listen (важно для длинных запросов!)
    command_timeout: int = 15
    command_phrase_time_limit: Optional[float] = None   # None => слушать до паузы
    command_pause_threshold: float = 1.7                # больше => меньше обрываний

    intent_timeout_sec: int = 7

    # Launcher index cache
    app_index_cache_file: str = "apps_index.json"
    app_index_cache_ttl_hours: int = 72
    scan_all_drives: bool = True
    max_index_items: int = 120000

    # Yandex Music
    yandex_music_target: str = ""
    yandex_music_process: str = ""


def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].strip()
    return s


def load_config() -> Config:
    load_dotenv()

    base_dir = Path.home() / "SerenadaData"
    base_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

    return Config(
        ai_name=os.getenv("AI_NAME", "Серенада"),
        wake_word=os.getenv("WAKE_WORD", "серенада").strip().lower(),
        voice=os.getenv("VOICE", "ru-RU-SvetlanaNeural"),
        base_dir=base_dir,
        api_key=api_key,
        genai_model=os.getenv("GENAI_MODEL", "gemini-2.0-flash"),
        scan_all_drives=os.getenv("SCAN_ALL_DRIVES", "1").strip() not in {"0", "false", "False"},
        yandex_music_target=_strip_quotes(os.getenv("YANDEX_MUSIC_TARGET", "")),
        yandex_music_process=_strip_quotes(os.getenv("YANDEX_MUSIC_PROCESS", "")),
    )