"""
tools/progress.py
-----------------
Shared in-process progress tracker for the pipeline.

Background threads call update() to report progress.
The Streamlit UI reads the current state via get().
"""

from __future__ import annotations
import threading

_lock = threading.Lock()

_state: dict = {
    "running": False,
    "pct": 0,           # 0-100
    "stage": "",        # e.g. "Scriptwriter"
    "detail": "",       # e.g. "Synthesizing scene 3/9"
    "done": False,
    "error": "",
}


def update(pct: int, stage: str, detail: str = "") -> None:
    with _lock:
        _state["running"] = True
        _state["pct"] = max(0, min(100, pct))
        _state["stage"] = stage
        _state["detail"] = detail
        _state["done"] = False
        _state["error"] = ""


def finish(msg: str = "Done!") -> None:
    with _lock:
        _state["running"] = False
        _state["pct"] = 100
        _state["stage"] = msg
        _state["detail"] = ""
        _state["done"] = True
        _state["error"] = ""


def error(msg: str) -> None:
    with _lock:
        _state["running"] = False
        _state["stage"] = "Error"
        _state["detail"] = msg
        _state["error"] = msg
        _state["done"] = False


def reset() -> None:
    with _lock:
        _state.update({"running": False, "pct": 0, "stage": "", "detail": "", "done": False, "error": ""})


def get() -> dict:
    with _lock:
        return dict(_state)
