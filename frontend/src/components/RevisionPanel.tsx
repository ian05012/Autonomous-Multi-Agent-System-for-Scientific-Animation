type Props = {
  value: string;
  disabled: boolean;
  canSubmit: boolean;
  canCompose: boolean;
  canPublish: boolean;
  subtitleEnabled: boolean;
  subtitleLanguage: string;
  onChange: (value: string) => void;
  onRevision: () => void;
  onCompose: () => void;
  onPublish: () => void;
};

export function RevisionPanel({
  value,
  disabled,
  canSubmit,
  canCompose,
  canPublish,
  subtitleEnabled,
  subtitleLanguage,
  onChange,
  onRevision,
  onCompose,
  onPublish,
}: Props) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <div>
        <label className="mb-2 block text-xs font-medium text-studio-muted">Revision instruction</label>
        <textarea
          className="field min-h-28 resize-y px-3 py-3"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder='Try: "Change scene 2 to use a clearer particle diagram."'
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
        <button
          type="button"
          disabled={disabled || !canCompose}
          onClick={onCompose}
          className="rounded-lg bg-white px-4 py-3 text-sm font-semibold text-black transition hover:bg-studio-violet disabled:cursor-not-allowed disabled:opacity-45"
        >
          Compose Video
          <span className="mt-1 block text-xs font-normal opacity-70">
            {subtitleEnabled ? subtitleLanguage : "no subtitles"}
          </span>
        </button>
        <button
          type="button"
          disabled={disabled || !canSubmit}
          onClick={onRevision}
          className="rounded-lg border border-white/14 bg-white/[0.05] px-4 py-3 text-sm font-semibold text-white transition hover:border-studio-violet disabled:cursor-not-allowed disabled:opacity-45"
        >
          Submit Revision
        </button>
        <button
          type="button"
          disabled={disabled || !canPublish}
          onClick={onPublish}
          className="rounded-lg bg-studio-purple px-4 py-3 text-sm font-semibold text-white transition hover:bg-studio-violet disabled:cursor-not-allowed disabled:opacity-45"
        >
          Approve & Publish
        </button>
      </div>
    </div>
  );
}
