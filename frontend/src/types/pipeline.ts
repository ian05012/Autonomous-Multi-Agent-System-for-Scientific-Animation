export type SourceType = "text" | "pdf" | "url";
export type ModelTier = "paid" | "free";

export type SceneSpec = {
  scene_id: number;
  narration: string;
  visual_description: string;
  estimated_duration: number;
  status: string;
};

export type PipelineState = {
  input_text: string;
  source_type: SourceType;
  input_path?: string | null;
  storyboard: SceneSpec[];
  audio_files: Array<Record<string, unknown>>;
  video_clips: Array<Record<string, unknown>>;
  final_video_path?: string | null;
  final_video_url?: string | null;
  hitl_revision?: string | null;
  revision_target?: Record<string, unknown> | null;
  iteration: number;
  error_log: string[];
  youtube_url?: string | null;
  instagram_url?: string | null;
};

export type ApiState = {
  state: PipelineState | null;
  running: boolean;
  status_message: string;
  error: string;
};

export type ProgressState = {
  running: boolean;
  pct: number;
  stage: string;
  detail: string;
  done: boolean;
  error: string;
  logs: Array<{ t: number; stage: string; msg: string; kind: string }>;
};

export type PipelineStartPayload = {
  source_type: SourceType;
  input_value: string;
  model_tier: ModelTier;
  tts_language: string;
  subtitle_enabled: boolean;
  subtitle_language: string;
};
