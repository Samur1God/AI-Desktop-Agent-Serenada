from __future__ import annotations

import json
import os
import re
import subprocess
import time
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.logger import get_logger

logger = get_logger("Serenada")


class AppLauncher:
    WORD_ALIASES = {
        "телеграм": "telegram",
        "телега": "telegram",
        "стим": "steam",
        "яндекс": "yandex",
        "музыка": "music",
        "браузер": "chrome",
    }

    PHRASE_ALIASES = {
        "яндекс музыка": "yandex music",
        "yandex музыка": "yandex music",
        "epic games": "epicgameslauncher",
        "epic games launcher": "epicgameslauncher",
    }

    BAD_STEM_WORDS = ["installer", "setup", "unins", "uninstall", "update", "updater"]

    EXCLUDE_DIR_PATTERNS = [
        r"\\Windows\\",
        r"\\Windows$",
        r"\\WinSxS\\",
        r"\\ProgramData\\Microsoft\\Windows\\",
        r"\\AppData\\Local\\Microsoft\\Windows\\",
        r"\\$Recycle\.Bin\\",
        r"\\System Volume Information\\",
    ]

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        cache_filename: str = "apps_index.json",
        cache_ttl_hours: int = 72,
        scan_all_drives: bool = True,
        max_items: int = 120000,
    ):
        self.base_dir = base_dir or (Path.home() / "SerenadaData")
        self.cache_path = self.base_dir / cache_filename
        self.cache_ttl_sec = max(1, cache_ttl_hours) * 3600
        self.scan_all_drives = scan_all_drives
        self.max_items = max_items

        self._exclude_rx = [re.compile(p, re.IGNORECASE) for p in self.EXCLUDE_DIR_PATTERNS]
        self._index_lock = threading.Lock()
        self._exe_index: Optional[Dict[str, str]] = None

    def warm_up(self) -> None:
        with self._index_lock:
            if self._exe_index is None:
                self._exe_index = self._load_or_build_index()

    def rebuild_index(self) -> None:
        with self._index_lock:
            self._exe_index = self._build_index()
            self._save_cache(self._exe_index)

    def launch(self, name: str) -> Tuple[bool, str]:
        name = (name or "").strip().lower()
        if not name:
            return False, ""

        name = self.PHRASE_ALIASES.get(name, name)
        name = self._normalize_phrase_alias_words(name)

        key_no_space = name.replace(" ", "")
        if len(key_no_space) < 3:
            return False, name

        path = self._where_find(key_no_space)
        if path:
            return self._spawn(path, used_name=name)

        path = self._registry_app_paths(key_no_space)
        if path:
            return self._spawn(path, used_name=name)

        self.warm_up()
        assert self._exe_index is not None

        if key_no_space in self._exe_index:
            # Иногда точное совпадение ведёт на установщик. Если похоже на installer/setup — ищем дальше.
            p = self._exe_index[key_no_space]
            bn = os.path.basename(p).lower()
            if not any(w in bn for w in self.BAD_STEM_WORDS):
                return self._spawn(p, used_name=name)

        key_tokens = self._tokens(name)
        candidates = []
        for stem, p in self._exe_index.items():
            stem_tokens = self._split_tokens(stem)
            if all(t in stem_tokens for t in key_tokens):
                candidates.append((stem, p))

        if candidates:
            candidates.sort(key=self._score_candidate)
            return self._spawn(candidates[0][1], used_name=name)

        candidates = [(stem, p) for stem, p in self._exe_index.items() if stem.startswith(key_no_space)]
        if candidates:
            candidates.sort(key=self._score_candidate)
            return self._spawn(candidates[0][1], used_name=name)

        return False, name

    def launch_target(self, target: str) -> bool:
        target = (target or "").strip()
        if not target:
            return False

        if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
            target = target[1:-1].strip()

        try:
            tl = target.lower()
            if tl.startswith("shell:") or "appsfolder" in tl or tl.startswith(("ms-", "app:")):
                subprocess.Popen(["explorer.exe", target], shell=False)
                return True

            if os.path.exists(target):
                subprocess.Popen([target], shell=False)
                return True

            subprocess.Popen(["explorer.exe", target], shell=False)
            return True

        except Exception as e:
            logger.warning("launch_target error: %s", e)
            return False

    def is_process_running(self, target_or_name: str) -> bool:
        s = (target_or_name or "").strip()
        if not s:
            return False

        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()

        name = s
        if "\\" in s or "/" in s:
            name = os.path.basename(s)

        name = name.strip()
        if not name.lower().endswith(".exe"):
            name = name + ".exe"

        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}"],
                capture_output=True, text=True, timeout=2
            ).stdout.lower()
            return name.lower() in out
        except Exception:
            return False

    # ---------- internals ----------
    def _spawn(self, path: str, used_name: str) -> Tuple[bool, str]:
        try:
            subprocess.Popen([path], shell=False)
            logger.info("Launch OK: %s", path)
            return True, used_name
        except Exception as e:
            logger.exception("Launch failed: %s", e)
            return False, used_name

    def _normalize_phrase_alias_words(self, phrase: str) -> str:
        parts = re.split(r"\s+", phrase.strip().lower())
        mapped = [self.WORD_ALIASES.get(p, p) for p in parts if p]
        return " ".join(mapped).strip()

    def _tokens(self, phrase: str) -> List[str]:
        phrase = phrase.lower().strip()
        parts = re.split(r"[^a-zа-я0-9]+", phrase, flags=re.IGNORECASE)
        parts = [p for p in parts if p]
        out = [self.WORD_ALIASES.get(p, p) for p in parts]
        out = [t for t in out if len(t) >= 2]
        return out

    def _score_candidate(self, item: Tuple[str, str]) -> Tuple[int, int, str]:
        stem, _ = item
        bad = 0
        s = stem.lower()
        for w in self.BAD_STEM_WORDS:
            if w in s:
                bad += 10
        return (bad, len(stem), stem)

    def _where_find(self, key: str) -> Optional[str]:
        try:
            p = subprocess.run(["where", key], capture_output=True, text=True, timeout=2)
            if p.returncode == 0 and p.stdout.strip():
                first = p.stdout.strip().splitlines()[0].strip()
                if first.lower().endswith(".exe"):
                    return first
        except Exception:
            return None
        return None

    def _registry_app_paths(self, key: str) -> Optional[str]:
        try:
            import winreg  # type: ignore
        except Exception:
            return None

        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]
        exe_name = key if key.endswith(".exe") else f"{key}.exe"

        for root, base in roots:
            try:
                with winreg.OpenKey(root, base + "\\" + exe_name) as k:
                    value, _ = winreg.QueryValueEx(k, "")
                    if value and str(value).lower().endswith(".exe"):
                        return str(value)
            except Exception:
                continue
        return None

    def _load_or_build_index(self) -> Dict[str, str]:
        cached = self._load_cache_if_fresh()
        if cached is not None:
            logger.info("EXE index loaded from cache: %d items", len(cached))
            return cached

        idx = self._build_index()
        self._save_cache(idx)
        return idx

    def _load_cache_if_fresh(self) -> Optional[Dict[str, str]]:
        try:
            if not self.cache_path.exists():
                return None
            age = time.time() - self.cache_path.stat().st_mtime
            if age > self.cache_ttl_sec:
                return None
            with self.cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                out = {}
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str) and v.lower().endswith(".exe"):
                        out[k] = v
                return out
        except Exception:
            return None
        return None

    def _save_cache(self, index: Dict[str, str]) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
            logger.info("EXE index saved: %s", str(self.cache_path))
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)

    def _build_index(self) -> Dict[str, str]:
        logger.info("Building EXE index...")

        dirs = self._get_scan_dirs()
        index: Dict[str, str] = {}

        for base in dirs:
            if not base.exists():
                continue
            for exe_path in self._walk_exe_files(base):
                stem = exe_path.stem.lower()
                # Не индексируем установщики/апдейтеры: они ломают выбор приложений (Epic Games и т.п.)
                if any(w in stem for w in self.BAD_STEM_WORDS):
                    continue
                index.setdefault(stem, str(exe_path))
                if len(index) >= self.max_items:
                    logger.warning("Index max items reached (%d). Stop scan.", self.max_items)
                    break
            if len(index) >= self.max_items:
                break

        logger.info("EXE index built: %d items", len(index))
        return index

    def _get_scan_dirs(self) -> List[Path]:
        user = Path.home()
        dirs: List[Path] = [
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
            user / "AppData" / "Roaming",
            user / "AppData" / "Local",
        ]

        if self.scan_all_drives:
            for d in self._list_drives():
                dirs.append(Path(d))

        uniq = []
        seen = set()
        for p in dirs:
            ps = str(p).lower()
            if ps not in seen:
                seen.add(ps)
                uniq.append(p)
        return uniq

    def _list_drives(self) -> List[str]:
        drives = []
        try:
            import string
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i, letter in enumerate(string.ascii_uppercase):
                if bitmask & (1 << i):
                    root = f"{letter}:\\"
                    if os.path.exists(root):
                        drives.append(root)
        except Exception:
            for letter in ["C", "D", "E"]:
                root = f"{letter}:\\"
                if os.path.exists(root):
                    drives.append(root)
        return drives

    def _is_excluded_dir(self, path_str: str) -> bool:
        for rx in self._exclude_rx:
            if rx.search(path_str):
                return True
        return False

    def _walk_exe_files(self, base: Path) -> Iterable[Path]:
        base_str = str(base)
        for root, dirs, files in os.walk(base_str):
            if self._is_excluded_dir(root):
                dirs[:] = []
                continue

            pruned = []
            for d in dirs:
                full = os.path.join(root, d)
                if self._is_excluded_dir(full):
                    continue
                pruned.append(d)
            dirs[:] = pruned

            for fn in files:
                if fn.lower().endswith(".exe"):
                    yield Path(root) / fn

    def _split_tokens(self, stem: str) -> List[str]:
        parts = re.split(r"[^a-z0-9]+", stem.lower())
        return [p for p in parts if p]