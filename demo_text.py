from __future__ import annotations

import asyncio
import os
import sys

from core.config import load_config
from core.intents import IntentDetector
from core.logger import get_logger, setup_logging


def _fmt(intent: str, value: str) -> str:
    value = (value or "").strip()
    if value:
        return f"{intent} | value={value!r}"
    return intent


async def run_demo() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    cfg = load_config()
    setup_logging(cfg.base_dir, name="Serenada")
    logger = get_logger("Serenada")

    # Демо без LLM (без ключей/сети). Это показывает, что ассистент УЖЕ умеет оффлайн.
    detector = IntentDetector(api_key=cfg.api_key, model_name=cfg.genai_model, enable_llm=False)

    samples = [
        "открой телеграм",
        "открой steam",
        "переключись на браузер",
        "сверни дискорд",
        "разверни телеграм",
        "громче",
        "тише",
        "пауза",
        "следующий трек",
        "предыдущий трек",
        "загугли погода в москве",
        "как приготовить пасту карбонара",
        "создай заметку купить молоко",
        "список заметок",
        "удали заметку молоко",
        "обнови индекс приложений",
        "выход",
    ]

    logger.info("=== Serenada text demo (intent detection) ===")
    for s in samples:
        data = await detector.detect(s, timeout_sec=3)
        print(f"{s!r} -> {_fmt(data.get('intent',''), data.get('value',''))}")

    if os.getenv("DEMO_REPL", "1").strip() in {"0", "false", "False"}:
        return

    print("\nТеперь можно вводить свои фразы. Пустая строка — выход.\n")
    while True:
        try:
            s = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not s:
            break
        data = await detector.detect(s, timeout_sec=3)
        print(_fmt(data.get("intent", ""), data.get("value", "")))


if __name__ == "__main__":
    asyncio.run(run_demo())

