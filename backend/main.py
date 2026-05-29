from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import ComposeVideoRequest, PipelineStartRequest, RevisionRequest
from backend.services.pipeline_service import get_runtime_status, run_revision, start_pipeline
from backend.services.publish_service import publish_background
from backend.services.state_service import (
    OUTPUT_DIR,
    clear_pipeline_state,
    load_pipeline_state,
    state_for_api,
)
from backend.services.video_service import compose_video_background
from tools.progress import get as get_progress, reset as reset_progress


UPLOAD_DIR = ROOT_DIR / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Science Animation Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=str(OUTPUT_DIR)), name="media")


def api_state():
    status = get_runtime_status()
    return {
        "state": state_for_api(load_pipeline_state()),
        "running": status.running,
        "status_message": status.status_message,
        "error": status.error,
    }


@app.get("/api/state")
def get_state():
    return api_state()


@app.get("/api/progress")
def progress():
    return get_progress()


@app.post("/api/pipeline/start")
def pipeline_start(request: PipelineStartRequest):
    try:
        start_pipeline(request)
        return api_state()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    target = UPLOAD_DIR / Path(file.filename).name
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return {"path": str(target.resolve()), "filename": target.name}


@app.post("/api/revision")
def revision(request: RevisionRequest):
    try:
        run_revision(request.revision_text)
        return api_state()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/video/compose")
def compose_video(request: ComposeVideoRequest):
    try:
        compose_video_background(request.subtitle_enabled, request.subtitle_language)
        return api_state()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/publish")
def publish():
    try:
        publish_background()
        return api_state()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/clear")
def clear():
    clear_pipeline_state()
    reset_progress()
    return api_state()
