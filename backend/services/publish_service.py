from __future__ import annotations

import threading

from backend.services.pipeline_service import _set_status, ensure_not_running
from backend.services.state_service import load_pipeline_state, save_pipeline_state


_worker: threading.Thread | None = None


def publish_background():
    global _worker
    ensure_not_running()
    state = load_pipeline_state()
    if state is None:
        raise RuntimeError("No pipeline state found. Generate an animation first.")

    _set_status(running=True, status_message="Publishing to social media...", error="")

    def run() -> None:
        from agents.social_media import social_media_node
        from tools.progress import error as progress_error, finish, reset, update

        reset()
        update(10, "Publish", "Preparing social metadata...")
        try:
            updates = social_media_node(state)
            new_state = {**state, **updates}
            save_pipeline_state(new_state)  # type: ignore[arg-type]
            finish("Published")
            yt = updates.get("youtube_url")
            ig = updates.get("instagram_url")
            channels = ", ".join(v for v in [yt, ig] if v)
            suffix = f" {channels}" if channels else ""
            _set_status(running=False, status_message=f"Publish complete.{suffix}", error="")
        except Exception as exc:
            message = f"Publish error: {exc}"
            progress_error(str(exc))
            _set_status(running=False, status_message=message, error=message)

    _worker = threading.Thread(target=run, daemon=True)
    _worker.start()
    return load_pipeline_state()
