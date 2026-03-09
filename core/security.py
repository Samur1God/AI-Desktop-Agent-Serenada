from __future__ import annotations

import re
from typing import Iterable

# Блокируем только реально опасные системные команды/уничтожающие действия.
# НЕ блокируем "удали заметку" и т.п.

DANGEROUS_PATTERNS: Iterable[str] = [
    r"\brm\s+-rf\b",
    r"\bformat\s+[a-z]:\b",
    r"\bshutdown\b",
    r"\brestart\b",
    r"\bdel\s+/f\s+/s\b",
    r"\berase\s+/f\s+/s\b",
    r"\bRemove-Item\b",
    r"\bmkfs\b",
    r"\bchkdsk\s+/f\b",
    r"\bpowershell\b.*\bremove\b",
    r"\bудали\s+диск\b",
    r"\bформатировать\s+диск\b",
    r"\bудали\s+систем(у|ные)\b",
]

_COMPILED = [re.compile(pat, re.IGNORECASE) for pat in DANGEROUS_PATTERNS]


def is_safe_command(text: str) -> bool:
    """
    Возвращает True, если команда выглядит безопасной.
    """
    text = (text or "").strip()
    if not text:
        return True

    for rx in _COMPILED:
        if rx.search(text):
            return False
    return True


# Алиас для совместимости со старым кодом, если где-то импортируется is_safe()
def is_safe(text: str) -> bool:
    return is_safe_command(text)