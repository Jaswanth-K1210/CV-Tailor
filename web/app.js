const $ = (id) => document.getElementById(id);
let lastDraft = "";

function showOverlay(msg) { $("overlay-msg").textContent = msg; $("overlay").classList.remove("hidden"); }
function hideOverlay() { $("overlay").classList.add("hidden"); }

async function api(name, ...args) {
  return await window.pywebview.api[name](...args);
}

window.addEventListener("pywebviewready", async () => {
  const eng = await api("check_engine");
  if (!eng.ok) {
    const b = $("engine-banner");
    b.textContent = "Claude engine not ready. Open Terminal, run `claude`, and log in with your Claude account, then reopen this app.";
    b.classList.remove("hidden");
  }
});

$("fetch-btn").onclick = async () => {
  const url = $("url").value.trim();
  if (!url) return;
  showOverlay("Fetching job description...");
  const r = await api("fetch_jd", url);
  hideOverlay();
  if (r.ok) { $("jd").value = r.jd; }
  else { alert(r.error + "\n\nPaste the job description manually instead."); }
};

function renderScore(r) {
  const color = r.score >= 85 ? "var(--good)" : "var(--warn)";
  let html = `<span class="score-num" style="color:${color}">${r.score}</span> / 100 ATS match`;
  if (r.missing_keywords && r.missing_keywords.length) {
    html += `<div class="note">Still missing keywords:</div>`;
    html += r.missing_keywords.slice(0, 12).map(k => `<span class="pill">${k}</span>`).join("");
  }
  if (r.repeated_words && r.repeated_words.length) {
    html += `<div class="note">Overused words toned down next round: ${r.repeated_words.join(", ")}</div>`;
  }
  $("score-box").innerHTML = html;
}

async function runGenerate(feedback) {
  const cv = $("cv").value, jd = $("jd").value;
  showOverlay("Generating and scoring. This runs a few passes to reach 85+...");
  const r = await api("generate", cv, jd, feedback || "", lastDraft);
  hideOverlay();
  if (!r.ok) { alert(r.error); return; }
  lastDraft = r.cv;
  $("draft").value = r.cv;
  renderScore(r);
  $("step-result").classList.remove("hidden");
  $("step-result").scrollIntoView({ behavior: "smooth" });
}

$("generate-btn").onclick = () => { lastDraft = ""; runGenerate(""); };
$("regen-btn").onclick = () => {
  lastDraft = $("draft").value;  // respect manual edits as the base
  runGenerate($("feedback").value);
};

$("export-btn").onclick = async () => {
  showOverlay("Exporting PDF...");
  const r = await api("export_pdf", $("draft").value);
  hideOverlay();
  $("export-msg").textContent = r.ok ? `Saved to ${r.path}` : `Error: ${r.error}`;
};
