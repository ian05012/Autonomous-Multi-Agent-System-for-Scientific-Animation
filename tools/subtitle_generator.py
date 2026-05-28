"""
tools/subtitle_generator.py
-----------------------------
Generates SRT subtitle files from storyboard narrations + audio timing.

Subtitle language and TTS language are configured independently:
  SUBTITLE_ENABLED=true
  SUBTITLE_LANGUAGE=zh-TW   # e.g. en, zh-TW, zh-CN, ja, ko, es, fr
  # TTS speech language is controlled by GOOGLE_TTS_LANGUAGE

If SUBTITLE_LANGUAGE differs from the narration language, the text is
translated using the LLM configured in LLM_MODEL.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from state import AudioMeta, SceneSpec

def _subtitle_enabled() -> bool:
    return os.getenv("SUBTITLE_ENABLED", "true").lower() == "true"

def _subtitle_language() -> str:
    return os.getenv("SUBTITLE_LANGUAGE", "en")

SUBTITLE_ENABLED = _subtitle_enabled()
SUBTITLE_LANGUAGE = _subtitle_language()
def _llm_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o")

LANGUAGE_NAMES = {
    "en": "English",
    "zh-TW": "Traditional Chinese",
    "zh-CN": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ar": "Arabic",
}


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _translate_texts(texts: list[str], target_language: str) -> list[str]:
    """Translate a list of narration texts to the target language using LLM."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    lang_name = LANGUAGE_NAMES.get(target_language, target_language)
    llm = ChatOpenAI(model=_llm_model(), temperature=0)

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    system = SystemMessage(content=(
        f"You are a professional subtitle translator. "
        f"Translate the following numbered lines to {lang_name}. "
        f"Return ONLY the translated lines in the same numbered format. "
        f"Keep each translation concise (suitable for subtitles). "
        f"Preserve the original meaning and tone."
    ))
    human = HumanMessage(content=numbered)
    response = llm.invoke([system, human])

    translated_lines: list[str] = []
    for line in response.content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip leading "1. ", "2. " etc.
        if line and line[0].isdigit():
            dot_idx = line.find(".")
            if dot_idx != -1 and dot_idx < 4:
                line = line[dot_idx + 1:].strip()
        translated_lines.append(line)

    # Fallback: if translation count doesn't match, return originals
    if len(translated_lines) != len(texts):
        return texts

    return translated_lines


def generate_srt(
    storyboard: list["SceneSpec"],
    audio_files: list["AudioMeta"],
    output_path: str,
    narration_language: str = "en",
) -> str:
    """
    Generate a .srt subtitle file from storyboard narrations and audio timings.

    Args:
        storyboard:         List of SceneSpecs with narration text.
        audio_files:        List of AudioMeta with duration_seconds per scene.
        output_path:        Where to write the .srt file.
        narration_language: Language of the original narration (e.g. "en").

    Returns:
        Path to the generated .srt file.
    """
    audio_by_scene = {a["scene_id"]: a for a in audio_files}

    # Collect scenes that have audio
    scenes_with_audio = [
        s for s in sorted(storyboard, key=lambda x: x["scene_id"])
        if s["scene_id"] in audio_by_scene
    ]

    narrations = [s["narration"] for s in scenes_with_audio]

    # Translate if needed
    target_lang = SUBTITLE_LANGUAGE
    if target_lang.lower() != narration_language.lower() and target_lang.lower() != "en" or \
       (narration_language.lower() != target_lang.lower()):
        # Only translate if languages differ
        if target_lang.lower() == narration_language.lower():
            texts = narrations
        else:
            print(f"  [Subtitles] Translating {len(narrations)} lines to {target_lang}...")
            try:
                texts = _translate_texts(narrations, target_lang)
            except Exception as exc:
                print(f"  [Subtitles] Translation failed ({exc}), using original text.")
                texts = narrations
    else:
        texts = narrations

    # Build SRT content
    srt_lines: list[str] = []
    current_time = 0.0

    for idx, (scene, text) in enumerate(zip(scenes_with_audio, texts), start=1):
        audio = audio_by_scene[scene["scene_id"]]
        duration = audio["duration_seconds"]

        start_ts = _seconds_to_srt_time(current_time)
        end_ts = _seconds_to_srt_time(current_time + duration)

        srt_lines.append(str(idx))
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(text)
        srt_lines.append("")

        current_time += duration

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(srt_lines), encoding="utf-8")
    print(f"  [Subtitles] Written {len(scenes_with_audio)} subtitle entries → {output_path}")
    return output_path
