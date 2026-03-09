from __future__ import annotations

import datetime as _dt
import os
import time
from dataclasses import dataclass

import psutil  # type: ignore


@dataclass(frozen=True)
class SystemSnapshot:
    cpu_percent: float
    memory_percent: float
    total_memory_gb: float
    used_memory_gb: float
    uptime_minutes: int


def take_snapshot() -> SystemSnapshot:
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()

    try:
        boot_ts = psutil.boot_time()
    except Exception:
        boot_ts = time.time()

    uptime_sec = int(time.time() - boot_ts)

    return SystemSnapshot(
        cpu_percent=float(cpu),
        memory_percent=float(vm.percent),
        total_memory_gb=round(vm.total / (1024 ** 3), 1),
        used_memory_gb=round((vm.total - vm.available) / (1024 ** 3), 1),
        uptime_minutes=uptime_sec // 60,
    )

