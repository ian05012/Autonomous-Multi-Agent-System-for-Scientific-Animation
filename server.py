"""
server.py
---------
Flask backend for AXION Science Animation Studio.
Serves the static frontend and provides REST API for pipeline control.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

_ROOT = str(Path(__file__).parent.resolve())
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(Path(_ROOT) / ".env")

from flask import Flask, jsonify, request, send_from_directory, send_file
from state import load_state, save_state, make_initial_state

app = Flask(__name__, static_folder="frontend", static_url_path="")

STATE_PATH = "output/state.json"

MODEL_TIERS = {
    "paid": {
        "base_url": "",
        "llm_model": os.getenv("LLM_MODEL", "gpt-5"),
        "animator_model": os.getenv("ANIMATOR_MODEL", "gpt-5.1-codex"),
        "api_key_env": "OPENAI_API_KEY",
    },
    "free": {
        "base_url": "https://openrouter.ai/api/v1",
        "llm_model": "openai/gpt-oss-20b:free",
        "animator_model": "openai/gpt-oss-120b:free",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}


def _apply_model_tier(tier: str) -> None:
    cfg = MODEL_TIERS.get(tier, MODEL_TIERS["paid"])
    api_key = os.getenv(cfg["api_key_env"], "")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    if cfg["base_url"]:
        os.environ["OPENAI_BASE_URL"] = cfg["base_url"]
    else:
        os.environ.pop("OPENAI_BASE_URL", None)
    os.environ["LLM_MODEL"] = cfg["llm_model"]
    os.environ["ANIMATOR_MODEL"] = cfg["animator_model"]


# ─── Static serving ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/result")
def result():
    return send_from_directory("frontend", "result.html")


# ─── API: State & Progress ────────────────────────────────────────────────────

@app.route("/api/state")
def api_state():
    state = load_state(STATE_PATH)
    if state is None:
        return jsonify({"status": "empty"})
    return jsonify({
        "status": "ok",
        "storyboard": state.get("storyboard", []),
        "audio_count": len(state.get("audio_files", [])),
        "video_count": len(state.get("video_clips", [])),
        "has_video_clips": bool(state.get("video_clips")),
        "final_video_path": state.get("final_video_path"),
        "error_log": state.get("error_log", []),
    })


@app.route("/api/progress")
def api_progress():
    try:
        from tools.progress import get as _get
        return jsonify(_get())
    except Exception:
        return jsonify({"pct": 0, "stage": "", "detail": "", "running": False, "done": False})


# ─── API: Generate ────────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json() or {}
    source_type = data.get("source_type", "text")
    input_text = data.get("input_text", "")
    input_path = data.get("input_path") or None
    model_tier = data.get("model_tier", "paid")
    tts_language = data.get("tts_language", "en-US")
    subtitle_enabled = data.get("subtitle_enabled", True)
    subtitle_language = data.get("subtitle_language", "zh-TW")

    if not input_text.strip():
        return jsonify({"error": "No input provided"}), 400

    _apply_model_tier(model_tier)
    os.environ["GOOGLE_TTS_LANGUAGE"] = tts_language
    os.environ["SUBTITLE_ENABLED"] = "true" if subtitle_enabled else "false"
    os.environ["SUBTITLE_LANGUAGE"] = subtitle_language

    def run():
        from agents.supervisor import run_pipeline
        try:
            run_pipeline(input_text, source_type, input_path)
        except Exception as exc:
            from tools.progress import error as _perr
            _perr(str(exc))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    os.makedirs("output", exist_ok=True)
    save_path = os.path.join("output", f.filename)
    f.save(save_path)
    return jsonify({"path": save_path, "name": f.filename})


# ─── API: Compose ─────────────────────────────────────────────────────────────

@app.route("/api/compose", methods=["POST"])
def api_compose():
    data = request.get_json() or {}
    subtitle_enabled = data.get("subtitle_enabled", True)
    subtitle_language = data.get("subtitle_language", "zh-TW")

    state = load_state(STATE_PATH)
    if not state or not state.get("video_clips"):
        return jsonify({"error": "No video clips available"}), 400

    os.environ["SUBTITLE_LANGUAGE"] = subtitle_language
    os.environ["SUBTITLE_ENABLED"] = "true" if subtitle_enabled else "false"

    def run():
        from tools.ffmpeg_composer import compose_video
        from tools.progress import update as _prog, finish as _finish, reset as _reset
        _reset()
        try:
            subtitle_path = None
            if subtitle_enabled and state.get("storyboard") and state.get("audio_files"):
                from tools.subtitle_generator import generate_srt
                _prog(20, "Subtitles", f"Generating subtitles ({subtitle_language})...")
                try:
                    subtitle_path = generate_srt(
                        storyboard=state["storyboard"],
                        audio_files=state["audio_files"],
                        output_path="output/subtitles.srt",
                    )
                except Exception as e:
                    print(f"[Subtitles] WARNING: {e}")
            _prog(70, "Composer", "Composing final video...")
            final_path = compose_video(
                audio_files=state.get("audio_files", []),
                video_clips=state.get("video_clips", []),
                subtitle_path=subtitle_path,
            )
            _finish("Video ready!")
            new_state = {**state, "final_video_path": final_path}
            save_state(new_state)
        except Exception as exc:
            from tools.progress import error as _perr
            _perr(str(exc))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


# ─── API: Video ───────────────────────────────────────────────────────────────

@app.route("/api/video")
def api_video():
    state = load_state(STATE_PATH)
    if not state or not state.get("final_video_path"):
        return jsonify({"error": "No video"}), 404
    video_path = Path(state["final_video_path"])
    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404
    return send_file(str(video_path), mimetype="video/mp4")


# ─── API: Clear ───────────────────────────────────────────────────────────────

@app.route("/api/clear", methods=["POST"])
def api_clear():
    if Path(STATE_PATH).exists():
        Path(STATE_PATH).unlink()
    try:
        from tools.progress import reset as _reset
        _reset()
    except Exception:
        pass
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    print("AXION Science Animation Studio")
    print("Server running at http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
