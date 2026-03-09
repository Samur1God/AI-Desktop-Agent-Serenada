from __future__ import annotations

import ctypes
from core.logger import get_logger

logger = get_logger("Serenada")

# Windows virtual key codes for media keys
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _press_vk(vk: int) -> None:
    try:
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    except Exception as e:
        logger.warning("Media key error: %s", e)


def volume_up(times: int = 3) -> None:
    for _ in range(max(1, times)):
        _press_vk(VK_VOLUME_UP)


def volume_down(times: int = 3) -> None:
    for _ in range(max(1, times)):
        _press_vk(VK_VOLUME_DOWN)


def play_pause() -> None:
    _press_vk(VK_MEDIA_PLAY_PAUSE)


def next_track() -> None:
    _press_vk(VK_MEDIA_NEXT_TRACK)


def prev_track() -> None:
    _press_vk(VK_MEDIA_PREV_TRACK)


def set_master_volume_percent(percent: int) -> bool:
    """
    Устанавливает мастер-громкость Windows в процентах (0..100).
    Возвращает True если удалось, иначе False.
    """
    try:
        p = int(percent)
    except Exception:
        return False

    p = max(0, min(100, p))
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL  # type: ignore

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(p / 100.0, None)
        return True
    except Exception as e:
        logger.warning("Set volume error: %s", e)
        return False