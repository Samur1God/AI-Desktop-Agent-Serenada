from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional

from core.logger import get_logger

logger = get_logger("Serenada")

VALID_INTENTS = {
    "launch_app",
    "focus_window",
    "minimize_window",
    "restore_window",
    "exit_assistant",
    "volume_up",
    "volume_down",
    "play_pause",
    "next_track",
    "prev_track",
    "web_search",
    "yandex_music",
    "note_create",
    "note_update",
    "note_read",
    "note_delete",
    "note_list",
    "note_close",
    "reindex_apps",
    "discord_mute_toggle",
    "youtube_open_search",
    "youtube_pause",
    "youtube_seek_forward",
    "youtube_seek_backward",
    "system_info",
    "set_volume",
    "chat",
}

_TRASH_TAIL_RX = re.compile(r"[,.!?:;]+$")


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = _TRASH_TAIL_RX.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower().strip()


# --- Команды ---
_LAUNCH_RX = re.compile(r"^(?:открой|открыть|запусти|запустить|включи|включить|стартуй|start)\s+(.+)$", re.I)
_FOCUS_RX = re.compile(r"^(?:переключись|переключи|фокус|сфокусируй|покажи|показать)\s+(?:на\s+)?(.+)$", re.I)

_MIN_RX = re.compile(r"^(?:сверни|свернуть|минимизируй|уменьши\s+окно)\s+(.+)$", re.I)
_RESTORE_RX = re.compile(r"^(?:разверни|развернуть|восстанови\s+окно|покажи\s+окно)\s+(.+)$", re.I)

_EXIT_RX = re.compile(r"^(?:выключись|выключайся|заверши\s+работу|завершись|выход)$", re.I)
_EXIT2_RX = re.compile(r"^(?:выключи(?:сь)?\s+себя|отключись|закройся)$", re.I)

_VOL_UP_RX = re.compile(r"^(?:громче|погромче|увеличь\s+громкость|сделай\s+громче|прибавь\s+громкость)$", re.I)
_VOL_DOWN_RX = re.compile(r"^(?:тише|потише|уменьши\s+громкость|сделай\s+тише|убавь\s+громкость)$", re.I)

_PLAY_PAUSE_RX = re.compile(r"^(?:пауза|поставь\s+на\s+паузу|продолжай|возобнови|возобновить|играй|play)$", re.I)
_NEXT_RX = re.compile(r"^(?:дальше|следующий|следующий\s+трек|next)$", re.I)
_PREV_RX = re.compile(r"^(?:назад|предыдущий|прошлый|предыдущий\s+трек|previous)$", re.I)

_REINDEX_RX = re.compile(r"^(?:обнови\s+индекс|пересканируй\s+приложения|просканируй\s+приложения|обнови\s+базу\s+приложений)$", re.I)

_NOTE_CLOSE_RX = re.compile(r"^(?:закрой\s+заметку|убери\s+заметку|скрой\s+заметку)$", re.I)
_NOTE_LIST_RX = re.compile(r"^(?:список\s+заметок|покажи\s+заметки|какие\s+заметки)$", re.I)
_NOTE_DELETE_RX = re.compile(r"^(?:удали)\s+(?:заметку|список)\s*(.*)$", re.I)
_NOTE_UPDATE_RX = re.compile(r"^(?:измени|обнови)\s+заметку\s*(.*)$", re.I)
_NOTE_CREATE_RX = re.compile(r"^(?:сделай|создай)\s+заметку\s*(.*)$", re.I)
_NOTE_MEMORIZE_RX = re.compile(r"^(?:запомни)\s*(.*)$", re.I)
_NOTE_READ_RX = re.compile(r"^(?:напомни|найди\s+заметку|покажи\s+заметку)\s*(.*)$", re.I)

# Поиск
_WEB_TRIG_RX = re.compile(r"^(?:загугли|гугли|поищи|ищи|найди|найди\s+мне|поиск)\s+(.+)$", re.I)
_AUTO_QUESTION_RX = re.compile(r"^(?:как|что|почему|где|когда|сколько|какой|какая|какое|рецепт)\b.+$", re.I)

# Музыка
_MUSIC_RX = re.compile(r"^(?:музыка|яндекс\s+музыка|yandex\s+music)$", re.I)

# Discord
_DISCORD_MUTE_RX = re.compile(r"^(?:заглуши|выключи|отключи)\s+(?:микрофон|мик)$", re.I)
_DISCORD_UNMUTE_RX = re.compile(r"^(?:включи|восстанови)\s+(?:микрофон|мик)$", re.I)

# YouTube / браузер видео
_YT_OPEN_RX = re.compile(r"^(?:открой|запусти)\s+youtube\s+(.+)$", re.I)
_YT_MUSIC_RX = re.compile(r"^(?:открой|включи|запусти)\s+музык[ау]\s+(.+)$", re.I)
_YT_PAUSE_RX = re.compile(r"^(?:пауза\s+видео|поставь\s+видео\s+на\s+паузу|продолжи\s+видео|продолжай\s+видео)$", re.I)
_YT_FWD_RX = re.compile(r"^(?:перемотай|промотай)\s+(?:вперёд|вперед)\s*(\d+)?\s*(?:секунд[уы]?)?$", re.I)
_YT_BACK_RX = re.compile(r"^(?:перемотай|промотай)\s+назад\s*(\d+)?\s*(?:секунд[уы]?)?$", re.I)

# Системная информация
_SYS_INFO_RX = re.compile(
    r"^(?:какая\s+)?(?:нагрузка|загрузка)\s+процессора|"
    r"сколько\s+памяти\s+занято|"
    r"сколько\s+памяти\s+свободно|"
    r"состояние\s+системы|"
    r"как\s+себя\s+чувствует\s+комп(ьютер)?$",
    re.I,
)


def _local_detect(text: str) -> Dict[str, str]:
    t = _norm(text)
    if not t:
        return {"intent": "chat", "value": ""}

    if _EXIT_RX.match(t):
        return {"intent": "exit_assistant", "value": ""}
    if _EXIT2_RX.match(t):
        return {"intent": "exit_assistant", "value": ""}

    if _REINDEX_RX.match(t):
        return {"intent": "reindex_apps", "value": ""}

    if _NOTE_CLOSE_RX.match(t):
        return {"intent": "note_close", "value": ""}

    if _VOL_UP_RX.match(t):
        return {"intent": "volume_up", "value": ""}
    if _VOL_DOWN_RX.match(t):
        return {"intent": "volume_down", "value": ""}

    if _NEXT_RX.match(t):
        return {"intent": "next_track", "value": ""}
    if _PREV_RX.match(t):
        return {"intent": "prev_track", "value": ""}
    if _PLAY_PAUSE_RX.match(t):
        return {"intent": "play_pause", "value": ""}

    if _MUSIC_RX.match(t):
        return {"intent": "yandex_music", "value": ""}

    if _DISCORD_MUTE_RX.match(t) or _DISCORD_UNMUTE_RX.match(t):
        # Для простоты одно действие — toggle. Discord сам покажет состояние.
        return {"intent": "discord_mute_toggle", "value": ""}

    m = _YT_OPEN_RX.match(t)
    if m:
        return {"intent": "youtube_open_search", "value": _norm(m.group(1))}

    m = _YT_MUSIC_RX.match(t)
    if m:
        return {"intent": "youtube_open_search", "value": _norm(m.group(1))}

    if _YT_PAUSE_RX.match(t):
        return {"intent": "youtube_pause", "value": ""}

    m = _YT_FWD_RX.match(t)
    if m:
        seconds = m.group(1) or "10"
        return {"intent": "youtube_seek_forward", "value": seconds}

    m = _YT_BACK_RX.match(t)
    if m:
        seconds = m.group(1) or "10"
        return {"intent": "youtube_seek_backward", "value": seconds}

    if _SYS_INFO_RX.match(t):
        return {"intent": "system_info", "value": ""}

    # Установка громкости: "громкость 30", "громкость на 30", "музыку на 30"
    m = re.match(r"^(?:громкость|звук|музык[ау])\s*(?:на\s*)?(\d{1,3})\s*(?:%|процент(?:а|ов)?)?$", t, flags=re.I)
    if m:
        return {"intent": "set_volume", "value": m.group(1)}

    m = _MIN_RX.match(t)
    if m:
        return {"intent": "minimize_window", "value": _norm(m.group(1))}

    m = _RESTORE_RX.match(t)
    if m:
        return {"intent": "restore_window", "value": _norm(m.group(1))}

    m = _WEB_TRIG_RX.match(t)
    if m:
        return {"intent": "web_search", "value": _norm(m.group(1))}

    if _AUTO_QUESTION_RX.match(t) and len(t) >= 12:
        return {"intent": "web_search", "value": t}

    if _NOTE_LIST_RX.match(t):
        return {"intent": "note_list", "value": ""}

    m = _NOTE_DELETE_RX.match(t)
    if m:
        return {"intent": "note_delete", "value": _norm(m.group(1))}

    m = _NOTE_UPDATE_RX.match(t)
    if m:
        return {"intent": "note_update", "value": _norm(m.group(1))}

    m = _NOTE_CREATE_RX.match(t)
    if m:
        return {"intent": "note_create", "value": _norm(m.group(1))}

    m = _NOTE_MEMORIZE_RX.match(t)
    if m:
        return {"intent": "note_create", "value": _norm(m.group(1))}

    if t.startswith("напомни мне") and ("куп" in t or "магаз" in t or "надо" in t or "нужно" in t):
        payload = t.replace("напомни мне", "", 1).strip()
        return {"intent": "note_create", "value": payload}

    m = _NOTE_READ_RX.match(t)
    if m:
        return {"intent": "note_read", "value": _norm(m.group(1))}

    m = _LAUNCH_RX.match(t)
    if m:
        return {"intent": "launch_app", "value": _norm(m.group(1))}

    m = _FOCUS_RX.match(t)
    if m:
        return {"intent": "focus_window", "value": _norm(m.group(1))}

    return {"intent": "chat", "value": t}


# --- LLM (опционально) ---
SYSTEM_PROMPT = """
Верни СТРОГО JSON:
{"intent":"launch_app|focus_window|minimize_window|restore_window|exit_assistant|volume_up|volume_down|play_pause|next_track|prev_track|web_search|yandex_music|note_create|note_update|note_read|note_delete|note_list|note_close|reindex_apps|chat","value":"..."}
"""


def _extract_json(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    return m.group(0).strip() if m else None


def _validate(parsed: Dict[str, Any], fallback_text: str) -> Dict[str, str]:
    intent = str(parsed.get("intent", "chat")).strip()
    value = parsed.get("value", "")
    if intent not in VALID_INTENTS:
        return {"intent": "chat", "value": fallback_text}
    if not isinstance(value, str):
        value = str(value)
    value = _norm(value)
    if intent == "chat" and not value:
        value = fallback_text
    return {"intent": intent, "value": value}


class IntentDetector:
    """
    Сначала локально (без сети), потом (опционально) LLM.
    Если LLM не работает — всё равно будет работать локальная логика.
    """
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-2.0-flash", enable_llm: bool = True):
        self.api_key = api_key
        self.model_name = model_name
        self.enable_llm = enable_llm and bool(api_key)
        self._client = None
        self._config = None

        if self.enable_llm:
            try:
                from google import genai
                from google.genai import types

                self._client = genai.Client(api_key=api_key)
                self._config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                )
            except Exception as e:
                logger.warning("LLM disabled: %s", e)
                self.enable_llm = False

    async def detect(self, text: str, timeout_sec: int = 7) -> Dict[str, str]:
        local = _local_detect(text)
        if local["intent"] != "chat":
            return local

        if not self.enable_llm or not self._client:
            return local

        prompt = f"{SYSTEM_PROMPT}\nПользователь: {text}"
        try:
            resp = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self._config,
                ),
                timeout=timeout_sec,
            )
            raw = (getattr(resp, "text", "") or "").strip()
            json_str = _extract_json(raw) or raw
            parsed = json.loads(json_str)
            return _validate(parsed, fallback_text=text)
        except Exception as e:
            logger.warning("LLM error (fallback local): %s", e)
            return local