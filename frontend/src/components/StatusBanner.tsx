import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

type Props = {
  message: string;
  error?: string;
  running?: boolean;
};

export function StatusBanner({ message, error, running }: Props) {
  if (!message && !error && !running) return null;

  const tone = error ? "border-red-400/30 bg-red-500/12 text-red-100" : "border-white/12 bg-white/[0.05] text-studio-ink";
  const Icon = error ? AlertCircle : running ? Loader2 : CheckCircle2;

  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${tone}`}>
      <Icon size={18} className={running ? "mt-0.5 animate-spin" : "mt-0.5"} />
      <p className="text-sm">{error || message || "Pipeline running..."}</p>
    </div>
  );
}
