from __future__ import annotations

import os
import threading

from backend.services.pipeline_service import _set_status, ensure_not_running
from backend.services.state_service import load_pipeline_state, save_pipeline_state


_worker: threading.Thread | None = None


def compose_video_background(subtitle_enabled: bool, subtitle_language: str):
    global _worker
    ensure_not_running()
    state = load_pipeline_state()
    if state is None:
        raise RuntimeError("No pipeline state found. Generate an animation first.")

    _set_status(running=True, status_message="Composing video...", error="")

    def run() -> None:
        from tools import subtitle_generator
        from tools.ffmpeg_composer import compose_video
        from tools.progress import error as progress_error, finish, reset, update

        reset()
        os.environ["SUBTITLE_ENABLED"] = "true" if subtitle_enabled else "false"
        os.environ["SUBTITLE_LANGUAGE"] = subtitle_language
        subtitle_generator.SUBTITLE_LANGUAGE = subtitle_language
        subtitle_generator.SUBTITLE_ENABLED = subtitle_enabled

        try:
            subtitle_path = None
            if subtitle_enabled and state.get("storyboard") and state.get("audio_files"):
                update(20, "Subtitles", f"Translating to {subtitle_language}...")
                try:
                    subtitle_path = subtitle_generator.generate_srt(
                        storyboard=state["storyboard"],
                        audio_files=state["audio_files"],
                        output_path="output/subtitles.srt",
                    )
                except Exception as exc:
                    update(35, "Subtitles", f"Subtitle generation skipped: {exc}")

            update(70, "Composer", "Composing final video...")
            final_path = compose_video(
                audio_files=state.get("audio_files", []),
                video_clips=state.get("video_clips", []),
                subtitle_path=subtitle_path,
            )
            new_state = {**state, "final_video_path": final_path}
            save_pipeline_state(new_state)  # type: ignore[arg-type]
            finish("Video ready!")
            _set_status(running=False, status_message="Video composed successfully.", error="")
        except Exception as exc:
            message = f"Composition error: {exc}"
            progress_error(str(exc))
            _set_status(running=False, status_message=message, error=message)

    _worker = threading.Thread(target=run, daemon=True)
    _worker.start()
    return load_pipeline_state()
