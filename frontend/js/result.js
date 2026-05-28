/* AXION — Result Page Controller */

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  let pollInterval  = null;
  let wasRunning    = false;
  let pollStartTime = Date.now();

  /* ─── Init ───────────────────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", () => {
    bindButtons();
    bindSubtitleToggle();
    startPolling();       // always poll on load — pipeline may be mid-run
    loadState();
  });

  /* ─── Buttons ────────────────────────────────────────────────────────────── */
  function bindButtons() {
    $("#compose-btn")  ?.addEventListener("click", handleCompose);
    $("#revision-btn") ?.addEventListener("click", handleRevision);
    $("#publish-btn")  ?.addEventListener("click", handlePublish);
  }

  function bindSubtitleToggle() {
    const cb  = $("#compose-subtitle-enabled");
    const sel = $("#compose-subtitle-language");
    if (!cb || !sel) return;
    cb.addEventListener("change", () => {
      sel.disabled = !cb.checked;
      sel.style.opacity = cb.checked ? "1" : "0.4";
    });
  }

  /* ─── Polling ────────────────────────────────────────────────────────────── */
  function startPolling() {
    if (pollInterval) return;
    pollStartTime = Date.now();
    pollInterval = setInterval(poll, 1500);
    poll();
  }

  function stopPolling() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  }

  async function poll() {
    try {
      const res  = await fetch("/api/progress");
      const prog = await res.json();

      updateProgress(prog);

      if (prog.running) {
        wasRunning = true;
        show("#progress-panel");
        show("#waiting-panel");
        hide("#video-panel");
      }

      // Pipeline just finished
      if (wasRunning && !prog.running) {
        wasRunning = false;
        stopPolling();
        hide("#progress-panel");
        hide("#waiting-panel");
        await loadState();
      }

      // Not running, nothing pending — stop polling only after 10s grace period
      // (avoids stopping before the pipeline thread has had a chance to start)
      if (!prog.running && !wasRunning && Date.now() - pollStartTime > 10000) {
        stopPolling();
      }
    } catch (_) {}
  }

  function updateProgress(prog) {
    const fill   = $("#progress-fill");
    const badge  = $("#progress-stage-badge");
    const detail = $("#progress-detail");
    const navBadge = $("#nav-status-badge");

    if (fill)   fill.style.width = (prog.pct || 0) + "%";
    if (badge)  badge.textContent = prog.stage || "Running";
    if (detail) detail.textContent = prog.detail || "Processing...";

    if (navBadge) {
      if (prog.running) {
        navBadge.textContent = prog.stage || "Running";
        navBadge.style.display = "inline-block";
      } else {
        navBadge.style.display = "none";
      }
    }
  }

  /* ─── Load state ─────────────────────────────────────────────────────────── */
  async function loadState() {
    try {
      const res   = await fetch("/api/state");
      const state = await res.json();
      renderState(state);
    } catch (_) {}
  }

  function renderState(state) {
    if (state.status === "empty") {
      show("#waiting-panel");
      return;
    }

    const hasVideo  = !!state.final_video_path;
    const hasClips  = state.has_video_clips;
    const hasErrors = state.error_log?.length > 0;
    const hasStory  = state.storyboard?.length > 0;

    // Video player
    if (hasVideo) {
      show("#video-panel");
      hide("#waiting-panel");
      const src = $("#video-source");
      if (src) { src.src = "/api/video?t=" + Date.now(); }
      const v = $("#result-video");
      if (v) v.load();
    } else if (!wasRunning) {
      show("#waiting-panel");
    }

    // Compose panel (when clips exist)
    if (hasClips && !hasVideo) show("#compose-panel");
    else if (hasClips && hasVideo) show("#compose-panel"); // re-compose allowed

    // Revision panel (when video exists)
    if (hasVideo) show("#revision-panel");

    // Errors
    if (hasErrors) {
      show("#error-panel");
      const list = $("#error-list");
      if (list) list.innerHTML = state.error_log.map((e) => `<p>• ${esc(e)}</p>`).join("");
    } else {
      hide("#error-panel");
    }

    // Storyboard
    if (hasStory) renderStoryboard(state.storyboard);
  }

  /* ─── Storyboard ─────────────────────────────────────────────────────────── */
  function renderStoryboard(scenes) {
    const list  = $("#storyboard-list");
    const count = $("#storyboard-count");
    if (!list) return;

    if (count) count.textContent = `${scenes.length} scenes`;

    const STATUS = {
      done:    { icon: "✅", cls: "scene-done" },
      error:   { icon: "❌", cls: "scene-error" },
      pending: { icon: "⏳", cls: "scene-pending" },
    };

    list.innerHTML = scenes.map((s) => {
      const st = STATUS[s.status] || STATUS.pending;
      return `
        <div class="scene-card ${st.cls}">
          <span class="scene-id">#${s.scene_id}</span>
          <span class="scene-status">${st.icon}</span>
          <div class="scene-body">
            <p class="scene-narration" title="${esc(s.narration)}">${esc(s.narration.slice(0, 80))}${s.narration.length > 80 ? "…" : ""}</p>
            <p class="scene-visual" title="${esc(s.visual_description)}">${esc(s.visual_description.slice(0, 60))}${s.visual_description.length > 60 ? "…" : ""}</p>
          </div>
        </div>`;
    }).join("");
  }

  /* ─── Compose ────────────────────────────────────────────────────────────── */
  async function handleCompose() {
    const btn = $("#compose-btn");
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="result-spinner d-inline-block me-2" style="width:12px;height:12px"></span>Composing...'; }

    const payload = {
      subtitle_enabled:  $("#compose-subtitle-enabled")?.checked ?? true,
      subtitle_language: $("#compose-subtitle-language")?.value  || "zh-TW",
    };

    try {
      const res  = await fetch("/api/compose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      wasRunning = true;
      show("#progress-panel");
      startPolling();
    } catch (err) {
      showToast("Compose failed: " + err.message, "error");
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi-film me-2"></i>Compose'; }
    }
  }

  /* ─── Revision ───────────────────────────────────────────────────────────── */
  async function handleRevision() {
    const text = ($("#revision-text")?.value || "").trim();
    if (!text) return showToast("Please enter a revision instruction.", "error");
    showToast("Revision via API — coming soon.", "info");
  }

  /* ─── Publish ────────────────────────────────────────────────────────────── */
  async function handlePublish() {
    showToast("Publishing to social media — coming soon.", "info");
  }

  /* ─── Helpers ────────────────────────────────────────────────────────────── */
  function show(sel) { const el = $(sel); if (el) el.style.display = "block"; }
  function hide(sel) { const el = $(sel); if (el) el.style.display = "none"; }

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function showToast(msg, type = "info") {
    const existing = document.querySelector(".axion-toast");
    if (existing) existing.remove();
    const colors = { success: "#10B981", error: "#ef4444", info: "#00CFFF" };
    const toast = document.createElement("div");
    toast.className = "axion-toast";
    toast.style.cssText = `
      position:fixed;bottom:24px;right:24px;z-index:9999;
      background:#0E1628;border:1px solid ${colors[type]||colors.info};
      border-radius:10px;padding:14px 20px;font-family:'Space Grotesk',sans-serif;
      font-size:14px;color:#F1F5F9;max-width:320px;
      box-shadow:0 8px 32px rgba(0,0,0,.4);
      animation:toastIn .3s ease;
    `;
    toast.textContent = msg;
    if (!document.querySelector("#toast-style")) {
      const s = document.createElement("style");
      s.id = "toast-style";
      s.textContent = "@keyframes toastIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}";
      document.head.appendChild(s);
    }
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

})();
