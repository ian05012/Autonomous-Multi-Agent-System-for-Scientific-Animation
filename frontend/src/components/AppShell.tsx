import type { ReactNode } from "react";
import { Settings, Sparkles } from "lucide-react";

type Props = {
  children: ReactNode;
  onGenerate: () => void;
  canGenerate: boolean;
  running: boolean;
};

export function AppShell({ children, onGenerate, canGenerate, running }: Props) {
  return (
    <div className="min-h-screen text-studio-ink">
      <nav className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-black">
            <Sparkles size={18} />
          </div>
          <span className="mono-display text-sm font-semibold uppercase">Science Animation Studio</span>
        </div>
        <div className="hidden items-center gap-7 text-sm text-studio-muted md:flex">
          <a href="#" className="hover:text-white">Docs</a>
          <a href="#" className="hover:text-white">Examples</a>
          <a href="#" className="hover:text-white">Settings</a>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="rounded-lg border border-white/12 bg-white/[0.05] p-2 text-studio-muted md:hidden">
            <Settings size={18} />
          </button>
          <button
            type="button"
            disabled={!canGenerate || running}
            onClick={onGenerate}
            className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-studio-violet disabled:cursor-not-allowed disabled:opacity-45"
          >
            Generate
          </button>
        </div>
      </nav>
      {children}
    </div>
  );
}
