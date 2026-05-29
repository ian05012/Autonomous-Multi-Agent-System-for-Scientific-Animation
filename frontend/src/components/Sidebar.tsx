import { Play, RotateCcw } from "lucide-react";
import { InputPanel } from "./InputPanel";
import { LanguageSettings } from "./LanguageSettings";
import { ModelSelector } from "./ModelSelector";
import type { ModelTier, SourceType } from "../types/pipeline";

type Props = {
  modelTier: ModelTier;
  sourceType: SourceType;
  inputValue: string;
  uploadedName: string;
  ttsLanguage: string;
  subtitleEnabled: boolean;
  subtitleLanguage: string;
  running: boolean;
  canGenerate: boolean;
  onModelTier: (value: ModelTier) => void;
  onSourceType: (value: SourceType) => void;
  onInputValue: (value: string) => void;
  onUpload: (file: File) => void;
  onTtsLanguage: (value: string) => void;
  onSubtitleEnabled: (value: boolean) => void;
  onSubtitleLanguage: (value: string) => void;
  onGenerate: () => void;
  onClear: () => void;
};

export function Sidebar(props: Props) {
  return (
    <aside className="glass-panel min-w-0 rounded-lg p-5">
      <div className="mb-5">
        <p className="mb-1 text-[11px] font-semibold uppercase text-studio-violet">Studio input</p>
        <h2 className="text-lg font-semibold">Source material</h2>
      </div>

      <div className="space-y-6">
        <div>
          <label className="mb-2 block text-xs font-medium text-studio-muted">Model tier</label>
          <ModelSelector value={props.modelTier} onChange={props.onModelTier} disabled={props.running} />
        </div>

        <InputPanel
          sourceType={props.sourceType}
          inputValue={props.inputValue}
          uploadedName={props.uploadedName}
          onSourceType={props.onSourceType}
          onInputValue={props.onInputValue}
          onUpload={props.onUpload}
          disabled={props.running}
        />

        <LanguageSettings
          ttsLanguage={props.ttsLanguage}
          subtitleEnabled={props.subtitleEnabled}
          subtitleLanguage={props.subtitleLanguage}
          onTtsLanguage={props.onTtsLanguage}
          onSubtitleEnabled={props.onSubtitleEnabled}
          onSubtitleLanguage={props.onSubtitleLanguage}
          disabled={props.running}
        />

        <div className="grid gap-3">
          <button
            type="button"
            disabled={props.running || !props.canGenerate}
            onClick={props.onGenerate}
            className="flex items-center justify-center gap-2 rounded-lg bg-studio-purple px-4 py-3 text-sm font-semibold text-white shadow-glow transition hover:bg-studio-violet disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Play size={17} />
            Generate Animation
          </button>
          <button
            type="button"
            disabled={props.running}
            onClick={props.onClear}
            className="flex items-center justify-center gap-2 rounded-lg border border-white/12 bg-white/[0.04] px-4 py-3 text-sm font-semibold text-studio-muted transition hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
          >
            <RotateCcw size={16} />
            Clear & Start Over
          </button>
        </div>
      </div>
    </aside>
  );
}
