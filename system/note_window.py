from __future__ import annotations

import queue
import threading
from typing import Optional

from core.logger import get_logger

logger = get_logger("Serenada")

_cmd_q: "queue.Queue[tuple]" = queue.Queue()
_thread: Optional[threading.Thread] = None


def _gui_thread():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()

    state = {"win": None, "text": None, "title": None}

    def do_show(title: str, content: str):
        if state["win"] is not None:
            try:
                state["win"].destroy()
            except Exception:
                pass
            state["win"] = None

        win = tk.Toplevel(root)
        win.title(f"Заметка: {title}")
        win.geometry("520x360")
        win.attributes("-topmost", True)

        lbl = tk.Label(win, text=f"Заметка: {title}", font=("Segoe UI", 12, "bold"))
        lbl.pack(padx=10, pady=8, anchor="w")

        txt = tk.Text(win, wrap="word", font=("Segoe UI", 11))
        txt.pack(padx=10, pady=8, fill="both", expand=True)
        txt.insert("1.0", content)
        txt.configure(state="disabled")

        btn = tk.Button(win, text="Закрыть", command=win.destroy)
        btn.pack(padx=10, pady=10, anchor="e")

        state["win"] = win
        state["text"] = txt
        state["title"] = title

        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass

    def do_close():
        if state["win"] is not None:
            try:
                state["win"].destroy()
            except Exception:
                pass
            state["win"] = None
            state["text"] = None
            state["title"] = None

    def poll():
        try:
            while True:
                cmd = _cmd_q.get_nowait()
                if not cmd:
                    continue
                if cmd[0] == "show":
                    _, title, content = cmd
                    do_show(title, content)
                elif cmd[0] == "close":
                    do_close()
        except queue.Empty:
            pass
        root.after(120, poll)

    poll()
    root.mainloop()


def _ensure_thread():
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_gui_thread, daemon=True)
    _thread.start()


def show_note_window(title: str, content: str) -> None:
    _ensure_thread()
    _cmd_q.put(("show", title, content))


def close_note_window() -> None:
    _ensure_thread()
    _cmd_q.put(("close",))