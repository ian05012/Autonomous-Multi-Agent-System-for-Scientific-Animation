/* AXION Science Studio — Frontend Controller */

(function () {
  "use strict";

  /* ─── State ─────────────────────────────────────────────────────────────── */
  let currentTier      = "paid";
  let currentInputType = "text";
  let uploadedPdfPath  = null;
  let pollInterval     = null;
  let isRunning        = false;

  const TIER_INFO = {
    paid: { llm: "gpt-5", animator: "gpt-5.1-codex" },
    free: { llm: "gpt-oss-20b:free", animator: "gpt-oss-120b:free" },
  };

  /* ─── DOM refs ───────────────────────────────────────────────────────────── */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  /* ─── Init ───────────────────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", () => {
    bindInputTabs();
    bindTierToggle();
    bindSubtitleToggle();
    bindPdfUpload();
    bindButtons();
    loadInitialState();
  });

  /* ─── Input tabs ─────────────────────────────────────────────────────────── */
  function bindInputTabs() {
    $$("[data-tab]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        const tab = el.dataset.tab;
        currentInputType = tab;
        $$("[data-tab]").forEach((t) => t.classList.remove("active"));
        el.classList.add("active");
        ["text", "pdf", "url"].forEach((t) => {
          const panel = $(`#input-${t}-panel`);
          if (panel) panel.style.display = t === tab ? "block" : "none";
        });
      });
    });
  }

  /* ─── Model tier toggle ──────────────────────────────────────────────────── */
  function bindTierToggle() {
    $$(".tier-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".tier-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentTier = btn.dataset.tier;
        const info = TIER_INFO[currentTier];
        const hint = $("#tier-hint");
        if (hint) {
          hint.innerHTML = `Scriptwriter: <code>${info.llm}</code> &nbsp;|&nbsp; Animator: <code>${info.animator}</code>`;
        }
      });
    });
  }

  /* ─── Subtitle toggle ────────────────────────────────────────────────────── */
  function bindSubtitleToggle() {
    const checkbox = $("#subtitle-enabled");
    const langSel  = $("#subtitle-language");
    if (!checkbox || !langSel) return;
    checkbox.addEventListener("change", () => {
      langSel.disabled = !checkbox.checked;
      langSel.style.opacity = checkbox.checked ? "1" : "0.4";
    });
  }

  /* ─── PDF upload ─────────────────────────────────────────────────────────── */
  function bindPdfUpload() {
    const zone  = $("#upload-zone");
    const input = $("#pdf-input");
    const label = $(".upload-browse");
    if (!zone || !input) return;

    label && label.addEventListener("click", (e) => { e.preventDefault(); input.click(); });

    zone.addEventListener("click", () => input.click());
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag-over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      if (e.dataTransfer.files[0]) uploadPdf(e.dataTransfer.files[0]);
    });

    input.addEventListener("change", () => {
      if (input.files[0]) uploadPdf(input.files[0]);
    });
  }

  async function uploadPdf(file) {
    const status = $("#upload-status");
    if (status) { status.style.display = "block"; status.textContent = `Uploading ${file.name}...`; }

    const form = new FormData();
    form.append("file", file);

    try {
      const res  = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      uploadedPdfPath = data.path;
      if (status) status.textContent = `✓ ${file.name} uploaded`;
    } catch (err) {
      if (status) status.textContent = `✗ Upload failed: ${err.message}`;
    }
  }

  /* ─── Buttons ────────────────────────────────────────────────────────────── */
  function bindButtons() {
    const generateBtn = $("#generate-btn");
    const clearBtn    = $("#clear-btn");
    const composeBtn  = $("#compose-btn");
    const revisionBtn = $("#revision-btn");

    generateBtn && generateBtn.addEventListener("click", handleGenerate);
    clearBtn    && clearBtn.addEventListener("click", handleClear);
    composeBtn  && composeBtn.addEventListener("click", handleCompose);
    revisionBtn && revisionBtn.addEventListener("click", handleRevision);
  }

  /* ─── Generate ───────────────────────────────────────────────────────────── */
  async function handleGenerate() {
    let inputText = "";
    let inputPath = null;

    if (currentInputType === "text") {
      inputText = ($("#input-text")?.value || "").trim();
      if (!inputText) return showToast("Please paste a science article first.", "error");
    } else if (currentInputType === "pdf") {
      if (!uploadedPdfPath) return showToast("Please upload a PDF first.", "error");
      inputText = uploadedPdfPath;
      inputPath = uploadedPdfPath;
    } else {
      inputText = ($("#input-url")?.value || "").trim();
      if (!inputText) return showToast("Please enter a URL.", "error");
      inputPath = inputText;
    }

    const payload = {
      source_type:       currentInputType,
      input_text:        inputText,
      input_path:        inputPath,
      model_tier:        currentTier,
      tts_language:      $("#tts-language")?.value || "en-US",
      subtitle_enabled:  $("#subtitle-enabled")?.checked ?? true,
      subtitle_language: $("#subtitle-language")?.value || "zh-TW",
    };

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.error) return showToast(data.error, "error");
      startPolling();
      scrollTo("#section_4");
      showToast("Pipeline started!", "success");
    } catch (err) {
      showToast("Failed to start pipeline: " + err.message, "error");
    }
  }

  /* ─── Compose ────────────────────────────────────────────────────────────── */
  async function handleCompose() {
    const payload = {
      subtitle_enabled:  $("#subtitle-enabled")?.checked ?? true,
      subtitle_language: $("#subtitle-language")?.value || "zh-TW",
    };
    try {
      await fetch("/api/compose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      startPolling();
      showToast("Composing video...", "success");
    } catch (err) {
      showToast("Compose failed: " + err.message, "error");
    }
  }

  /* ─── Revision ───────────────────────────────────────────────────────────── */
  async function handleRevision() {
    const text = ($("#revision-text")?.value || "").trim();
    if (!text) return showToast("Please enter a revision instruction.", "error");
    showToast("Revision support via API coming soon.", "info");
  }

  /* ─── Clear ──────────────────────────────────────────────────────────────── */
  async function handleClear() {
    if (!confirm("Clear all generated content and start over?")) return;
    try {
      await fetch("/api/clear", { method: "POST" });
      stopPolling();
      hideAllPanels();
      showToast("Cleared.", "success");
    } catch (err) {
      showToast("Clear failed.", "error");
    }
  }

  /* ─── Polling ────────────────────────────────────────────────────────────── */
  function startPolling() {
    isRunning = true;
    showPanel("#progress-panel");
    setButtonsDisabled(true);
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollProgress, 1500);
    pollProgress();
  }

  function stopPolling() {
    isRunning = false;
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    setButtonsDisabled(false);
  }

  async function pollProgress() {
    try {
      const res  = await fetch("/api/progress");
      const prog = await res.json();

      updateProgressUI(prog);

      if (prog.done || (!prog.running && prog.pct >= 100)) {
        stopPolling();
        hidePanel("#progress-panel");
        await refreshState();
      } else if (!prog.running && prog.pct === 0 && !isRunning) {
        stopPolling();
      }
    } catch (_) {}
  }

  function updateProgressUI(prog) {
    const fill  = $("#progress-fill");
    const badge = $("#progress-stage-badge");
    const detail = $("#progress-detail");

    if (fill)   fill.style.width = (prog.pct || 0) + "%";
    if (badge)  badge.textContent = prog.stage || "Running";
    if (detail) detail.textContent = prog.detail || "Processing...";
  }

  /* ─── State refresh ──────────────────────────────────────────────────────── */
  async function loadInitialState() {
    try {
      const res   = await fetch("/api/state");
      const state = await res.json();
      if (state.status !== "empty") renderState(state);
    } catch (_) {}
  }

  async function refreshState() {
    try {
      const res   = await fetch("/api/state");
      const state = await res.json();
      renderState(state);
    } catch (_) {}
  }

  function renderState(state) {
    const hasClips = state.has_video_clips;
    const hasVideo = !!state.final_video_path;
    const hasStoryboard = state.storyboard && state.storyboard.length > 0;
    const hasErrors = state.error_log && state.error_log.length > 0;

    // Controls
    if (hasClips || hasVideo) showPanel("#controls-panel");

    // Video
    if (hasVideo) {
      showPanel("#video-panel");
      const v = $("#result-video");
      if (v) { v.load(); }
    }

    // Errors
    if (hasErrors) {
      showPanel("#error-panel");
      const list = $("#error-list");
      if (list) {
        list.innerHTML = state.error_log.map((e) => `<p>• ${escHtml(e)}</p>`).join("");
      }
    } else {
      hidePanel("#error-panel");
    }

    // Storyboard
    if (hasStoryboard) {
      showPanel("#storyboard-panel");
      const count = $("#storyboard-count");
      if (count) count.textContent = `${state.storyboard.length} scenes`;
      renderStoryboard(state.storyboard);
    }
  }

  function renderStoryboard(scenes) {
    const list = $("#storyboard-list");
    if (!list) return;
    const STATUS_ICON = { done: "✅", error: "❌", pending: "⏳" };
    list.innerHTML = scenes.map((s) => `
      <div class="scene-card">
        <span class="scene-id">Scene ${s.scene_id}</span>
        <span class="scene-status">${STATUS_ICON[s.status] || "⏳"}</span>
        <div class="scene-body">
          <p class="scene-narration">${escHtml(s.narration.slice(0, 120))}${s.narration.length > 120 ? "…" : ""}</p>
          <p class="scene-visual">${escHtml(s.visual_description.slice(0, 80))}${s.visual_description.length > 80 ? "…" : ""}</p>
        </div>
      </div>
    `).join("");
  }

  /* ─── UI helpers ─────────────────────────────────────────────────────────── */
  function showPanel(sel) {
    const el = $(sel);
    if (el) el.style.display = "block";
  }
  function hidePanel(sel) {
    const el = $(sel);
    if (el) el.style.display = "none";
  }
  function hideAllPanels() {
    ["#progress-panel","#error-panel","#video-panel","#controls-panel","#storyboard-panel"]
      .forEach(hidePanel);
  }

  function setButtonsDisabled(disabled) {
    ["#generate-btn","#compose-btn","#revision-btn"].forEach((sel) => {
      const btn = $(sel);
      if (btn) btn.disabled = disabled;
    });
    if (disabled) {
      const btn = $("#generate-btn");
      if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running...';
    } else {
      const btn = $("#generate-btn");
      if (btn) btn.innerHTML = '<i class="bi-play-fill me-2"></i>Generate Animation';
    }
  }

  function scrollTo(sel) {
    const el = $(sel);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ─── Toast notifications ────────────────────────────────────────────────── */
  function showToast(message, type = "info") {
    const existing = $(".axion-toast");
    if (existing) existing.remove();

    const colors = { success: "#10B981", error: "#ef4444", info: "#00CFFF" };
    const toast = document.createElement("div");
    toast.className = "axion-toast";
    toast.style.cssText = `
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      background: #0E1628; border: 1px solid ${colors[type] || colors.info};
      border-radius: 10px; padding: 14px 20px; font-family: 'Space Grotesk', sans-serif;
      font-size: 14px; color: #F1F5F9; max-width: 320px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      animation: toastIn 0.3s ease;
    `;
    toast.textContent = message;

    const style = document.createElement("style");
    style.textContent = `@keyframes toastIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }`;
    document.head.appendChild(style);

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

})();
