## ADDED Requirements

### Requirement: Merge scene clips and audio into final MP4
The system SHALL use FFMPEG to concatenate all per-scene video clips with their corresponding audio tracks into a single output MP4 file at `output/final/final_video.mp4`.

#### Scenario: Successful composition
- **WHEN** all scene video clips and audio files are present in `output/video/` and `output/audio/`
- **THEN** FFMPEG produces a single MP4 where each scene's video is synchronized with its corresponding audio track, and the total duration equals the sum of all scene audio durations

#### Scenario: Missing scene file
- **WHEN** a scene's video clip or audio file is missing (e.g., due to a render error)
- **THEN** system skips that scene, logs a warning, and composes the remaining scenes into the final video

### Requirement: Audio and video streams are synchronized per scene
The FFMPEG composition command SHALL align each video clip's start time with its corresponding audio track start time, with no gap or overlap exceeding 50ms between consecutive scenes.

#### Scenario: Synchronization accuracy
- **WHEN** final video is composed
- **THEN** the audio track for scene N begins within 50ms of the video clip for scene N
