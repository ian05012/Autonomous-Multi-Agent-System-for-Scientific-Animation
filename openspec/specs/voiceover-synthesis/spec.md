## ADDED Requirements

### Requirement: Synthesize speech for each scene narration
The system SHALL call the configured TTS provider (OpenAI TTS or ElevenLabs) for each scene's `narration` text and save the resulting audio as an MP3 file, returning an `AudioMeta` object with file path and measured duration.

#### Scenario: Successful TTS synthesis
- **WHEN** Voiceover Agent receives a non-empty `narration` string
- **THEN** it saves an MP3 file to `output/audio/scene_{scene_id}.mp3` and returns `AudioMeta` with `file_path` and `duration_seconds` (measured, not estimated)

#### Scenario: TTS API failure
- **WHEN** TTS API call fails (network error, quota exceeded, invalid API key)
- **THEN** system logs the error and raises a recoverable exception; the Supervisor Agent retries up to 3 times before surfacing the error to the user

### Requirement: Audio duration measured from actual file
The `duration_seconds` in `AudioMeta` MUST be measured from the generated audio file using `librosa.get_duration`, not taken from the TTS API response or estimated from word count.

#### Scenario: Duration measurement
- **WHEN** TTS synthesis succeeds and MP3 file is saved
- **THEN** `AudioMeta.duration_seconds` equals `librosa.get_duration(filename=mp3_path)` with precision to one decimal place

### Requirement: Configurable TTS provider
The system SHALL support switching between OpenAI TTS (`tts-1` model, `onyx` voice) and ElevenLabs via an environment variable `TTS_PROVIDER`.

#### Scenario: Provider selection via environment variable
- **WHEN** `TTS_PROVIDER=openai` is set
- **THEN** Voiceover Agent uses OpenAI TTS API

#### Scenario: ElevenLabs selection
- **WHEN** `TTS_PROVIDER=elevenlabs` is set
- **THEN** Voiceover Agent uses ElevenLabs API with voice ID from `ELEVENLABS_VOICE_ID` env var
