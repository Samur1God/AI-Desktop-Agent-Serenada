from __future__ import annotations

import asyncio
import re
from pathlib import Path
import ctypes

from core.config import load_config
from core.logger import setup_logging, get_logger
from core.intents import IntentDetector
from core.assistant import Assistant
from system.launcher import AppLauncher
from system.window_manager import WindowManager
from voice.stt import STT
from voice.tts import TTS
from system.media_controls import volume_up


_single_instance_lock_file = None
_single_instance_mutex_handle = None


def _normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _contains_wake_word(text: str, wake_word: str) -> bool:
    if not text:
        return False
    pattern = rf"\b{re.escape(wake_word)}\b"
    return re.search(pattern, text.lower()) is not None


def _remove_wake_word(text: str, wake_word: str) -> str:
    pattern = rf"\b{re.escape(wake_word)}\b"
    cleaned = re.sub(pattern, "", text.lower(), count=1).strip(" ,.!?:;")
    cleaned = _normalize_text(cleaned)
    return cleaned


def _beep():
    try:
        import winsound  # type: ignore
        winsound.Beep(900, 120)
    except Exception:
        pass


def _acquire_single_instance_lock(base_dir: Path) -> bool:
    """
    Простейший файловый лок: не даёт запустить несколько Серенад одновременно.
    Работает только в рамках одного пользователя/папки данных, чего здесь достаточно.
    """
    global _single_instance_lock_file
    lock_path = base_dir / "serenada.lock"

    try:
        # Создаём/открываем файл и пытаемся заблокировать его.
        f = lock_path.open("w")
        try:
            import msvcrt  # type: ignore

            # Блокируем 1 байт, чтобы другие процессы не смогли наложить лок.
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            # Уже заблокирован другим процессом.
            f.close()
            return False
        except Exception:
            # Если вдруг нет msvcrt или ошибка — просто позволяем запуск (не жёстко)
            _single_instance_lock_file = f
            return True

        _single_instance_lock_file = f
        return True
    except Exception:
        return True


def _acquire_single_instance_mutex() -> bool:
    """
    Самый надёжный single-instance для Windows: именованный mutex.
    """
    global _single_instance_mutex_handle
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, True, "Local\\SerenadaAssistantMutex")
        if not handle:
            return True
        # 183 = ERROR_ALREADY_EXISTS
        if kernel32.GetLastError() == 183:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            return False
        _single_instance_mutex_handle = handle
        return True
    except Exception:
        return True


async def main() -> None:
    cfg = load_config()

    setup_logging(cfg.base_dir, name="Serenada")
    logger = get_logger("Serenada")

    if not _acquire_single_instance_mutex():
        print(f"{cfg.ai_name} уже запущена. Второй экземпляр не нужен, выхожу.")
        logger.info("Another Serenada instance (mutex) already running; exiting.")
        return

    if not _acquire_single_instance_lock(cfg.base_dir):
        # Уже запущен другой экземпляр — просто выходим.
        print(f"{cfg.ai_name} уже запущена. Второй экземпляр не нужен, выхожу.")
        logger.info("Another Serenada instance is already running; exiting.")
        return

    logger.info("Starting %s ...", cfg.ai_name)

    stt = STT(language=cfg.stt_language)
    tts = TTS(voice=cfg.voice, base_dir=cfg.base_dir)

    detector = IntentDetector(api_key=cfg.api_key, model_name=cfg.genai_model)

    launcher = AppLauncher(
        base_dir=cfg.base_dir,
        cache_filename=cfg.app_index_cache_file,
        cache_ttl_hours=cfg.app_index_cache_ttl_hours,
        scan_all_drives=cfg.scan_all_drives,
        max_items=cfg.max_index_items,
    )

    window_manager = WindowManager()

    assistant = Assistant(
        cfg=cfg,
        intent_detector=detector,
        tts=tts,
        launcher=launcher,
        window_manager=window_manager,
    )

    # Прогрев индекса при старте (чтобы потом было мгновенно)
    logger.info("Startup: announce scan (TTS) ...")
    await tts.speak("Запускаюсь. Сканирую приложения. Это может занять время.")
    logger.info("Startup: announce scan (TTS) done")
    logger.info("Startup: launcher warm_up ...")
    await asyncio.to_thread(launcher.warm_up)
    logger.info("Startup: launcher warm_up done")
    logger.info("Startup: announce ready (TTS) ...")
    await tts.speak("Сканирование завершено. Я готова слушать команды.")
    logger.info("Startup: announce ready (TTS) done")
    print(f"--- [ {cfg.wake_word.upper()} В СЕТИ ] ---")

    while True:
        try:
            loop = asyncio.get_running_loop()

            # ЭТАП 1: ловим wake word коротко
            hot = await loop.run_in_executor(
                None,
                lambda: stt.listen_once(
                    timeout=cfg.hotword_timeout,
                    phrase_time_limit=cfg.hotword_phrase_time_limit,
                    pause_threshold_override=cfg.hotword_pause_threshold,
                )
            )
            hot = _normalize_text(hot)
            if not hot:
                continue

            print(f"Распознано (hotword): {hot}")

            if not _contains_wake_word(hot, cfg.wake_word):
                continue

            command = _remove_wake_word(hot, cfg.wake_word)

            # Если сказал только "Серенада" — делаем чуть громче и слушаем команду
            if not command:
                volume_up(times=2)
                _beep()

                cmd = await loop.run_in_executor(
                    None,
                    lambda: stt.listen_once(
                        timeout=cfg.command_timeout,
                        phrase_time_limit=cfg.command_phrase_time_limit,  # None => слушаем до паузы
                        pause_threshold_override=cfg.command_pause_threshold,
                    )
                )
                cmd = _normalize_text(cmd)
                if not cmd:
                    continue

                if _contains_wake_word(cmd, cfg.wake_word):
                    cmd = _remove_wake_word(cmd, cfg.wake_word)

                if not cmd:
                    continue

                print(f"Распознано (command): {cmd}")
                keep_running = await assistant.handle(cmd, intent_timeout=cfg.intent_timeout_sec)
                if not keep_running:
                    break
                continue

            # Команда была в той же фразе
            print(f"Команда из той же фразы: {command}")
            keep_running = await assistant.handle(command, intent_timeout=cfg.intent_timeout_sec)
            if not keep_running:
                break

        except KeyboardInterrupt:
            print(f"\n{cfg.ai_name}: До связи, сэр.")
            break
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Main loop error: %s", e)
            await asyncio.sleep(0.4)


if __name__ == "__main__":
    asyncio.run(main())