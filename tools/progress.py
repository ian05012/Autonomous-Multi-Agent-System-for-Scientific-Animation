"""
tools/progress.py
-----------------
Shared in-process progress tracker for the pipeline.
Tracks percentage, stage, and a timestamped activity log.
"""

from __future__ import annotations
import threading
import time

_lock = threading.Lock()

_state: dict = {
    "running": False,
    "pct": 0,
    "stage": "",
    "detail": "",
    "done": False,
    "error": "",
    "logs": [],   # list of {t, stage, msg, type}
}

_start_time: float = 0.0


def _ts() -> float:
    return round(time.time() - _start_time, 1) if _start_time else 0.0


def update(pct: int, stage: str, detail: str = "") -> None:
    with _lock:
        _state["running"] = True
        _state["pct"] = max(0, min(100, pct))
        _state["stage"] = stage
        _state["detail"] = detail
        _state["done"] = False
        _state["error"] = ""


def log(msg: str, stage: str = "", kind: str = "info") -> None:
    """Append a log entry visible on the frontend."""
    with _lock:
        _state["logs"].append({
            "t": _ts(),
            "stage": stage or _state.get("stage", ""),
            "msg": msg,
            "kind": kind,   # info | success | error | design | warn
        })
        # keep only last 200 entries
        if len(_state["logs"]) > 200:
            _state["logs"] = _state["logs"][-200:]


def finish(msg: str = "Done!") -> None:
    with _lock:
        _state["running"] = False
        _state["pct"] = 100
        _state["stage"] = msg
        _state["detail"] = ""
        _state["done"] = True
        _state["error"] = ""
    log("Pipeline complete ✓", stage=msg, kind="success")


def error(msg: str) -> None:
    with _lock:
        _state["running"] = False
        _state["stage"] = "Error"
        _state["detail"] = msg
        _state["error"] = msg
        _state["done"] = False
    log(msg, stage="Error", kind="error")


def reset() -> None:
    global _start_time
    _start_time = time.time()
    with _lock:
        _state.update({
            "running": False, "pct": 0, "stage": "", "detail": "",
            "done": False, "error": "", "logs": [],
        })


def get() -> dict:
    with _lock:
        return dict(_state)
