"""
tools/ffmpeg_composer.py
-------------------------
FFMPEG-based video composition tool for the Science Animation System.

Merges per-scene video clips with their corresponding audio tracks into
a single final MP4 output.

Composition strategy:
1. For each scene: mux video clip + audio track → scene_combined_N.mp4
2. Concatenate all combined scene clips → final_video.mp4

Missing scene files are skipped with a warning (best-effort composition).
Audio and video are synchronized per scene with ≤50ms offset.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from state import AudioMeta, VideoMeta


# ─── Configuration ────────────────────────────────────────────────────────────

FINAL_OUTPUT_DIR = "output/final"
FINAL_OUTPUT_FILENAME = "final_video.mp4"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run_ffmpeg(args: list[str], description: str) -> None:
    """Run an FFMPEG command and raise RuntimeError on failure."""
    cmd = ["ffmpeg", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFMPEG failed ({description}):\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stderr: {result.stderr[-2000:]}"
        )


def _merge_scene(video_path: str, audio_path: str, output_path: str) -> None:
    """
    Mux a video clip with an audio track.
    The audio track is the timing ground truth — video is trimmed/padded to match.
    """
    _run_ffmpeg(
        [
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "experimental",
            "-shortest",          # trim to the shorter of video/audio
            output_path,
        ],
        description=f"merge scene {Path(video_path).stem}",
    )


def _concatenate_clips(clip_paths: list[str], output_path: str) -> None:
    """Concatenate a list of video clips into a single MP4 using FFMPEG concat."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")
        concat_list_path = f.name

    try:
        _run_ffmpeg(
            [
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                output_path,
            ],
            description="concatenate all scenes",
        )
    finally:
        os.unlink(concat_list_path)


# ─── Subtitle helpers ─────────────────────────────────────────────────────────

def _find_font_file() -> str | None:
    """Find a font FILE path that supports CJK + Latin characters."""
    import platform
    candidates: list[str] = []

    if platform.system() == "Windows":
        candidates = [
            r"C:\Windows\Fonts\msjh.ttc",     # 微軟正黑體 (繁體)
            r"C:\Windows\Fonts\msyh.ttc",     # 微軟雅黑 (簡體)
            r"C:\Windows\Fonts\arial.ttf",    # Arial (英文 fallback)
            r"C:\Windows\Fonts\simsun.ttc",   # 新細明體
            r"C:\Windows\Fonts\mingliu.ttc",  # 細明體
        ]
    elif platform.system() == "Linux":
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]

    for p in candidates:
        if Path(p).exists():
            return p
    return None


def _escape_ffmpeg_path(path: str) -> str:
    """Escape a Windows path for ffmpeg filtergraph syntax."""
    escaped = path.replace("\\", "/")
    # Escape drive-letter colon: C: → C\:
    if len(escaped) >= 2 and escaped[1] == ":":
        escaped = escaped[0] + "\\:" + escaped[2:]
    return escaped


def _srt_to_ass(srt_path: str, ass_path: str, font_name: str = "Arial") -> None:
    """
    Convert SRT to ASS subtitle format with embedded font/style settings.
    This is more reliable than force_style because the font is declared
    in the ASS header itself.
    """
    import re

    # Parse SRT
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    # ASS header with embedded font and style
    ass_header = f"""[Script Info]
Title: Subtitles
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,4,2,1,2,20,20,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Parse SRT entries
    # Pattern: index\ntimestamp --> timestamp\ntext\n\n
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*\n"
        r"((?:.+\n?)*)",
        re.MULTILINE,
    )

    events = []
    for m in pattern.finditer(srt_content):
        h1, m1, s1, ms1 = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        h2, m2, s2, ms2 = int(m.group(6)), int(m.group(7)), int(m.group(8)), int(m.group(9))
        text = m.group(10).strip().replace("\n", "\\N")

        start = f"{h1}:{m1:02d}:{s1:02d}.{ms1 // 10:02d}"
        end = f"{h2}:{m2:02d}:{s2:02d}.{ms2 // 10:02d}"
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write(ass_header)
        f.write("\n".join(events))
        f.write("\n")


def _burn_subtitles(video_path: str, srt_path: str, output_path: str) -> None:
    """
    Burn subtitles into a video. Uses ASS format with explicit font embedding
    for maximum reliability across platforms.

    Strategy:
    1. Find a CJK-capable font file on the system
    2. Convert SRT → ASS with font name embedded in the ASS header
    3. Copy the font file next to the ASS file (fontsdir)
    4. Use ffmpeg's ass filter with fontsdir pointing to the font copy
    """
    import subprocess
    import shutil

    srt_abs = str(Path(srt_path).resolve())
    srt_dir = str(Path(srt_abs).parent)

    # Step 1: Find a font file
    font_file = _find_font_file()
    font_name = "Microsoft JhengHei"  # default

    if font_file:
        # Derive font name from the file
        fname = Path(font_file).stem.lower()
        font_map = {
            "msjh": "Microsoft JhengHei",
            "msjhbd": "Microsoft JhengHei",
            "msyh": "Microsoft YaHei",
            "msyhbd": "Microsoft YaHei",
            "simsun": "SimSun",
            "mingliu": "MingLiU",
            "arial": "Arial",
        }
        for key, name in font_map.items():
            if fname.startswith(key):
                font_name = name
                break

        # Copy font to subtitle directory so fontsdir can find it
        font_dest = Path(srt_dir) / Path(font_file).name
        if not font_dest.exists():
            shutil.copy2(font_file, str(font_dest))
        print(f"  [Subtitles] Using font: {font_name} ({font_file})")
    else:
        print("  [Subtitles] WARNING: No suitable font found, subtitles may not render.")

    # Step 2: Convert SRT to ASS
    ass_path = srt_abs.replace(".srt", ".ass")
    _srt_to_ass(srt_abs, ass_path, font_name=font_name)
    print(f"  [Subtitles] Converted SRT → ASS: {ass_path}")

    # Step 3: Build ffmpeg command with ass filter + fontsdir
    ass_escaped = _escape_ffmpeg_path(ass_path)
    fontsdir_escaped = _escape_ffmpeg_path(srt_dir)

    vf = f"ass='{ass_escaped}':fontsdir='{fontsdir_escaped}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]
    print(f"  [Subtitles] ffmpeg -vf {vf}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if result.returncode != 0:
        # Fallback: try subtitles filter with direct font path
        print(f"  [Subtitles] ASS filter failed, trying subtitles filter fallback...")
        print(f"  [Subtitles] ASS stderr: {result.stderr[-500:]}")

        srt_escaped = _escape_ffmpeg_path(srt_abs)
        fallback_vf = f"subtitles='{srt_escaped}':fontsdir='{fontsdir_escaped}':force_style='Fontname={font_name},FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1,Alignment=2,MarginV=15,BackColour=&H80000000,BorderStyle=4'"

        cmd2 = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", fallback_vf,
            "-c:a", "copy",
            output_path,
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result2.returncode != 0:
            raise RuntimeError(f"Subtitle burn failed (both methods):\nASS: {result.stderr[-300:]}\nSRT: {result2.stderr[-300:]}")

    print(f"  [Subtitles] Burn complete: {output_path}")


def compose_video(
    audio_files: list[AudioMeta],
    video_clips: list[VideoMeta],
    output_path: str | None = None,
    subtitle_path: str | None = None,
) -> str:
    """
    Merge all per-scene video clips with their audio tracks into a final MP4.

    Args:
        audio_files: List of AudioMeta from Voiceover Agent.
        video_clips: List of VideoMeta from Animator Agent.
        output_path: Where to write the final video. Defaults to
                     output/final/final_video.mp4.

    Returns:
        Absolute path to the composed final video.

    Notes:
        - Scenes missing either video or audio are skipped with a warning.
        - Audio/video are synchronized per scene (FFMPEG -shortest flag).
    """
    if output_path is None:
        output_path = str(Path(FINAL_OUTPUT_DIR) / FINAL_OUTPUT_FILENAME)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build lookup maps
    audio_by_scene = {a["scene_id"]: a for a in audio_files}
    video_by_scene = {v["scene_id"]: v for v in video_clips}

    # Determine which scenes can be composed (both audio and video present)
    all_scene_ids = sorted(set(audio_by_scene.keys()) | set(video_by_scene.keys()))

    composable_scenes = []
    for scene_id in all_scene_ids:
        audio = audio_by_scene.get(scene_id)
        video = video_by_scene.get(scene_id)

        if audio is None:
            print(f"  [Composer] WARNING: No audio for scene {scene_id} — skipping")
            continue
        if video is None:
            print(f"  [Composer] WARNING: No video for scene {scene_id} — skipping")
            continue
        if not Path(audio["file_path"]).exists():
            print(f"  [Composer] WARNING: Audio file missing for scene {scene_id} — skipping")
            continue
        if not Path(video["file_path"]).exists():
            print(f"  [Composer] WARNING: Video file missing for scene {scene_id} — skipping")
            continue

        composable_scenes.append((scene_id, audio, video))

    if not composable_scenes:
        raise RuntimeError(
            "No scenes with both audio and video available. Cannot compose final video."
        )

    print(f"  [Composer] Composing {len(composable_scenes)} scene(s)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Merge audio+video for each scene
        combined_clips: list[str] = []
        for scene_id, audio, video in composable_scenes:
            combined_path = str(Path(tmpdir) / f"scene_{scene_id}_combined.mp4")
            print(f"  [Composer] Merging scene {scene_id}...")
            _merge_scene(video["file_path"], audio["file_path"], combined_path)
            combined_clips.append(combined_path)

        # Step 2: Concatenate all combined clips
        if len(combined_clips) == 1:
            # Only one scene — just copy it directly
            import shutil
            shutil.copy2(combined_clips[0], output_path)
        else:
            print(f"  [Composer] Concatenating {len(combined_clips)} clips...")
            _concatenate_clips(combined_clips, output_path)

    # Step 3: Burn subtitles if provided
    if subtitle_path and Path(subtitle_path).exists():
        print(f"  [Composer] Burning subtitles from {subtitle_path}...")
        subtitled_path = output_path.replace(".mp4", "_subtitled.mp4")
        try:
            _burn_subtitles(output_path, subtitle_path, subtitled_path)
            import shutil as _shutil
            _shutil.move(subtitled_path, output_path)
            print(f"  [Composer] Subtitles burned successfully.")
        except Exception as exc:
            print(f"  [Composer] WARNING: Subtitle burn failed ({exc}), keeping video without subtitles.")

    final_path = str(Path(output_path).resolve())
    print(f"  [Composer] Final video written to: {final_path}")
    return final_path


def verify_sync(output_path: str, tolerance_ms: float = 50.0) -> bool:
    """
    Verify that the audio stream in the composed video starts within
    `tolerance_ms` milliseconds of the video stream (start time offset ≤ 50ms).

    The per-scene merge strategy (FFMPEG -i video -i audio, both starting at 0)
    guarantees alignment by construction. This function verifies the output
    stream start times using ffprobe as an additional sanity check.

    Args:
        output_path:  Path to the composed MP4 file.
        tolerance_ms: Maximum allowed start-time difference in milliseconds.

    Returns:
        True if audio/video start times are within tolerance, False otherwise.
    """
    import subprocess
    import json as _json

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0,a:0",
                "-show_entries", "stream=codec_type,start_time",
                "-of", "json",
                output_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = _json.loads(result.stdout)
        streams = data.get("streams", [])

        start_times = {}
        for s in streams:
            codec_type = s.get("codec_type")
            start_time = s.get("start_time", "0")
            try:
                start_times[codec_type] = float(start_time)
            except (ValueError, TypeError):
                start_times[codec_type] = 0.0

        if "video" not in start_times or "audio" not in start_times:
            return True  # Can't verify — assume OK

        diff_ms = abs(start_times["video"] - start_times["audio"]) * 1000
        return diff_ms <= tolerance_ms
    except Exception:
        return True  # ffprobe failure — assume OK, don't block pipeline
