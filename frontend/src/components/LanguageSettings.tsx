type Props = {
  ttsLanguage: string;
  subtitleEnabled: boolean;
  subtitleLanguage: string;
  onTtsLanguage: (value: string) => void;
  onSubtitleEnabled: (value: boolean) => void;
  onSubtitleLanguage: (value: string) => void;
  disabled?: boolean;
};

const ttsLanguages = ["en-US", "zh-TW", "zh-CN", "ja-JP", "ko-KR", "fr-FR", "de-DE", "es-ES"];
const subtitleLanguages = ["en", "zh-TW", "zh-CN", "ja", "ko", "fr", "de", "es", "pt", "ar"];

export function LanguageSettings({
  ttsLanguage,
  subtitleEnabled,
  subtitleLanguage,
  onTtsLanguage,
  onSubtitleEnabled,
  onSubtitleLanguage,
  disabled,
}: Props) {
  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-2 block text-xs font-medium text-studio-muted">Speech language</span>
        <select
          className="field px-3 py-2"
          value={ttsLanguage}
          disabled={disabled}
          onChange={(event) => onTtsLanguage(event.target.value)}
        >
          {ttsLanguages.map((language) => (
            <option key={language}>{language}</option>
          ))}
        </select>
      </label>

      <label className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-3">
        <span>
          <span className="block text-sm font-medium">Subtitles</span>
          <span className="text-xs text-studio-muted">Burn translated captions into final video</span>
        </span>
        <input
          type="checkbox"
          checked={subtitleEnabled}
          disabled={disabled}
          onChange={(event) => onSubtitleEnabled(event.target.checked)}
          className="h-5 w-5 accent-studio-purple"
        />
      </label>

      <label className="block">
        <span className="mb-2 block text-xs font-medium text-studio-muted">Subtitle language</span>
        <select
          className="field px-3 py-2"
          value={subtitleLanguage}
          disabled={disabled || !subtitleEnabled}
          onChange={(event) => onSubtitleLanguage(event.target.value)}
        >
          {subtitleLanguages.map((language) => (
            <option key={language}>{language}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
