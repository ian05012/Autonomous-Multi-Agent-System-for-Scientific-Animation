import { useEffect, useMemo, useState } from "react";
import { Bug, FileJson, ListChecks } from "lucide-react";
import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { DashboardCard } from "./components/DashboardCard";
import { LogsPanel } from "./components/LogsPanel";
import { ProgressPanel } from "./components/ProgressPanel";
import { RevisionPanel } from "./components/RevisionPanel";
import { Sidebar } from "./components/Sidebar";
import { StatusBanner } from "./components/StatusBanner";
import { StoryboardTable } from "./components/StoryboardTable";
import { VideoPreview } from "./components/VideoPreview";
import type { ApiState, ModelTier, ProgressState, SourceType } from "./types/pipeline";

const initialApiState: ApiState = {
  state: null,
  running: false,
  status_message: "",
  error: "",
};

function App() {
  const [apiState, setApiState] = useState<ApiState>(initialApiState);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [modelTier, setModelTier] = useState<ModelTier>("paid");
  const [sourceType, setSourceType] = useState<SourceType>("text");
  const [inputValue, setInputValue] = useState("");
  const [uploadedName, setUploadedName] = useState("");
  const [ttsLanguage, setTtsLanguage] = useState("en-US");
  const [subtitleEnabled, setSubtitleEnabled] = useState(true);
  const [subtitleLanguage, setSubtitleLanguage] = useState("zh-TW");
  const [revisionText, setRevisionText] = useState("");
  const [activeTab, setActiveTab] = useState<"storyboard" | "logs" | "debug">("storyboard");
  const [clientError, setClientError] = useState("");

  const state = apiState.state;
  const running = apiState.running;
  const canGenerate = inputValue.trim().length > 0;
  const canCompose = Boolean(state?.video_clips?.length);
  const canPublish = Boolean(state?.final_video_path);
  const canSubmitRevision = Boolean(state?.final_video_path && revisionText.trim());

  const metrics = useMemo(
    () => [
      { label: "Scenes", value: state?.storyboard?.length ?? 0 },
      { label: "Audio", value: state?.audio_files?.length ?? 0 },
      { label: "Clips", value: state?.video_clips?.length ?? 0 },
      { label: "Iteration", value: state?.iteration ?? 0 },
    ],
    [state],
  );

  async function refresh() {
    const [nextState, nextProgress] = await Promise.all([api.getState(), api.getProgress()]);
    setApiState(nextState);
    setProgress(nextProgress);
  }

  useEffect(() => {
    refresh().catch((error) => setClientError(error.message));
    const timer = window.setInterval(() => {
      refresh().catch((error) => setClientError(error.message));
    }, 2500);
    return () => window.clearInterval(timer);
  }, []);

  async function runAction(action: () => Promise<ApiState | void>) {
    setClientError("");
    try {
      const next = await action();
      if (next) setApiState(next);
      await refresh();
    } catch (error) {
      setClientError(error instanceof Error ? error.message : "Unknown error");
    }
  }

  function handleGenerate() {
    if (!canGenerate) return;
    runAction(() =>
      api.startPipeline({
        source_type: sourceType,
        input_value: inputValue.trim(),
        model_tier: modelTier,
        tts_language: ttsLanguage,
        subtitle_enabled: subtitleEnabled,
        subtitle_language: subtitleLanguage,
      }),
    );
  }

  function handleUpload(file: File) {
    setClientError("");
    api
      .uploadPdf(file)
      .then((result) => {
        setInputValue(result.path);
        setUploadedName(result.filename);
      })
      .catch((error) => setClientError(error.message));
  }

  const errorScenes = state?.storyboard?.filter((scene) => scene.status === "error") ?? [];

  return (
    <AppShell onGenerate={handleGenerate} canGenerate={canGenerate} running={running}>
      <main className="mx-auto w-full max-w-7xl px-4 pb-12 pt-8 sm:px-6 lg:px-8">
        <header className="grid gap-8 pb-10 lg:grid-cols-[1fr_360px] lg:items-end">
          <div>
            <p className="mb-4 inline-flex rounded-full border border-studio-violet/30 bg-studio-purple/15 px-3 py-1 text-xs font-semibold uppercase text-studio-violet">
              AI video pipeline
            </p>
            <h1 className="mono-display max-w-4xl text-5xl font-bold leading-tight text-white sm:text-6xl lg:text-7xl">
              Science Animation Studio
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-studio-muted">
              Turn science articles into narrated educational animations with storyboard, voiceover, Manim rendering, review, and publishing controls.
            </p>
          </div>
          <DashboardCard eyebrow="Current run" title={running ? "Pipeline active" : "Ready for input"}>
            <ProgressPanel progress={progress} />
            <div className="mt-5 grid grid-cols-4 gap-2">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
                  <p className="mono-display text-lg font-semibold text-white">{metric.value}</p>
                  <p className="text-[11px] uppercase text-studio-muted">{metric.label}</p>
                </div>
              ))}
            </div>
          </DashboardCard>
        </header>

        <div className="mb-5 space-y-3">
          <StatusBanner message={apiState.status_message} error={apiState.error || clientError} running={running} />
          {errorScenes.length > 0 && (
            <StatusBanner
              message=""
              error={`${errorScenes.length} scene(s) failed to render. Check Logs and use revision instructions to target a fix.`}
            />
          )}
        </div>

        <section className="grid min-w-0 gap-5 lg:grid-cols-[380px_1fr]">
          <Sidebar
            modelTier={modelTier}
            sourceType={sourceType}
            inputValue={inputValue}
            uploadedName={uploadedName}
            ttsLanguage={ttsLanguage}
            subtitleEnabled={subtitleEnabled}
            subtitleLanguage={subtitleLanguage}
            running={running}
            canGenerate={canGenerate}
            onModelTier={setModelTier}
            onSourceType={(value) => {
              setSourceType(value);
              setInputValue("");
              setUploadedName("");
            }}
            onInputValue={setInputValue}
            onUpload={handleUpload}
            onTtsLanguage={setTtsLanguage}
            onSubtitleEnabled={setSubtitleEnabled}
            onSubtitleLanguage={setSubtitleLanguage}
            onGenerate={handleGenerate}
            onClear={() => runAction(api.clear)}
          />

          <div className="min-w-0 space-y-5">
            <DashboardCard eyebrow="Preview" title="Draft video">
              <VideoPreview state={state} running={running} />
              {(state?.youtube_url || state?.instagram_url) && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {state.youtube_url && <a className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-studio-violet" href={state.youtube_url}>YouTube published</a>}
                  {state.instagram_url && <a className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm text-studio-violet" href={state.instagram_url}>Instagram published</a>}
                </div>
              )}
            </DashboardCard>

            <DashboardCard eyebrow="Review" title="Human-in-the-loop controls">
              <RevisionPanel
                value={revisionText}
                disabled={running}
                canSubmit={canSubmitRevision}
                canCompose={canCompose}
                canPublish={canPublish}
                subtitleEnabled={subtitleEnabled}
                subtitleLanguage={subtitleLanguage}
                onChange={setRevisionText}
                onRevision={() =>
                  runAction(async () => {
                    const result = await api.submitRevision(revisionText.trim());
                    setRevisionText("");
                    return result;
                  })
                }
                onCompose={() => runAction(() => api.composeVideo(subtitleEnabled, subtitleLanguage))}
                onPublish={() => runAction(api.publish)}
              />
            </DashboardCard>
          </div>
        </section>

        <DashboardCard className="mt-5" eyebrow="Pipeline data" title="Review artifacts">
          <div className="mb-4 flex flex-wrap gap-2">
            {[
              { id: "storyboard", label: "Storyboard", icon: ListChecks },
              { id: "logs", label: "Logs", icon: Bug },
              { id: "debug", label: "Debug State", icon: FileJson },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setActiveTab(id as typeof activeTab)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  activeTab === id
                    ? "border-studio-violet bg-studio-purple/30 text-white"
                    : "border-white/10 bg-white/[0.04] text-studio-muted"
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>

          {activeTab === "storyboard" && <StoryboardTable state={state} />}
          {activeTab === "logs" && <LogsPanel state={state} progress={progress} />}
          {activeTab === "debug" && (
            <pre className="max-h-[520px] overflow-auto rounded-lg border border-white/10 bg-black/30 p-4 text-xs text-studio-muted">
              {JSON.stringify(state ?? { empty: true }, null, 2)}
            </pre>
          )}
        </DashboardCard>
      </main>
    </AppShell>
  );
}

export default App;
