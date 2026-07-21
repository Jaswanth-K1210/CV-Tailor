const $ = (id) => document.getElementById(id);
let lastDraft = "";
let selectedEngine = "claude";

function showOverlay(msg) {
  $("overlay-msg").textContent = msg;
  $("overlay").classList.remove("hidden");
}
function hideOverlay() {
  $("overlay").classList.add("hidden");
}

async function api(name, ...args) {
  const result = await window.pywebview.api[name](...args);
  return result;
}

async function loadSettings() {
  const r = await api("get_settings");
  if (!r.ok) return;
  selectedEngine = r.engine;
  $("settings-model").value = r.model;
  $("settings-budget").value = r.budget_usd;
  $("engine-badge").textContent = r.engine_label + " \u00B7 " + r.model;
}

async function loadEngines() {
  const r = await api("get_engines");
  if (!r.ok) return;
  const list = $("engine-list");
  list.innerHTML = "";
  for (const eng of r.engines) {
    const div = document.createElement("div");
    div.className = "engine-option" + (eng.name === selectedEngine ? " selected" : "");
    const statusCls = eng.available ? "ok" : "fail";
    const statusText = eng.available ? "Ready \u00B7 " + eng.version : "Not found";
    div.innerHTML =
      '<div class="radio"></div>' +
      '<div class="info">' +
        '<div class="name">' + eng.label + '</div>' +
        '<div class="status ' + statusCls + '">' + statusText + '</div>' +
      '</div>';
    div.onclick = () => {
      list.querySelectorAll(".engine-option").forEach(e => e.classList.remove("selected"));
      div.classList.add("selected");
      selectedEngine = eng.name;
      $("settings-model").value = eng.default_model;
    };
    list.appendChild(div);
  }
}

function openSettings() {
  $("settings-overlay").classList.remove("hidden");
  $("test-result").classList.add("hidden");
  loadEngines();
}

function closeSettings() {
  $("settings-overlay").classList.add("hidden");
}

async function saveSettings() {
  const model = $("settings-model").value.trim();
  const budget = parseFloat($("settings-budget").value) || 0.10;
  const r = await api("save_settings", selectedEngine, model, budget);
  if (r.ok) {
    const engLabel = { claude: "Claude Code", gemini: "Gemini CLI", codex: "Codex CLI" };
    $("engine-badge").textContent = (engLabel[selectedEngine] || selectedEngine) + " \u00B7 " + model;
    closeSettings();
  }
}

async function testEngine() {
  const el = $("test-result");
  el.classList.remove("hidden", "ok", "fail");
  el.textContent = "Testing...";
  const r = await api("test_engine", selectedEngine);
  if (r.ok) {
    el.classList.add("ok");
    el.textContent = "Connected \u00B7 " + (r.version || "OK");
  } else {
    el.classList.add("fail");
    el.textContent = "Failed \u00B7 " + (r.error || "CLI not found");
  }
}

function renderScore(r) {
  const color = r.score >= 85 ? "var(--good)" : "var(--warn)";
  let html = '<span class="score-num" style="color:' + color + '">' + r.score + '</span> / 100 ATS match';
  if (r.missing_keywords && r.missing_keywords.length) {
    html += '<div class="note">Still missing keywords:</div>';
    html += r.missing_keywords.slice(0, 12).map(function(k) {
      return '<span class="pill">' + k + '</span>';
    }).join("");
  }
  if (r.repeated_words && r.repeated_words.length) {
    html += '<div class="note">Overused words: ' + r.repeated_words.join(", ") + '</div>';
  }
  $("score-box").innerHTML = html;
}

async function runGenerate(feedback) {
  const cv = $("cv").value, jd = $("jd").value;
  showOverlay("Generating and scoring\u2026 this runs a few passes to reach 85+");
  const r = await api("generate", cv, jd, feedback || "", lastDraft);
  hideOverlay();
  if (!r.ok) { alert(r.error); return; }
  lastDraft = r.cv;
  $("draft").value = r.cv;
  renderScore(r);
  $("step-result").classList.remove("hidden");
  $("step-result").scrollIntoView({ behavior: "smooth" });
  showOverlay("Running external ATS scorer for validation\u2026");
  const ext = await api("external_score", r.cv, jd);
  hideOverlay();
  if (ext.ok) {
    var extBox = $("external-score-box");
    if (extBox) {
      var eColor = ext.ats_score >= 70 ? "var(--good)" : ext.ats_score >= 40 ? "var(--warn)" : "var(--bad)";
      var ehtml = '<div class="ext-score"><span class="score-num" style="color:' + eColor + '">' + ext.ats_score + '</span> / 100 TF-IDF similarity';
      ehtml += ' &nbsp;|&nbsp; <span class="score-num" style="color:' + (ext.match_rate >= 70 ? "var(--good)" : "var(--warn)") + '">' + ext.match_rate + '%</span> JD keyword match</div>';
      if (ext.matched_keywords && ext.matched_keywords.length)
        ehtml += '<div class="note">Matched: ' + ext.matched_keywords.join(", ") + '</div>';
      if (ext.missing_keywords && ext.missing_keywords.length)
        ehtml += '<div class="note">Missing: ' + ext.missing_keywords.join(", ") + '</div>';
      if (ext.suggestions && ext.suggestions.length)
        ehtml += '<div class="note">' + ext.suggestions.join(" ") + '</div>';
      extBox.innerHTML = ehtml;
    }
  }
}

window.addEventListener("pywebviewready", async function() {
  await loadSettings();
  const eng = await api("check_engine");
  if (!eng.ok) {
    var b = $("engine-banner");
    b.textContent = "AI engine not ready. Open Settings (gear icon) to select and configure your engine.";
    b.classList.remove("hidden");
  }
});

$("settings-btn").onclick = openSettings;
$("settings-close").onclick = closeSettings;
$("settings-cancel").onclick = closeSettings;
$("settings-save").onclick = saveSettings;
$("test-engine-btn").onclick = testEngine;

$("fetch-btn").onclick = async function() {
  var url = $("url").value.trim();
  if (!url) return;
  showOverlay("Fetching job description\u2026");
  var r = await api("fetch_jd", url);
  hideOverlay();
  if (r.ok) { $("jd").value = r.jd; }
  else { alert(r.error + "\n\nPaste the job description manually instead."); }
};

$("generate-btn").onclick = function() { lastDraft = ""; runGenerate(""); };
$("regen-btn").onclick = function() {
  lastDraft = $("draft").value;
  runGenerate($("feedback").value);
};

$("export-btn").onclick = async function() {
  showOverlay("Exporting PDF\u2026");
  var r = await api("export_pdf", $("draft").value);
  hideOverlay();
  $("export-msg").textContent = r.ok ? "Saved to " + r.path : "Error: " + r.error;
};
