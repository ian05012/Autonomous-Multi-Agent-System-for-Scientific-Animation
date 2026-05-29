from __future__ import annotations

from pathlib import Path
from typing import Any

from state import PipelineState, load_state, make_initial_state, save_state


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "output"
STATE_PATH = OUTPUT_DIR / "state.json"


def load_pipeline_state() -> PipelineState | None:
    return load_state(str(STATE_PATH))


def save_pipeline_state(state: PipelineState) -> None:
    save_state(state, str(STATE_PATH))


def clear_pipeline_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()


def initial_state(input_value: str, source_type: str, input_path: str | None = None) -> PipelineState:
    return make_initial_state(input_value, source_type, input_path)  # type: ignore[arg-type]


def state_for_api(state: PipelineState | None) -> dict[str, Any] | None:
    if state is None:
        return None

    data: dict[str, Any] = dict(state)
    final_video_path = data.get("final_video_path")
    data["final_video_url"] = media_url(final_video_path) if final_video_path else None
    return data


def media_url(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    try:
        rel = path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()
