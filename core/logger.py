from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(base_dir: Path, name: str = "Serenada") -> logging.Logger:
    """
    Настраивает логирование (в файл + консоль) один раз.
    """
    log_file = base_dir / "serenada.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # чтобы не дублировалось в root logger

    # Если уже настроено — не добавляем хендлеры повторно
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


# Алиас на случай, если где-то осталось старое имя функции
def setup_logger(base_dir: Path, name: str = "Serenada") -> logging.Logger:
    return setup_logging(base_dir=base_dir, name=name)


def get_logger(name: str = "Serenada") -> logging.Logger:
    """
    Возвращает логгер (если setup_logging уже вызывали — будет настроенным).
    """
    return logging.getLogger(name)