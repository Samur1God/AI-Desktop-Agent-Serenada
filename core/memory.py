from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List


@dataclass
class Message:
    role: str
    content: str


class ShortMemory:
    def __init__(self, size: int = 12):
        self._buffer: Deque[Message] = deque(maxlen=size)

    def add(self, role: str, content: str) -> None:
        self._buffer.append(Message(role=role, content=content))

    def get(self) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self._buffer]

    def clear(self) -> None:
        self._buffer.clear()