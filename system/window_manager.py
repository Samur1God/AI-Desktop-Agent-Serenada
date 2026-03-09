from __future__ import annotations

from typing import Optional, Tuple

from core.logger import get_logger

logger = get_logger("Serenada")


class WindowManager:
    def __init__(self):
        try:
            import pygetwindow as gw  # type: ignore
        except Exception as e:
            raise RuntimeError("Не установлен pygetwindow. Установи: pip install pygetwindow") from e
        self.gw = gw

    def _find_window_by_part(self, title_part: str) -> Tuple[Optional[object], str]:
        title_part = (title_part or "").strip().lower()
        if not title_part:
            return None, ""

        # спец-слово "браузер"
        if title_part in {"браузер", "browser"}:
            for key in ["Yandex", "Chrome", "Microsoft Edge", "Edge", "Firefox", "Opera"]:
                w, t = self._find_window_by_part(key)
                if w:
                    return w, t
            return None, ""

        try:
            titles = self.gw.getAllTitles()
            wanted = title_part

            candidates = []
            for title in titles:
                if not title:
                    continue
                if wanted in title.lower():
                    wins = self.gw.getWindowsWithTitle(title)
                    if wins:
                        candidates.append((len(title), title, wins[0]))

            if not candidates:
                return None, ""

            candidates.sort(key=lambda x: x[0])
            _, title, win = candidates[0]
            return win, title
        except Exception:
            return None, ""

    def focus(self, title_part: str) -> Tuple[bool, str]:
        win, title = self._find_window_by_part(title_part)
        if not win:
            return False, ""

        try:
            try:
                if getattr(win, "isMinimized", False):
                    win.restore()
            except Exception:
                pass

            try:
                win.activate()
            except Exception:
                try:
                    win.minimize()
                    win.restore()
                    win.activate()
                except Exception:
                    pass

            logger.info("Focus window: %s", title)
            return True, title
        except Exception:
            return False, ""

    def minimize(self, title_part: str) -> Tuple[bool, str]:
        win, title = self._find_window_by_part(title_part)
        if not win:
            return False, ""
        try:
            win.minimize()
            return True, title
        except Exception:
            return False, ""

    def restore(self, title_part: str) -> Tuple[bool, str]:
        win, title = self._find_window_by_part(title_part)
        if not win:
            return False, ""
        try:
            try:
                win.restore()
            except Exception:
                pass
            try:
                win.activate()
            except Exception:
                pass
            return True, title
        except Exception:
            return False, ""

    def restore_or_focus_guess(self, app_name: str) -> bool:
        q = (app_name or "").strip().lower()
        if not q:
            return False

        mapping = {
            "steam": "Steam",
            "стим": "Steam",
            "telegram": "Telegram",
            "телеграм": "Telegram",
            "discord": "Discord",
            "браузер": "браузер",
            "browser": "браузер",
            "yandex": "Yandex",
            "яндекс": "Yandex",
            "музыка": "Музыка",
        }

        title_part = mapping.get(q, q)

        ok, _ = self.restore(title_part)
        if ok:
            return True

        ok, _ = self.focus(title_part)
        return ok

    def focus_any_browser(self) -> bool:
        ok, _ = self.focus("браузер")
        return ok


# ---------- Backward-compatible aliases (если где-то остался старый код) ----------
_default = WindowManager()


def focus_window(title_part: str) -> bool:
    ok, _ = _default.focus(title_part)
    return ok


def minimize_window(title_part: str) -> bool:
    ok, _ = _default.minimize(title_part)
    return ok


def restore_window(title_part: str) -> bool:
    ok, _ = _default.restore(title_part)
    return ok