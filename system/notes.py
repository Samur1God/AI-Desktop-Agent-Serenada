from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from core.logger import get_logger

logger = get_logger("Serenada")


def _desktop_notes_dir() -> Path:
    return Path.home() / "Desktop" / "SerenadaNotes"


def _clean(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_note_key(text: str) -> str:
    """
    Пытаемся вытащить ключ заметки:
    - из кавычек: "футбол"
    - из фразы "про футбол"
    - из фразы "на футбол"
    - иначе возвращаем начало строки
    """
    t = _clean(text).lower()

    m = re.search(r"[«\"\']([^»\"\']+)[»\"\']", t)
    if m:
        return _clean(m.group(1)).lower()

    m = re.search(r"\bпро\s+([a-zа-я0-9_ -]{2,})", t)
    if m:
        return _clean(m.group(1)).split(",")[0].lower()

    m = re.search(r"\bна\s+([a-zа-я0-9_ -]{2,})", t)
    if m:
        return _clean(m.group(1)).split(",")[0].lower()

    return t[:60].strip()


def _guess_title_from_text(t: str) -> str:
    t = _clean(t).lower()

    if "футбол" in t:
        return "футбол"

    if any(x in t for x in ["куп", "магаз", "продукт", "список"]):
        return "продукты"

    # "в 11 на футбол"
    m = re.search(r"\bв\s+\d{1,2}(:\d{2})?\s+на\s+([a-zа-я0-9_ -]{2,})", t)
    if m:
        return _clean(m.group(2)).split(",")[0].lower()

    m = re.search(r"\bна\s+([a-zа-я0-9_ -]{2,})", t)
    if m:
        return _clean(m.group(1)).split(",")[0].lower()

    return "заметка"


def parse_note_create(payload: str) -> Tuple[str, str]:
    """
    Создание:
    "что мне в 11 на футбол" -> title футбол, content "что мне в 11 на футбол"
    "мне надо купить в магазине хлеб..." -> title продукты
    """
    t = _clean(payload)
    if not t:
        return "заметка", ""

    title = _guess_title_from_text(t)
    content = t
    return title, content


def parse_note_update(payload: str) -> Tuple[str, str, str]:
    """
    Возвращает (title, content, mode)
    mode: replace / append
    """
    t = _clean(payload)
    if not t:
        return "", "", "replace"

    title = extract_note_key(t)

    mode = "replace"
    if any(x in t.lower() for x in ["добав", "дополн"]):
        mode = "append"

    content = t
    if "," in t:
        content = t.split(",", 1)[1].strip()
    elif ":" in t:
        content = t.split(":", 1)[1].strip()

    content = _clean(content)
    return title, content, mode


class NotesManager:
    """
    Заметки хранятся на рабочем столе:
    Desktop/SerenadaNotes/notes.json
    и также создаются отдельные *.txt по каждому названию заметки.
    """
    def __init__(self):
        self.dir = _desktop_notes_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "notes.json"
        self._data: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self._data = {str(k).lower(): str(v) for k, v in raw.items()}
        except Exception as e:
            logger.warning("Notes load error: %s", e)
            self._data = {}

    def _save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            self._sync_txt_files()
        except Exception as e:
            logger.warning("Notes save error: %s", e)

    def _safe_filename(self, title: str) -> str:
        name = re.sub(r"[\\/:*?\"<>|]+", "_", title.strip())
        return name[:80] if name else "заметка"

    def _sync_txt_files(self) -> None:
        for title, content in self._data.items():
            fn = self._safe_filename(title) + ".txt"
            p = self.dir / fn
            try:
                p.write_text(content, encoding="utf-8")
            except Exception:
                pass

    def upsert(self, title: str, content: str) -> None:
        title = _clean(title).lower() or "заметка"
        content = _clean(content)
        self._data[title] = content
        self._save()

    def update(self, title: str, content: str, mode: str = "replace") -> bool:
        key = _clean(title).lower()
        if key not in self._data:
            best = self._find_key_partial(key)
            if not best:
                return False
            key = best

        if mode == "append":
            self._data[key] = _clean(self._data[key] + "\n" + content)
        else:
            self._data[key] = _clean(content)

        self._save()
        return True

    def delete(self, title_or_key: str) -> bool:
        key = _clean(title_or_key).lower()
        if key in self._data:
            del self._data[key]
            self._save()
            return True

        best = self._find_key_partial(key)
        if best:
            del self._data[best]
            self._save()
            return True

        return False

    def list_titles(self) -> List[str]:
        return sorted(self._data.keys())

    def find_best(self, query: str) -> Optional[Tuple[str, str]]:
        q = _clean(query).lower()
        if not q:
            return None

        if q in self._data:
            return q, self._data[q]

        best = self._find_key_partial(q)
        if best:
            return best, self._data[best]

        for k, v in self._data.items():
            if q in v.lower():
                return k, v

        return None

    def _find_key_partial(self, q: str) -> Optional[str]:
        if not q:
            return None
        candidates = [k for k in self._data.keys() if q in k]
        if candidates:
            candidates.sort(key=len)
            return candidates[0]
        return None