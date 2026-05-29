import type { ModelTier } from "../types/pipeline";

type Props = {
  value: ModelTier;
  onChange: (value: ModelTier) => void;
  disabled?: boolean;
};

export function ModelSelector({ value, onChange, disabled }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {[
        { id: "paid", label: "Paid", detail: "OpenAI" },
        { id: "free", label: "Free", detail: "OpenRouter" },
      ].map((item) => (
        <button
          key={item.id}
          type="button"
          disabled={disabled}
          onClick={() => onChange(item.id as ModelTier)}
          className={`rounded-lg border px-3 py-3 text-left transition ${
            value === item.id
              ? "border-studio-violet bg-studio-purple/30 text-white"
              : "border-white/10 bg-white/[0.04] text-studio-muted hover:border-white/24"
          } disabled:cursor-not-allowed disabled:opacity-50`}
        >
          <span className="block text-sm font-semibold">{item.label}</span>
          <span className="block text-xs">{item.detail}</span>
        </button>
      ))}
    </div>
  );
}
