import type { PipelineState } from "../types/pipeline";

type Props = {
  state: PipelineState | null;
};

export function StoryboardTable({ state }: Props) {
  const scenes = state?.storyboard ?? [];

  if (!scenes.length) {
    return <p className="rounded-lg border border-white/10 bg-white/[0.04] p-4 text-sm text-studio-muted">Storyboard not generated yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <thead className="text-xs uppercase text-studio-muted">
          <tr className="border-b border-white/10">
            <th className="py-3 pr-4">Scene</th>
            <th className="py-3 pr-4">Status</th>
            <th className="py-3 pr-4">Narration</th>
            <th className="py-3 pr-4">Visual</th>
            <th className="py-3">Duration</th>
          </tr>
        </thead>
        <tbody>
          {scenes.map((scene) => (
            <tr key={scene.scene_id} className="border-b border-white/8 align-top">
              <td className="py-3 pr-4 mono-display text-studio-violet">{scene.scene_id}</td>
              <td className="py-3 pr-4">
                <span className="rounded-full border border-white/10 bg-white/[0.05] px-2 py-1 text-xs">{scene.status}</span>
              </td>
              <td className="max-w-xs py-3 pr-4 text-studio-ink">{scene.narration}</td>
              <td className="max-w-xs py-3 pr-4 text-studio-muted">{scene.visual_description}</td>
              <td className="py-3 text-studio-muted">{scene.estimated_duration?.toFixed?.(1) ?? "0.0"}s</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
