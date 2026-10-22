"use strict";

const app = document.getElementById("app");
let config = {};
let me = null;
let pollTimer = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const init = { credentials: "same-origin", ...opts };
  if (opts.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(opts.json);
  }
  const r = await fetch(path, init);
  const body = r.headers.get("content-type")?.includes("json") ? await r.json() : null;
  if (!r.ok) throw Object.assign(new Error(body?.detail || `Request failed (${r.status})`), { status: r.status });
  return body;
}

const ago = (ts) => {
  if (!ts) return "never";
  const s = Math.max(0, Math.round((me?.now ?? Date.now() / 1000) - ts));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
};

const helperOnline = () => me?.devices.some((d) => (me.now - d.last_seen) < 60);

function render(html) {
  app.innerHTML = html;
  for (const a of document.querySelectorAll("nav a")) {
    a.classList.toggle("on", a.getAttribute("href") === (location.hash || "#/"));
  }
}

function showError(el, err) {
  el.textContent = err.message;
  el.className = "err";
}

// ---------- routing ----------

async function route() {
  clearTimeout(pollTimer);
  const hash = location.hash || "#/";
  try {
    me = await api("/api/me");
  } catch (e) {
    me = null;
  }
  document.getElementById("nav").hidden = !me;
  if (!me) return loginPage();
  if (hash === "#/setup") return setupPage();
  if (hash === "#/profile") return profilePage();
  const m = hash.match(/^#\/job\/(\d+)$/);
  if (m) return jobPage(Number(m[1]));
  if (!me.has_profile || !me.devices.length) return setupPage();
  return homePage();
}

// ---------- sign in ----------

function loginPage() {
  render(`
    <h1>A resume rewritten for every job you apply to</h1>
    <p>Paste a job link. Your own Claude, Codex or Antigravity rewrites your resume from
      everything you've done, an ATS check scores it, and a second AI reviews it honestly.
      It keeps revising until the ATS score is above 85 and the review is 9 out of 10.</p>
    <p class="muted">It never invents experience. When the job asks for something your profile
      doesn't show, it asks you.</p>
    <div class="sheet">
      <div id="gbtn"></div>
      ${config.dev_login ? `
        <form id="dev">
          <label for="email">Email (local testing sign-in)</label>
          <input type="email" id="email" required autocomplete="email">
          <button class="primary">Sign in</button>
        </form>` : ""}
      <p id="msg" role="alert"></p>
    </div>`);
  const msg = document.getElementById("msg");
  if (config.google_client_id) {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.onload = () => {
      google.accounts.id.initialize({
        client_id: config.google_client_id,
        callback: async ({ credential }) => {
          try { await api("/api/auth/google", { json: { credential } }); route(); }
          catch (e) { showError(msg, e); }
        },
      });
      google.accounts.id.renderButton(document.getElementById("gbtn"), { theme: "outline", size: "large", text: "continue_with" });
    };
    document.head.appendChild(s);
  }
  document.getElementById("dev")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await api("/api/auth/dev", { json: { email: document.getElementById("email").value } }); route(); }
    catch (e) { showError(msg, e); }
  });
}

// ---------- setup ----------

function setupPage() {
  const linked = me.devices.length > 0;
  const engines = [...new Set(me.devices.flatMap((d) => d.engines))];
  const labels = { claude: "Claude Code", codex: "Codex", agy: "Antigravity" };
  render(`
    <h1>Set up once, then just paste job links</h1>
    <ol class="steps">
      <li class="${linked ? "done" : ""}">
        <div class="sheet">
          <h3>Link your computer</h3>
          <p class="muted small">The AI work runs on your computer with your own subscription.
            Install the helper, then link it with a one-time code.</p>
          ${me.devices.map((d) => `<p class="small">${d.engines.map((e) => esc(labels[e] || e)).join(", ") || "No AI tools found"}
              · last seen ${esc(ago(d.last_seen))}</p>`).join("")}
          <button type="button" class="secondary" id="code">${linked ? "Link another computer" : "Get a link code"}</button>
          <div id="codebox"></div>
        </div>
      </li>
      <li class="${linked ? "done" : ""}">
        <div class="sheet">
          <h3>Choose your AI</h3>
          ${engines.length ? `
            <select id="engine" aria-label="AI to use">
              ${engines.map((e) => `<option value="${esc(e)}" ${e === me.engine ? "selected" : ""}>${esc(labels[e] || e)}</option>`).join("")}
            </select>
            <p id="engmsg" class="small muted" role="status"></p>`
          : `<p class="muted small">Link your computer first. We'll list the AI tools it has.</p>`}
        </div>
      </li>
      <li class="${me.has_profile ? "done" : ""}">
        <div class="sheet">
          <h3>Build your profile</h3>
          <p class="muted small">Your resume probably shows 2 or 3 projects. Add everything else here,
            so each job gets the most relevant ones.</p>
          <form id="sources">
            <label for="resume">Current resume (PDF, DOCX or TXT)</label>
            <input type="file" id="resume" name="resume" accept=".pdf,.docx,.doc,.txt,.md" required>
            <label for="ai">Ask the AI chat you use most</label>
            <p class="small muted">Copy this into ChatGPT, Claude or Gemini, then paste its answer below.</p>
            <div class="code-line" style="white-space:pre-wrap">${esc(config.ai_prompt)}</div>
            <button type="button" class="secondary" id="copy" style="margin-top:8px">Copy prompt</button>
            <textarea id="ai" name="ai_paste" placeholder="Paste the AI's answer here"></textarea>
            <label for="gh">GitHub username (optional)</label>
            <input type="text" id="gh" name="github" autocomplete="off">
            <label for="li">LinkedIn data export .zip (optional)</label>
            <p class="small muted">LinkedIn → Settings → Data privacy → Get a copy of your data.</p>
            <input type="file" id="li" name="linkedin" accept=".zip">
            <button class="primary" ${linked ? "" : "disabled"}>Build my profile</button>
            ${linked ? "" : `<p class="small muted">Link your computer first; it does the building.</p>`}
            <p id="srcmsg" role="alert"></p>
          </form>
        </div>
      </li>
    </ol>`);

  document.getElementById("code").onclick = async () => {
    const { code } = await api("/api/devices/code", { method: "POST" });
    document.getElementById("codebox").innerHTML = `
      <p class="pair">${esc(code)}</p>
      <p class="small muted">On your computer, in the CV Tailor folder, run these two commands.
        The code works for 10 minutes.</p>
      <div class="code-line">python -m src.agent link ${esc(code)} --server ${esc(location.origin)}
python -m src.agent serve</div>
      <p class="small muted">Keep <b>serve</b> running while you use the site. This page updates when it connects.</p>`;
    const before = me.devices.length;
    const wait = async () => {
      me = await api("/api/me");
      if (me.devices.length > before) return setupPage();
      pollTimer = setTimeout(wait, 2000);
    };
    pollTimer = setTimeout(wait, 2000);
  };
  document.getElementById("copy").onclick = async (ev) => {
    await navigator.clipboard.writeText(config.ai_prompt);
    ev.target.textContent = "Copied";
  };
  document.getElementById("engine")?.addEventListener("change", async (ev) => {
    await api("/api/me", { method: "PUT", json: { engine: ev.target.value } });
    document.getElementById("engmsg").textContent = "Saved";
  });
  document.getElementById("sources").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = ev.target.querySelector("button.primary");
    btn.disabled = true;
    try {
      const { id } = await api("/api/profile/sources", { method: "POST", body: new FormData(ev.target) });
      location.hash = `#/job/${id}`;
    } catch (e) { showError(document.getElementById("srcmsg"), e); btn.disabled = false; }
  });
}

// ---------- profile ----------

async function profilePage() {
  const { profile } = await api("/api/profile");
  render(`
    <h1>Your profile</h1>
    <p class="muted">This is everything the AI is allowed to use. It never adds anything that
      isn't here. Fix anything that's wrong; answers you give to job questions are added under
      <b>user_answers</b>.</p>
    ${profile ? `
      <textarea class="code" id="pj" spellcheck="false" aria-label="Profile JSON">${esc(JSON.stringify(profile, null, 2))}</textarea>
      <button class="primary" id="save">Save profile</button>
      <p id="pmsg" role="status"></p>`
    : `<p>No profile yet. <a href="#/setup">Build your profile</a>.</p>`}`);
  document.getElementById("save")?.addEventListener("click", async () => {
    const msg = document.getElementById("pmsg");
    try {
      await api("/api/profile", { method: "PUT", json: { profile: JSON.parse(document.getElementById("pj").value) } });
      msg.textContent = "Saved"; msg.className = "ok";
    } catch (e) {
      showError(msg, e instanceof SyntaxError ? new Error(`That isn't valid JSON: ${e.message}`) : e);
    }
  });
}

// ---------- jobs ----------

const statusText = { queued: "Waiting for your computer", running: "Working", waiting: "Needs your answer", done: "Done", failed: "Failed" };

async function homePage() {
  const { jobs } = await api("/api/jobs");
  const tailored = jobs.filter((j) => j.kind === "tailor");
  render(`
    <h1>Which job are you applying to?</h1>
    <form id="new" class="sheet">
      <label for="url">Job link</label>
      <input type="url" id="url" placeholder="https://boards.greenhouse.io/…">
      <details style="margin-top:12px"><summary class="small muted">Link doesn't work? Paste the job description</summary>
        <textarea id="jd" aria-label="Job description"></textarea>
      </details>
      <button class="primary">Tailor my resume</button>
      ${helperOnline() ? "" : `<p class="small muted">Your computer's helper isn't connected. Jobs wait until you run <b>python -m src.agent serve</b>.</p>`}
      <p id="jmsg" role="alert"></p>
    </form>
    ${tailored.length ? `<h2>Your resumes</h2><ul class="jobs">${tailored.map((j) => `
      <li><a href="#/job/${j.id}">
        <span class="title">${esc(j.job_url || "Pasted job description")}</span>
        <span class="scores">${j.ats != null ? `ATS ${esc(j.ats)} · ${esc(j.review)}/10` : ""}</span>
        <span class="status ${esc(j.status)}">${esc(statusText[j.status])}</span>
        <span class="small muted">${esc(new Date(j.created_at * 1000).toLocaleDateString())}</span>
      </a></li>`).join("")}</ul>`
    : `<p class="muted">Your tailored resumes will show up here.</p>`}`);
  document.getElementById("new").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const { id } = await api("/api/jobs", { json: {
        job_url: document.getElementById("url").value, jd: document.getElementById("jd").value } });
      location.hash = `#/job/${id}`;
    } catch (e) { showError(document.getElementById("jmsg"), e); }
  });
}

function meter(name, value, max, line, pass) {
  const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100));
  return `<div class="meter">
    <span class="name">${esc(name)}</span>
    <span class="bar" role="img" aria-label="${esc(name)} ${esc(value)} of ${max}, needs ${pass}">
      <span class="fill ${value >= line ? "pass" : ""}" style="width:${pct(value)}%"></span>
      <span class="line" style="left:${pct(line)}%"></span>
    </span>
    <span class="val">${esc(value)}</span>
  </div>`;
}

function roundHtml(r) {
  const rev = r.review || {};
  const notes = [
    ...(rev.fabrications || []).map((f) => `<li class="fab">Not in your profile: ${esc(f)}</li>`),
    ...(rev.issues || []).map((i) => `<li>${esc(i)}</li>`),
  ];
  return `<li class="round">
    <span class="n">${esc(r.round)}</span>
    <div>
      ${meter("ATS", r.ats.score, 100, 86, "above 85")}
      ${meter("Review", rev.score, 10, 9, "9 or more")}
      ${notes.length ? `<details><summary class="small muted">Reviewer notes (${notes.length})</summary><ul class="notes">${notes.join("")}</ul></details>` : ""}
    </div>
  </li>`;
}

async function jobPage(id) {
  let job;
  try { job = await api(`/api/jobs/${id}`); }
  catch (e) { return render(`<h1>Job not found</h1><p><a href="#/">Back to your jobs</a></p>`); }
  // Keep typed-but-unsent answers across refreshes.
  const drafts = {};
  for (const t of document.querySelectorAll(".question textarea")) drafts[t.dataset.id] = t.value;

  const rounds = job.events.filter((e) => e.type === "round").map((e) => e.data);
  const logs = job.events.filter((e) => e.type === "log").map((e) => e.data.msg);
  const open = job.questions.filter((q) => q.answer == null);
  const live = !["done", "failed"].includes(job.status);
  const res = job.result || {};
  const isProfile = job.kind === "profile";

  render(`
    <p><a href="#/">← Your jobs</a></p>
    <h1>${isProfile ? "Building your profile" : esc(job.job_url ? new URL(job.job_url).hostname : "Pasted job")}</h1>
    <p><span class="status ${esc(job.status)}">${esc(statusText[job.status])}</span>
      ${job.status === "queued" ? `<span class="small muted"> · ${helperOnline() ? "your computer will pick it up in a moment" : "start the helper on your computer: python -m src.agent serve"}</span>` : ""}
      ${live && logs.length ? `<span class="small muted"> · ${esc(logs[logs.length - 1])}</span>` : ""}</p>

    ${job.status === "failed" ? `<p class="err">${esc(job.error || res.error || "Something went wrong.")}</p>` : ""}

    ${isProfile && job.status === "done" ? `<p class="ok">Profile ready.</p>
      <p><a href="#/profile">Check your profile</a> or <a href="#/">tailor your first resume</a>.</p>` : ""}

    ${open.length ? `<h2>The job asks for things your profile doesn't show</h2>
      <p class="muted small">Answer honestly. Your answers are saved to your profile. Leave blank to skip.</p>
      <form id="answers">${open.map((q) => `
        <div class="question"><p>${esc(q.text)}</p>
          <textarea data-id="${q.id}" aria-label="${esc(q.text)}">${esc(drafts[q.id] || "")}</textarea></div>`).join("")}
        <button class="primary">Send answers</button>
      </form>` : ""}

    ${job.status === "done" && !isProfile ? `
      <div class="verdict ${res.reached_target ? "" : "short"}">
        <strong>${res.reached_target ? "Ready to send" : "Best version after 6 rounds"}</strong>
        <p>ATS ${esc(res.ats?.score)} · review ${esc(res.review?.score)}/10${res.error ? ` · ${esc(res.error)}` : ""}</p>
        ${res.reached_target ? "" : `<p class="small muted">It didn't reach the target. The reviewer's notes below say what's missing; most of it is experience the job wants that your profile doesn't show.</p>`}
        ${job.has_pdf ? `<a class="primary" href="/api/jobs/${id}/pdf">Download PDF</a>` : ""}
      </div>` : ""}

    ${rounds.length ? `<h2>Rounds</h2>
      <p class="small muted">The dark line on each bar is the pass mark: ATS above 85, review 9 or more.</p>
      <ol class="rounds">${rounds.map(roundHtml).join("")}</ol>` : ""}

    ${job.jd ? `<h2>Job description</h2><div class="jd">${esc(job.jd)}</div>` : ""}`);

  document.getElementById("answers")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = {};
    for (const t of ev.target.querySelectorAll("textarea")) body[t.dataset.id] = t.value;
    await api(`/api/jobs/${id}/answers`, { json: body });
    jobPage(id);
  });
  // Don't refresh under someone typing an answer.
  if (live) pollTimer = setTimeout(async () => {
    if (document.activeElement?.closest(".question")) { pollTimer = setTimeout(() => jobPage(id), 4000); return; }
    me = await api("/api/me").catch(() => me);
    jobPage(id);
  }, 2000);
}

// ---------- boot ----------

document.getElementById("logout").onclick = async () => {
  await api("/api/auth/logout", { method: "POST" });
  location.hash = "#/";
  route();
};
window.addEventListener("hashchange", route);
api("/api/config").then((c) => { config = c; route(); });
