from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict

from core.config import Config
from core.security import is_safe_command
from core.memory import ShortMemory
from core.logger import get_logger
from core.intents import IntentDetector

from system.launcher import AppLauncher
from system.window_manager import WindowManager
from system.media_controls import volume_up, volume_down, play_pause, next_track, prev_track, set_master_volume_percent
from system.browser import open_search, open_youtube_search
from system.notes import NotesManager, parse_note_create, parse_note_update, extract_note_key
from system.note_window import show_note_window, close_note_window
from system.discord_control import toggle_discord_mute
from system.system_info import take_snapshot

from voice.tts import TTS

logger = get_logger("Serenada")


class Assistant:
    def __init__(self, cfg: Config, intent_detector: IntentDetector, tts: TTS, launcher: AppLauncher, window_manager: WindowManager):
        self.cfg = cfg
        self.intent_detector = intent_detector
        self.tts = tts
        self.launcher = launcher
        self.window_manager = window_manager
        self.memory = ShortMemory(size=12)
        self.notes = NotesManager()  # хранит на Desktop

        self._handlers: Dict[str, Callable[[str], Awaitable[bool]]] = {
            "launch_app": self._handle_launch,
            "focus_window": self._handle_focus,
            "minimize_window": self._handle_minimize,
            "restore_window": self._handle_restore,
            "exit_assistant": self._handle_exit,
            "volume_up": self._handle_volume_up,
            "volume_down": self._handle_volume_down,
            "play_pause": self._handle_play_pause,
            "next_track": self._handle_next_track,
            "prev_track": self._handle_prev_track,
            "web_search": self._handle_web_search,
            "yandex_music": self._handle_yandex_music,
            "note_create": self._handle_note_create,
            "note_update": self._handle_note_update,
            "note_read": self._handle_note_read,
            "note_delete": self._handle_note_delete,
            "note_list": self._handle_note_list,
            "note_close": self._handle_note_close,
            "reindex_apps": self._handle_reindex,
            "discord_mute_toggle": self._handle_discord_mute_toggle,
            "youtube_open_search": self._handle_youtube_open_search,
            "youtube_pause": self._handle_youtube_pause,
            "youtube_seek_forward": self._handle_youtube_seek_forward,
            "youtube_seek_backward": self._handle_youtube_seek_backward,
            "system_info": self._handle_system_info,
            "set_volume": self._handle_set_volume,
            "chat": self._handle_chat,
        }

    async def handle(self, text: str, intent_timeout: int = 6) -> bool:
        text = (text or "").strip()
        if not text:
            return True

        if not is_safe_command(text):
            await self.tts.speak("Эта команда может быть опасной. Я не буду её выполнять.")
            return True

        self.memory.add("user", text)

        intent_data = await self.intent_detector.detect(text, timeout_sec=intent_timeout)
        intent = intent_data.get("intent", "chat")
        value = intent_data.get("value", "")

        logger.info("Intent: %s | Value: %r", intent, value)

        handler = self._handlers.get(intent, self._handle_chat)
        return await handler(value)

    # ----------- Apps / Windows -----------

    async def _handle_launch(self, app_name: str) -> bool:
        app_name = (app_name or "").strip().lower()
        if not app_name:
            await self.tts.speak("Скажи, что нужно открыть.")
            return True

        # Музыка
        if app_name in {"музыка", "яндекс музыка", "yandex music"} or ("яндекс" in app_name and "музык" in app_name):
            return await self._handle_yandex_music("")

        # Если окно уже есть — просто активируем/разворачиваем
        if self.window_manager.restore_or_focus_guess(app_name):
            await self.tts.speak("Ок.")
            return True

        ok, used_name = self.launcher.launch(app_name)
        if ok:
            await self.tts.speak(f"Запускаю {used_name}.")
        else:
            await self.tts.speak("Не нашла приложение. Назови точнее.")
        return True

    async def _handle_focus(self, title_part: str) -> bool:
        title_part = (title_part or "").strip()
        if not title_part:
            await self.tts.speak("Скажи, на какое окно переключиться.")
            return True

        ok, matched = self.window_manager.focus(title_part)
        if ok:
            await self.tts.speak(f"Переключаю на {matched}.")
        else:
            await self.tts.speak("Окно не найдено.")
        return True

    async def _handle_minimize(self, title_part: str) -> bool:
        q = (title_part or "").strip()
        if not q:
            await self.tts.speak("Скажи, какое окно свернуть.")
            return True

        ok, matched = self.window_manager.minimize(q)
        if ok:
            await self.tts.speak("Свернула.")
        else:
            await self.tts.speak("Окно не найдено.")
        return True

    async def _handle_restore(self, title_part: str) -> bool:
        q = (title_part or "").strip()
        if not q:
            await self.tts.speak("Скажи, какое окно развернуть.")
            return True

        ok, matched = self.window_manager.restore(q)
        if ok:
            await self.tts.speak("Ок.")
        else:
            await self.tts.speak("Окно не найдено.")
        return True

    # ----------- Exit -----------

    async def _handle_exit(self, _: str) -> bool:
        await self.tts.speak("Выключаюсь. До связи.")
        return False

    # ----------- Media -----------

    async def _handle_volume_up(self, _: str) -> bool:
        volume_up(times=4)
        await self.tts.speak("Сделала громче.")
        return True

    async def _handle_volume_down(self, _: str) -> bool:
        volume_down(times=4)
        await self.tts.speak("Сделала тише.")
        return True

    async def _handle_play_pause(self, _: str) -> bool:
        play_pause()
        await self.tts.speak("Ок.")
        return True

    async def _handle_next_track(self, _: str) -> bool:
        next_track()
        await self.tts.speak("Следующий.")
        return True

    async def _handle_prev_track(self, _: str) -> bool:
        prev_track()
        await self.tts.speak("Предыдущий.")
        return True

    # ----------- Web Search -----------

    async def _handle_web_search(self, query: str) -> bool:
        query = (query or "").strip()
        if not query:
            await self.tts.speak("Скажи, что искать.")
            return True

        # Попытаемся сфокусировать браузер, если открыт (не обязательно)
        self.window_manager.focus_any_browser()
        open_search(query)
        await self.tts.speak("Ищу.")
        return True

    # ----------- Yandex Music -----------

    async def _handle_yandex_music(self, _: str) -> bool:
        target = (self.cfg.yandex_music_target or "").strip()
        proc = (self.cfg.yandex_music_process or "").strip()

        # если уже запущена — play/pause
        if self.launcher.is_process_running(proc or target):
            play_pause()
            await self.tts.speak("Ок.")
            return True

        if target:
            ok = self.launcher.launch_target(target)
            if ok:
                await self.tts.speak("Открываю Яндекс Музыку.")
            else:
                await self.tts.speak("Не смогла открыть Яндекс Музыку. Проверь путь в .env.")
            return True

        # fallback: попробуем по индексу
        ok, _ = self.launcher.launch("yandex music")
        if ok:
            await self.tts.speak("Открываю Яндекс Музыку.")
        else:
            await self.tts.speak("Не нашла Яндекс Музыку. Укажи YANDEX_MUSIC_TARGET в .env.")
        return True

    # ----------- Notes -----------

    async def _handle_note_create(self, payload: str) -> bool:
        title, content = parse_note_create(payload)
        self.notes.upsert(title, content)
        show_note_window(title, content)
        await self.tts.speak(f"Записала заметку {title}.")
        return True

    async def _handle_note_update(self, payload: str) -> bool:
        title, content, mode = parse_note_update(payload)
        if not title:
            await self.tts.speak("Скажи, какую заметку изменить.")
            return True

        ok = self.notes.update(title, content, mode=mode)
        if ok:
            note = self.notes.find_best(title)
            if note:
                show_note_window(note[0], note[1])
            await self.tts.speak(f"Обновила заметку {title}.")
        else:
            await self.tts.speak("Такой заметки нет.")
        return True

    async def _handle_note_read(self, payload: str) -> bool:
        key = extract_note_key(payload)
        note = self.notes.find_best(key)
        if not note:
            await self.tts.speak("Не нашла такую заметку.")
            return True

        title, content = note
        show_note_window(title, content)
        await self.tts.speak(f"Заметка {title}. {content}")
        return True

    async def _handle_note_delete(self, payload: str) -> bool:
        key = extract_note_key(payload)
        if not key:
            await self.tts.speak("Скажи, какую заметку удалить.")
            return True

        ok = self.notes.delete(key)
        if ok:
            await self.tts.speak("Удалено.")
        else:
            await self.tts.speak("Не нашла такую заметку.")
        return True

    async def _handle_note_list(self, _: str) -> bool:
        titles = self.notes.list_titles()
        if not titles:
            await self.tts.speak("Заметок пока нет.")
            return True
        await self.tts.speak("У тебя есть заметки: " + ", ".join(titles[:12]))
        return True

    async def _handle_note_close(self, _: str) -> bool:
        close_note_window()
        await self.tts.speak("Ок.")
        return True

    # ----------- Index -----------

    async def _handle_reindex(self, _: str) -> bool:
        await self.tts.speak("Обновляю индекс приложений.")
        await asyncio.to_thread(self.launcher.rebuild_index)
        await self.tts.speak("Индекс обновлён. Я готова.")
        return True

    # ----------- Discord / браузер / система -----------

    async def _handle_discord_mute_toggle(self, _: str) -> bool:
        # Сфокусируем Discord — так хоткей обычно ловится лучше.
        try:
            self.window_manager.focus("Discord")
        except Exception:
            pass
        toggle_discord_mute("mic")
        await self.tts.speak("Переключаю микрофон в Дискорде.")
        return True

    async def _handle_youtube_open_search(self, query: str) -> bool:
        q = (query or "").strip()
        if not q:
            await self.tts.speak("Скажи, что искать на Ютубе.")
            return True

        self.window_manager.focus_any_browser()
        open_youtube_search(q)
        await self.tts.speak("Открываю Ютуб по запросу.")
        return True

    async def _handle_youtube_pause(self, _: str) -> bool:
        # В большинстве браузеров пробел — пауза/старт видео на YouTube, когда вкладка активна.
        try:
            import pyautogui  # type: ignore

            self.window_manager.focus_any_browser()
            await asyncio.sleep(0.1)
            pyautogui.press("space")
            await self.tts.speak("Пауза.")
        except Exception:
            await self.tts.speak("Не получилось нажать паузу в браузере.")
        return True

    async def _handle_youtube_seek_forward(self, seconds_str: str) -> bool:
        sec = 10
        try:
            sec = max(1, min(60, int((seconds_str or "10").strip())))
        except Exception:
            pass

        try:
            import pyautogui  # type: ignore

            self.window_manager.focus_any_browser()
            await asyncio.sleep(0.1)
            # На YouTube стрелка вправо = +5 секунд. Нажмём нужное количество раз.
            steps = max(1, sec // 5)
            for _ in range(steps):
                pyautogui.press("right")
                await asyncio.sleep(0.05)
            await self.tts.speak("Проматываю вперёд.")
        except Exception:
            await self.tts.speak("Не получилось перемотать видео вперёд.")
        return True

    async def _handle_youtube_seek_backward(self, seconds_str: str) -> bool:
        sec = 10
        try:
            sec = max(1, min(60, int((seconds_str or "10").strip())))
        except Exception:
            pass

        try:
            import pyautogui  # type: ignore

            self.window_manager.focus_any_browser()
            await asyncio.sleep(0.1)
            # Стрелка влево = -5 секунд.
            steps = max(1, sec // 5)
            for _ in range(steps):
                pyautogui.press("left")
                await asyncio.sleep(0.05)
            await self.tts.speak("Проматываю назад.")
        except Exception:
            await self.tts.speak("Не получилось перемотать видео назад.")
        return True

    async def _handle_system_info(self, _: str) -> bool:
        snap = take_snapshot()
        hours = snap.uptime_minutes // 60
        minutes = snap.uptime_minutes % 60

        parts = []
        parts.append(f"Загрузка процессора около {round(snap.cpu_percent)} процентов.")
        parts.append(
            f"Память: занято примерно {snap.used_memory_gb} гигабайт из {snap.total_memory_gb}."
        )
        if hours > 0:
            parts.append(f"Компьютер включён примерно {hours} часов {minutes} минут.")
        else:
            parts.append(f"Компьютер включён примерно {minutes} минут.")

        await self.tts.speak(" ".join(parts))
        return True

    async def _handle_set_volume(self, value: str) -> bool:
        try:
            p = int((value or "").strip())
        except Exception:
            await self.tts.speak("Скажи громкость числом от нуля до ста.")
            return True

        ok = set_master_volume_percent(p)
        if ok:
            await self.tts.speak(f"Громкость {max(0, min(100, p))} процентов.")
        else:
            await self.tts.speak("Не смогла изменить громкость.")
        return True

    async def _handle_chat(self, text: str) -> bool:
        # если это похоже на запрос — делаем поиск даже без "загугли"
        t = (text or "").strip()
        if t and len(t) >= 12 and any(t.lower().startswith(x) for x in ("как ", "что ", "почему ", "где ", "когда ", "рецепт ")):
            return await self._handle_web_search(t)

        await self.tts.speak("Скажи команду: музыка, поиск, заметка или окна.")
        return True