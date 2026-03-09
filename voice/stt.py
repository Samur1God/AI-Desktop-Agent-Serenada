from __future__ import annotations

from typing import Optional

import speech_recognition as sr

from core.logger import get_logger

logger = get_logger("Serenada")


class STT:
    def __init__(self, language: str = "ru-RU"):
        self.language = language
        self.recognizer = sr.Recognizer()

        # Базовые настройки (дальше можно переопределять pause_threshold в listen_once)
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.1
        self.recognizer.phrase_threshold = 0.25
        self.recognizer.non_speaking_duration = 0.55

        try:
            self.microphone = sr.Microphone()
        except Exception as e:
            raise RuntimeError("Микрофон не найден или нет доступа.") from e

    def listen_once(
        self,
        timeout: int,
        phrase_time_limit: Optional[float],
        pause_threshold_override: Optional[float] = None,
    ) -> str:
        """
        Одно прослушивание.
        phrase_time_limit=None => слушаем до паузы (не режет длинные фразы).
        pause_threshold_override => временно меняет порог паузы (важно для команд).
        """
        old_pause = self.recognizer.pause_threshold
        if pause_threshold_override is not None:
            self.recognizer.pause_threshold = float(pause_threshold_override)

        try:
            with self.microphone as source:
                try:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self.recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit
                    )
                except sr.WaitTimeoutError:
                    return ""
                except Exception as e:
                    logger.warning("STT listen error: %s", e)
                    return ""

            try:
                return self.recognizer.recognize_google(audio, language=self.language)
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                logger.warning("STT request error (Google): %s", e)
                return ""
            except Exception as e:
                logger.warning("STT recognize error: %s", e)
                return ""
        finally:
            self.recognizer.pause_threshold = old_pause


__all__ = ["STT"]