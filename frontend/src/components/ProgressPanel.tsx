import type { ProgressState } from "../types/pipeline";

type Props = {
  progress: ProgressState | null;
};

export function ProgressPanel({ progress }: Props) {
  const pct = progress?.pct ?? 0;
  const stage = progress?.stage || "Ready";
  const detail = progress?.detail || "Waiting for your source material.";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-studio-ink">{stage}</p>
          <p className="text-xs text-studio-muted">{detail}</p>
        </div>
        <span className="mono-display text-sm text-studio-violet">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-studio-purple to-studio-violet transition-all"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}
