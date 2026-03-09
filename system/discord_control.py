from __future__ import annotations

import time
from typing import Literal

import ctypes

from core.logger import get_logger

logger = get_logger("Serenada")

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_M = 0x4D

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _key_down(vk: int) -> None:
    try:
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
    except Exception as e:
        logger.warning("discord_control key down error: %s", e)


def _key_up(vk: int) -> None:
    try:
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.warning("discord_control key up error: %s", e)


def toggle_discord_mute(kind: Literal["mic", "deafen"] = "mic") -> None:
    """
    Жмём глобальный хоткей Discord:
    - Ctrl+Shift+M — mute микрофона
    - Ctrl+Shift+D — deafen (звук + микрофон)

    По умолчанию используем Ctrl+Shift+M. Важно:
    - Убедись, что в настройках Discord включён такой же глобальный hotkey.
    """
    # Предпочитаем pyautogui (часто надёжнее на некоторых системах),
    # иначе падаем на keybd_event.
    try:
        import pyautogui  # type: ignore

        if kind == "mic":
            pyautogui.hotkey("ctrl", "shift", "m")
        else:
            pyautogui.hotkey("ctrl", "shift", "d")
        logger.info("Discord %s toggle hotkey sent (pyautogui)", kind)
        return
    except Exception:
        pass

    vk_target = VK_M if kind == "mic" else 0x44  # 'D'

    try:
        _key_down(VK_CONTROL)
        _key_down(VK_SHIFT)
        _key_down(vk_target)
        time.sleep(0.05)
        _key_up(vk_target)
        _key_up(VK_SHIFT)
        _key_up(VK_CONTROL)
        logger.info("Discord %s toggle hotkey sent", kind)
    except Exception as e:
        logger.warning("Discord toggle error: %s", e)

