import type { PipelineState, ProgressState } from "../types/pipeline";

type Props = {
  state: PipelineState | null;
  progress: ProgressState | null;
};

export function LogsPanel({ state, progress }: Props) {
  const progressLogs = progress?.logs ?? [];
  const errorLog = state?.error_log ?? [];

  if (!progressLogs.length && !errorLog.length) {
    return <p className="rounded-lg border border-white/10 bg-white/[0.04] p-4 text-sm text-studio-muted">No logs yet.</p>;
  }

  return (
    <div className="space-y-2">
      {progressLogs.map((entry, index) => (
        <div key={`${entry.t}-${index}`} className="rounded-lg border border-white/10 bg-black/28 px-3 py-2 text-sm">
          <span className="mono-display mr-2 text-xs text-studio-violet">{entry.t}s</span>
          <span className="text-studio-muted">{entry.stage}</span>
          <span className="mx-2 text-white/25">/</span>
          <span>{entry.msg}</span>
        </div>
      ))}
      {errorLog.map((entry, index) => (
        <pre key={index} className="whitespace-pre-wrap rounded-lg border border-red-400/20 bg-red-500/10 p-3 text-xs text-red-100">
          {entry}
        </pre>
      ))}
    </div>
  );
}
