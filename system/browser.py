from __future__ import annotations

import subprocess
from urllib.parse import quote_plus


def open_url(url: str) -> None:
    url = (url or "").strip()
    if not url:
        return
    subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)


def open_search(query: str) -> None:
    """
    Открывает поиск Google в браузере.
    Работает надёжно на Windows через 'start'.
    """
    q = quote_plus((query or "").strip())
    if not q:
        return

    url = f"https://www.google.com/search?q={q}"

    open_url(url)


def open_youtube_search(query: str) -> None:
    q = quote_plus((query or "").strip())
    if not q:
        return
    open_url(f"https://www.youtube.com/results?search_query={q}")