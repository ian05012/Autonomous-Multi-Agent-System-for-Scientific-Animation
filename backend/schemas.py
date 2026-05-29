from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SourceType = Literal["text", "pdf", "url"]
ModelTier = Literal["paid", "free"]


class PipelineStartRequest(BaseModel):
    source_type: SourceType
    input_value: str = Field(min_length=1)
    model_tier: ModelTier = "paid"
    tts_language: str = "en-US"
    subtitle_enabled: bool = True
    subtitle_language: str = "zh-TW"


class RevisionRequest(BaseModel):
    revision_text: str = Field(min_length=1)


class ComposeVideoRequest(BaseModel):
    subtitle_enabled: bool = True
    subtitle_language: str = "zh-TW"


class StateResponse(BaseModel):
    state: dict[str, Any] | None
    running: bool
    status_message: str = ""
    error: str = ""


class UploadResponse(BaseModel):
    path: str
    filename: str


class ProgressResponse(BaseModel):
    running: bool = False
    pct: int = 0
    stage: str = ""
    detail: str = ""
    done: bool = False
    error: str = ""
    logs: list[dict[str, Any]] = []
