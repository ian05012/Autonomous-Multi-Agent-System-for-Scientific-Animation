from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from backend.schemas import PipelineStartRequest
from backend.services.state_service import initial_state, load_pipeline_state, save_pipeline_state


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


MODEL_TIERS = {
    "paid": {
        "base_url": "",
        "llm_model": "gpt-5",
        "animator_model": "gpt-5.1-codex",
        "api_key_env": "OPENAI_API_KEY",
    },
    "free": {
        "base_url": "https://openrouter.ai/api/v1",
        "llm_model": "openai/gpt-oss-20b:free",
        "animator_model": "openai/gpt-oss-120b:free",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}


@dataclass
class RuntimeStatus:
    running: bool = False
    status_message: str = ""
    error: str = ""


_lock = threading.Lock()
_status = RuntimeStatus()
_worker: threading.Thread | None = None


def _set_status(*, running: bool | None = None, status_message: str | None = None, error: str | None = None) -> None:
    with _lock:
        if running is not None:
            _status.running = running
        if status_message is not None:
            _status.status_message = status_message
        if error is not None:
            _status.error = error


def get_runtime_status() -> RuntimeStatus:
    with _lock:
        return RuntimeStatus(_status.running, _status.status_message, _status.error)


def ensure_not_running() -> None:
    if get_runtime_status().running:
        raise RuntimeError("A pipeline action is already running.")


def apply_model_tier(tier: str) -> None:
    cfg = MODEL_TIERS[tier]
    api_key = os.getenv(cfg["api_key_env"], "")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    if cfg["base_url"]:
        os.environ["OPENAI_BASE_URL"] = cfg["base_url"]
    else:
        os.environ.pop("OPENAI_BASE_URL", None)
    os.environ["LLM_MODEL"] = cfg["llm_model"]
    os.environ["ANIMATOR_MODEL"] = cfg["animator_model"]


def start_pipeline(request: PipelineStartRequest):
    global _worker
    ensure_not_running()
    apply_model_tier(request.model_tier)
    os.environ["GOOGLE_TTS_LANGUAGE"] = request.tts_language
    os.environ["SUBTITLE_ENABLED"] = "true" if request.subtitle_enabled else "false"
    os.environ["SUBTITLE_LANGUAGE"] = request.subtitle_language

    input_path = request.input_value if request.source_type in ("pdf", "url") else None
    state = initial_state(request.input_value, request.source_type, input_path)
    save_pipeline_state(state)
    _set_status(running=True, status_message="Pipeline starting...", error="")

    def run() -> None:
        from agents.supervisor import run_pipeline
        from tools.progress import error as progress_error

        try:
            final_state = run_pipeline(request.input_value, request.source_type, input_path)
            save_pipeline_state(final_state)
            _set_status(running=False, status_message="Generation complete. Review the draft.", error="")
        except Exception as exc:
            message = f"Pipeline error: {exc}"
            progress_error(str(exc))
            _set_status(running=False, status_message=message, error=message)

    _worker = threading.Thread(target=run, daemon=True)
    _worker.start()
    return load_pipeline_state()


def run_revision(revision_text: str):
    global _worker
    ensure_not_running()
    state = load_pipeline_state()
    if state is None:
        raise RuntimeError("No pipeline state found. Generate an animation first.")

    updated_state = {**state, "hitl_revision": revision_text}
    save_pipeline_state(updated_state)  # type: ignore[arg-type]
    _set_status(running=True, status_message="Processing revision...", error="")

    def run() -> None:
        from agents.supervisor import compile_pipeline
        from tools.progress import error as progress_error, reset, update

        reset()
        update(5, "Revision", "Routing revision...")
        try:
            pipeline = compile_pipeline()
            final_state = pipeline.invoke(updated_state)
            final_state = {**final_state, "hitl_revision": None, "revision_target": None}
            save_pipeline_state(final_state)  # type: ignore[arg-type]
            _set_status(running=False, status_message="Revision applied.", error="")
        except Exception as exc:
            message = f"Revision error: {exc}"
            progress_error(str(exc))
            _set_status(running=False, status_message=message, error=message)

    _worker = threading.Thread(target=run, daemon=True)
    _worker.start()
    return load_pipeline_state()
