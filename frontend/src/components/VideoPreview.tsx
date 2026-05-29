import { Clapperboard } from "lucide-react";
import { API_BASE } from "../api/client";
import type { PipelineState } from "../types/pipeline";

type Props = {
  state: PipelineState | null;
  running: boolean;
};

export function VideoPreview({ state, running }: Props) {
  const videoUrl = state?.final_video_url ? `${API_BASE}${state.final_video_url}` : null;

  if (videoUrl) {
    return (
      <div className="overflow-hidden rounded-lg border border-white/10 bg-black">
        <video src={videoUrl} controls className="aspect-video w-full" />
      </div>
    );
  }

  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-white/16 bg-black/35 p-6 text-center sm:h-auto sm:aspect-video sm:min-h-64">
      <div>
        <Clapperboard className="mx-auto mb-4 text-studio-violet" size={42} />
        <p className="text-base font-semibold text-studio-ink">{running ? "Rendering draft..." : "No video yet"}</p>
        <p className="mx-auto mt-2 max-w-sm text-sm text-studio-muted">
          {running ? "The preview will appear after composition finishes." : "Start the pipeline to generate scenes, audio, and a composed MP4."}
        </p>
      </div>
    </div>
  );
}
