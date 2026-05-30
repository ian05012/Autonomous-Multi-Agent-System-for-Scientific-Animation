import { FileText, Link, Type } from "lucide-react";
import type { SourceType } from "../types/pipeline";

type Props = {
  sourceType: SourceType;
  inputValue: string;
  uploadedName: string;
  uploadStatus: string;
  onSourceType: (value: SourceType) => void;
  onInputValue: (value: string) => void;
  onUpload: (file: File) => void;
  disabled?: boolean;
};

export function InputPanel({
  sourceType,
  inputValue,
  uploadedName,
  uploadStatus,
  onSourceType,
  onInputValue,
  onUpload,
  disabled,
}: Props) {
  const sourceOptions = [
    { id: "text", label: "Text", icon: Type },
    { id: "pdf", label: "PDF", icon: FileText },
    { id: "url", label: "URL", icon: Link },
  ] as const;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {sourceOptions.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            disabled={disabled}
            onClick={() => onSourceType(id)}
            className={`flex items-center justify-center gap-2 rounded-lg border px-2 py-2 text-sm transition ${
              sourceType === id
                ? "border-studio-violet bg-studio-purple/30 text-white"
                : "border-white/10 bg-white/[0.04] text-studio-muted hover:border-white/24"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {sourceType === "text" && (
        <textarea
          className="field min-h-44 resize-y px-3 py-3"
          value={inputValue}
          disabled={disabled}
          onChange={(event) => onInputValue(event.target.value)}
          placeholder="Paste a science article here..."
        />
      )}

      {sourceType === "pdf" && (
        <label className="block rounded-lg border border-dashed border-white/20 bg-white/[0.04] p-4 text-sm text-studio-muted">
          <span className="mb-2 block font-medium text-studio-ink">Upload PDF</span>
          <input
            type="file"
            accept="application/pdf"
            disabled={disabled}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
            }}
            className="w-full text-sm"
          />
          {uploadedName && <span className="mt-3 block text-studio-violet">{uploadedName}</span>}
          {uploadStatus && <span className="mt-2 block text-xs text-studio-muted">{uploadStatus}</span>}
          {!uploadedName && !uploadStatus && (
            <span className="mt-2 block text-xs text-studio-muted">Generate unlocks after the PDF is uploaded to the backend.</span>
          )}
        </label>
      )}

      {sourceType === "url" && (
        <input
          className="field px-3 py-3"
          value={inputValue}
          disabled={disabled}
          onChange={(event) => onInputValue(event.target.value)}
          placeholder="https://..."
        />
      )}
    </div>
  );
}
