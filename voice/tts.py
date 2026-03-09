from __future__ import annotations

import asyncio
import subprocess
import sys
import uuid
from pathlib import Path

from core.logger import get_logger

logger = get_logger("Serenada")


class TTS:
    def __init__(
        self,
        voice: str,
        base_dir: Path,
        edge_timeout_sec: float = 12.0,
        play_timeout_sec: float = 25.0,
    ):
        self.voice = voice
        self.base_dir = base_dir
        self.edge_timeout_sec = float(edge_timeout_sec)
        self.play_timeout_sec = float(play_timeout_sec)
        self._lock = asyncio.Lock()
        self._pygame_ready = False
        self._pygame = None

    def _ensure_pygame(self) -> None:
        if self._pygame_ready:
            return
        try:
            import pygame  # type: ignore
            pygame.mixer.init()
            self._pygame = pygame
            self._pygame_ready = True
        except Exception as e:
            raise RuntimeError(
                "Не удалось инициализировать pygame mixer. Установи: pip install pygame"
            ) from e

    def _synthesize_mp3(self, text: str, file_path: Path) -> None:
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "edge_tts",
                "--text",
                text,
                "--voice",
                self.voice,
                "--write-media",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=self.edge_timeout_sec,
        )
        if p.returncode != 0:
            msg = (p.stderr or p.stdout or "").strip()
            raise RuntimeError(msg or f"edge_tts failed with exit code {p.returncode}")

    async def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        async with self._lock:
            try:
                self._ensure_pygame()
            except Exception as e:
                logger.warning("TTS init error: %s", e)
                return

            file_path = self.base_dir / f"voice_{uuid.uuid4().hex}.mp3"

            try:
                await asyncio.to_thread(self._synthesize_mp3, text, file_path)

                self._pygame.mixer.music.load(str(file_path))
                self._pygame.mixer.music.play()

                started = asyncio.get_running_loop().time()
                while self._pygame.mixer.music.get_busy():
                    if (asyncio.get_running_loop().time() - started) > self.play_timeout_sec:
                        try:
                            self._pygame.mixer.music.stop()
                        except Exception:
                            pass
                        logger.warning("TTS playback timeout after %.1fs", self.play_timeout_sec)
                        break
                    await asyncio.sleep(0.08)

            except Exception as e:
                logger.warning("TTS error: %s", e)
            finally:
                try:
                    self._pygame.mixer.music.unload()
                except Exception:
                    pass
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass


# Алиас на случай старых импортов/опечаток
Tts = TTS

__all__ = ["TTS", "Tts"]