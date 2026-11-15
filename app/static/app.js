"use strict";
/* ------------------------------------------------------------------ i18n */
const I18N = {
  de: {
    subtitle: "Dateien verlustfrei in Video oder Audio einbetten und bit-genau wieder extrahieren",
    tab_encode: "Encode", tab_decode: "Decode",
    src_title: "Quellmedium", src_pick: "Video oder Audio wählen / hierher ziehen",
    files_title: "Dateien", files_pick: "Eine oder mehrere Dateien wählen / hierher ziehen",
    opt_title: "Optionen", opt_password: "Passwort (optional)", opt_password_ph: "leer = ohne Verschlüsselung",
    opt_fps: "Träger-Frames pro Sekunde", opt_bits: "Bits pro Kanal (1–4)",
    opt_rs: "Reed-Solomon-Fehlerkorrektur (+14,3 %)", opt_vcodec: "Ausgabe-Codec", opt_aformat: "Ausgabeformat",
    cap_title: "Kapazität", cap_empty: "Zuerst ein Quellmedium hochladen.",
    cap_video: "Video", cap_audio: "Tonspur", cap_total: "Gesamt (aktuelle Einstellung)",
    cap_max: "Maximum (alle Frames, 4 Bit)", cap_frames: "Träger-Frames", cap_frame: "pro Frame",
    cap_payload: "Dateien (unkomprimiert, inkl. Overhead)",
    cap_fits: "Passt mit den gewählten Einstellungen.",
    cap_auto: "Passt nicht mit den gewählten Einstellungen – es werden automatisch mehr Frames/Bits genutzt.",
    cap_toolarge: "Unkomprimiert zu groß ({max} passen hinein). Kompression kann helfen, sonst schlägt das Encoding fehl.",
    btn_encode: "Encode starten", btn_decode: "Decode starten",
    uploading: "Upload", processing: "Verarbeitung",
    st_payload: "Payload (zstd/AES/RS)", st_plan: "Planung", st_audio: "Tonspur", st_video: "Video-Frames", st_files: "Dateien prüfen",
    info_type: "Typ", info_video: "Video", info_audio: "Audio", info_videoaudio: "Video + Ton",
    info_res: "Auflösung", info_fps: "Bildrate", info_frames: "Frames", info_duration: "Dauer",
    info_arate: "Ton", info_none: "–",
    res_title: "Ergebnis", res_download: "Herunterladen", res_note: "Die Datei wird nach dem Download auf dem Server gelöscht. Nicht verlustbehaftet neu kodieren!",
    res_bits: "Bits pro Kanal", res_k: "Träger-Frames/s", res_auto: "automatisch erhöht", res_capacity: "Kapazität",
    res_stream: "Eingebettete Daten", res_header: "Header", res_size: "Ausgabegröße", res_enc: "Verschlüsselung", res_rs: "Reed-Solomon",
    yes: "ja", no: "nein", segments: "Segmente",
    dec_src_title: "Konvertiertes Medium", dec_pick: "MKV / FLAC / WAV wählen / hierher ziehen",
    dec_pw_title: "Passwort", dec_pw_ph: "nur falls beim Encode gesetzt",
    dec_files: "Dateien", dec_timeline: "Timeline", dec_manifest: "Manifest & Parameter", dec_raw: "Rohdaten (JSON)",
    th_name: "Datei", th_size: "Größe", th_sha: "SHA-256", th_status: "Status", th_pos: "Position",
    valid: "gültig", invalid: "ungültig", download: "Download", downloaded: "heruntergeladen",
    frames_n: "{n} Frames", audio_s: "{s} s Ton",
    tl_header: "Header", tl_video: "Video-Frame", tl_audio: "Audio-Bereich",
    p_bits: "Bits pro Kanal", p_k: "Träger-Frames/s", p_seed: "Seed-Modus", p_enc: "Verschlüsselung", p_kdf: "Schlüsselableitung",
    p_rs: "Fehlerkorrektur", p_comp: "Kompression", p_stream: "Payload-Länge", p_video: "Video", p_audio: "Ton",
    p_hdr: "Header", p_hdrsha: "Header-SHA-256", p_rsfix: "RS-korrigierte Blöcke",
    seed_password: "aus Passwort", seed_fixed: "fest",
    err_capacity: "Zu wenig Kapazität: benötigt {needed}, maximal möglich {available}.",
    err_password_required: "Dieses Medium ist passwortgeschützt. Bitte Passwort eingeben.",
    err_wrong_password: "Falsches Passwort.",
    err_no_data: "In diesem Medium wurden keine eingebetteten Daten gefunden (evtl. verlustbehaftet neu kodiert?).",
    err_too_large: "Upload zu groß (Limit {limit} MB).",
    err_network: "Netzwerkfehler.",
    done_ok: "Alle {n} Dateien gültig (SHA-256 stimmt).", done_bad: "{bad} von {n} Dateien ungültig!",
    footer: "Läuft lokal · keine Speicherung · Uploads und Ergebnisse werden nach Verarbeitung bzw. Download gelöscht",
  },
  en: {
    subtitle: "Embed files losslessly into video or audio and extract them bit-exactly",
    tab_encode: "Encode", tab_decode: "Decode",
    src_title: "Source medium", src_pick: "Choose or drop a video or audio file",
    files_title: "Files", files_pick: "Choose or drop one or more files",
    opt_title: "Options", opt_password: "Password (optional)", opt_password_ph: "empty = no encryption",
    opt_fps: "Carrier frames per second", opt_bits: "Bits per channel (1–4)",
    opt_rs: "Reed-Solomon error correction (+14.3 %)", opt_vcodec: "Output codec", opt_aformat: "Output format",
    cap_title: "Capacity", cap_empty: "Upload a source medium first.",
    cap_video: "Video", cap_audio: "Audio track", cap_total: "Total (current settings)",
    cap_max: "Maximum (all frames, 4 bits)", cap_frames: "Carrier frames", cap_frame: "per frame",
    cap_payload: "Files (uncompressed, incl. overhead)",
    cap_fits: "Fits with the chosen settings.",
    cap_auto: "Does not fit with the chosen settings – more frames/bits will be used automatically.",
    cap_toolarge: "Too large uncompressed ({max} fit). Compression may help, otherwise encoding fails.",
    btn_encode: "Start encoding", btn_decode: "Start decoding",
    uploading: "Upload", processing: "Processing",
    st_payload: "Payload (zstd/AES/RS)", st_plan: "Planning", st_audio: "Audio track", st_video: "Video frames", st_files: "Verifying files",
    info_type: "Type", info_video: "Video", info_audio: "Audio", info_videoaudio: "Video + audio",
    info_res: "Resolution", info_fps: "Frame rate", info_frames: "Frames", info_duration: "Duration",
    info_arate: "Audio", info_none: "–",
    res_title: "Result", res_download: "Download", res_note: "The file is deleted from the server after download. Never re-encode it lossily!",
    res_bits: "Bits per channel", res_k: "Carrier frames/s", res_auto: "raised automatically", res_capacity: "Capacity",
    res_stream: "Embedded data", res_header: "Header", res_size: "Output size", res_enc: "Encryption", res_rs: "Reed-Solomon",
    yes: "yes", no: "no", segments: "segments",
    dec_src_title: "Converted medium", dec_pick: "Choose or drop MKV / FLAC / WAV",
    dec_pw_title: "Password", dec_pw_ph: "only if set during encoding",
    dec_files: "Files", dec_timeline: "Timeline", dec_manifest: "Manifest & parameters", dec_raw: "Raw data (JSON)",
    th_name: "File", th_size: "Size", th_sha: "SHA-256", th_status: "Status", th_pos: "Position",
    valid: "valid", invalid: "invalid", download: "Download", downloaded: "downloaded",
    frames_n: "{n} frames", audio_s: "{s} s audio",
    tl_header: "Header", tl_video: "Video frame", tl_audio: "Audio range",
    p_bits: "Bits per channel", p_k: "Carrier frames/s", p_seed: "Seed mode", p_enc: "Encryption", p_kdf: "Key derivation",
    p_rs: "Error correction", p_comp: "Compression", p_stream: "Payload length", p_video: "Video", p_audio: "Audio",
    p_hdr: "Header", p_hdrsha: "Header SHA-256", p_rsfix: "RS corrected blocks",
    seed_password: "from password", seed_fixed: "fixed",
    err_capacity: "Not enough capacity: needs {needed}, maximum possible {available}.",
    err_password_required: "This medium is password protected. Please enter the password.",
    err_wrong_password: "Wrong password.",
    err_no_data: "No embedded data found in this medium (re-encoded lossily?).",
    err_too_large: "Upload too large (limit {limit} MB).",
    err_network: "Network error.",
    done_ok: "All {n} files valid (SHA-256 matches).", done_bad: "{bad} of {n} files invalid!",
    footer: "Runs locally · no storage · uploads and results are deleted after processing or download",
  },
};
let lang = "de";
try { lang = localStorage.getItem("avdc-lang") || (navigator.language || "de").slice(0, 2); } catch (_) {}
if (!I18N[lang]) lang = "en";
const t = (k, vars) => {
  let s = (I18N[lang][k] ?? I18N.en[k] ?? k);
  if (vars) for (const [a, b] of Object.entries(vars)) s = s.replaceAll(`{${a}}`, b);
  return s;
};
const rerenders = [];
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll("[data-i18n-ph]").forEach(el => el.placeholder = t(el.dataset.i18nPh));
  document.querySelectorAll(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
  rerenders.forEach(fn => fn());
}
document.querySelectorAll(".lang button").forEach(b => b.onclick = () => {
  lang = b.dataset.lang;
  try { localStorage.setItem("avdc-lang", lang); } catch (_) {}
  applyLang();
});

/* ------------------------------------------------------------------ helpers */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function fmtBytes(n) {
  if (n == null) return "–";
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; let x = n;
  while (x >= 1024 && i < u.length - 1) { x /= 1024; i++; }
  return (i ? x.toFixed(x < 10 ? 2 : 1) : x) + " " + u[i];
}
const fmtTime = s => { s = Math.max(0, s); const m = Math.floor(s / 60); return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`; };
let CONFIG = { max_upload_mb: 2048 };
fetch("/api/config").then(r => r.json()).then(c => CONFIG = c).catch(() => {});

function errText(detail) {
  if (!detail) return t("err_network");
  const d = typeof detail === "string" ? { message: detail } : detail;
  const key = "err_" + d.code;
  if (I18N[lang][key]) return t(key, { needed: fmtBytes(d.needed), available: fmtBytes(d.available), limit: CONFIG.max_upload_mb });
  return d.message || t("err_network");
}
function showMsg(el, kind, text) { el.innerHTML = text ? `<div class="msg ${kind}">${esc(text)}</div>` : ""; }
function setProgress(el, frac, label) {
  el.classList.remove("hidden");
  el.firstElementChild.style.width = (Math.max(0, Math.min(1, frac)) * 100).toFixed(1) + "%";
  el.lastElementChild.textContent = label;
}

function upload(url, formData, progEl) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";
    xhr.upload.onprogress = e => { if (e.lengthComputable) setProgress(progEl, e.loaded / e.total, `${t("uploading")} ${Math.round(100 * e.loaded / e.total)} %`); };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300) ? resolve(xhr.response) : reject(xhr.response?.detail || { code: "http", message: `HTTP ${xhr.status}` });
    xhr.onerror = () => reject({ code: "network" });
    xhr.send(formData);
  });
}
async function poll(jid, progEl) {
  for (;;) {
    const r = await fetch(`/api/job/${jid}`);
    const j = await r.json();
    if (!r.ok) throw j.detail;
    if (j.status === "done") return j;
    if (j.status === "error") throw j.error;
    const st = j.stage ? t("st_" + j.stage) : t("processing");
    setProgress(progEl, j.progress, `${st} ${Math.round(100 * j.progress)} %`);
    await new Promise(res => setTimeout(res, 500));
  }
}
function setupDrop(label, input, onFiles) {
  ["dragenter", "dragover"].forEach(ev => label.addEventListener(ev, e => { e.preventDefault(); label.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => label.addEventListener(ev, e => { e.preventDefault(); label.classList.remove("over"); }));
  label.addEventListener("drop", e => onFiles([...e.dataTransfer.files]));
  input.addEventListener("change", () => { onFiles([...input.files]); input.value = ""; });
}

/* ------------------------------------------------------------------ tabs */
document.querySelectorAll(".tab").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("hidden", p.id !== "tab-" + b.dataset.tab));
});

/* ================================================================== ENCODE */
const enc = { token: null, info: null, srcName: null, cap: null, files: [], busy: false };

function renderSrcInfo() {
  const el = $("srcInfo");
  if (!enc.info) { el.classList.add("hidden"); return; }
  const i = enc.info;
  const type = i.has_video && i.has_audio ? t("info_videoaudio") : i.has_video ? t("info_video") : t("info_audio");
  el.innerHTML = `<dl>
    <dt>${t("th_name")}</dt><dd>${esc(enc.srcName)}</dd>
    <dt>${t("info_type")}</dt><dd>${type}</dd>
    ${i.has_video ? `<dt>${t("info_res")}</dt><dd>${i.width}×${i.height}</dd>
      <dt>${t("info_fps")}</dt><dd>${i.fps.toFixed(3)}</dd><dt>${t("info_frames")}</dt><dd>${i.n_frames}</dd>` : ""}
    ${i.has_audio ? `<dt>${t("info_arate")}</dt><dd>${i.sample_rate} Hz · ${i.channels} ch</dd>` : ""}
    <dt>${t("info_duration")}</dt><dd>${fmtTime(i.duration)}</dd></dl>`;
  el.classList.remove("hidden");
  $("kRow").classList.toggle("hidden", !i.has_video);
  $("vcodecRow").classList.toggle("hidden", !i.has_video);
  $("aformatRow").classList.toggle("hidden", i.has_video);
  $("optK").max = Math.max(1, Math.ceil(i.fps || 1));
}

function estPayload() {
  // raw sizes + per-file overhead; RS expands by 255/223
  let n = enc.files.reduce((a, f) => a + f.size + 64 + (($("encPassword").value ? 16 * Math.ceil((f.size + 1) / 16777216) : 0)), 0);
  if ($("optRs").checked) n = Math.ceil(n / 223) * 255;
  return n;
}

function renderCap() {
  const box = $("capBox");
  if (!enc.cap) { box.className = "muted"; box.textContent = t("cap_empty"); return; }
  const c = enc.cap, need = estPayload();
  const frac = c.total_bytes ? need / c.total_bytes : 1;
  let cls = "", note = "", kind = "ok";
  if (need <= c.total_bytes) note = t("cap_fits");
  else if (need <= c.max_total_bytes) { cls = "warn"; kind = "warn"; note = t("cap_auto"); }
  else { cls = "bad"; kind = "err"; note = t("cap_toolarge", { max: fmtBytes(c.max_total_bytes) }); }
  box.className = "";
  box.innerHTML = `<dl class="kv cap">
    ${enc.info.has_video ? `<dt>${t("cap_video")}</dt><dd>${fmtBytes(c.video_bytes)} <span class="muted">(${c.carrier_frames} × ${fmtBytes(c.frame_bytes)})</span></dd>` : ""}
    ${enc.info.has_audio ? `<dt>${t("cap_audio")}</dt><dd>${fmtBytes(c.audio_bytes)}</dd>` : ""}
    <dt><b>${t("cap_total")}</b></dt><dd><b>${fmtBytes(c.total_bytes)}</b></dd>
    <dt>${t("cap_max")}</dt><dd>${fmtBytes(c.max_total_bytes)}</dd>
    <dt>${t("cap_payload")}</dt><dd>${fmtBytes(need)}</dd></dl>
    ${enc.files.length ? `<div class="bar ${cls}"><div style="width:${Math.min(100, frac * 100).toFixed(1)}%"></div></div>
    <div class="msg ${kind}">${esc(note)}</div>` : ""}`;
}

let capTimer = null;
function refreshCap() {
  clearTimeout(capTimer);
  if (!enc.token) { renderCap(); return; }
  capTimer = setTimeout(async () => {
    const q = new URLSearchParams({ token: enc.token, bits: $("optBits").value, k: $("optK").value || 1 });
    try {
      const r = await fetch(`/api/capacity?${q}`);
      if (r.ok) enc.cap = await r.json();
    } catch (_) {}
    renderCap();
  }, 150);
  renderCap();
}

function renderFiles() {
  $("fileList").innerHTML = enc.files.map((f, i) =>
    `<li><span title="${esc(f.name)}">${esc(f.name)}</span><span>${fmtBytes(f.size)} <button data-rm="${i}" title="remove">✕</button></span></li>`).join("");
  $("fileList").querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { enc.files.splice(+b.dataset.rm, 1); renderFiles(); });
  const tot = enc.files.reduce((a, f) => a + f.size, 0);
  $("filesTotal").textContent = enc.files.length ? `${enc.files.length} · ${fmtBytes(tot)}` : "";
  updateEncodeBtn();
  renderCap();
}
function updateEncodeBtn() { $("encodeBtn").disabled = enc.busy || !enc.token || !enc.files.length; }

async function onSource(files) {
  const f = files[0];
  if (!f || enc.busy) return;
  if (enc.token) fetch(`/api/job/${enc.token}`, { method: "DELETE" });
  Object.assign(enc, { token: null, info: null, cap: null, srcName: f.name });
  $("encResult").classList.add("hidden");
  showMsg($("encMsg"));
  renderSrcInfo(); renderCap(); updateEncodeBtn();
  const fd = new FormData(); fd.append("medium", f);
  try {
    const r = await upload("/api/probe", fd, $("srcProgress"));
    Object.assign(enc, { token: r.token, info: r.info, cap: r.capacity });
    $("srcProgress").classList.add("hidden");
    renderSrcInfo(); refreshCap();
  } catch (e) {
    $("srcProgress").classList.add("hidden");
    showMsg($("encMsg"), "err", errText(e));
  }
  updateEncodeBtn();
}
setupDrop($("srcDrop"), $("srcInput"), onSource);
setupDrop($("filesDrop"), $("filesInput"), fs => { enc.files.push(...fs); renderFiles(); });
["optBits", "optK"].forEach(id => $(id).addEventListener("input", refreshCap));
["optRs", "encPassword"].forEach(id => $(id).addEventListener("input", renderCap));

$("encodeBtn").onclick = async () => {
  enc.busy = true; enc.lastHasVideo = !!enc.info?.has_video; updateEncodeBtn();
  showMsg($("encMsg")); $("encResult").classList.add("hidden");
  const fd = new FormData();
  fd.append("token", enc.token);
  fd.append("password", $("encPassword").value);
  fd.append("k", $("optK").value || 1);
  fd.append("bits", $("optBits").value);
  fd.append("rs", $("optRs").checked);
  fd.append("video_codec", $("optVcodec").value);
  fd.append("audio_format", $("optAformat").value);
  enc.files.forEach(f => fd.append("files", f, f.name));
  try {
    const { job } = await upload("/api/encode", fd, $("encProgress"));
    const res = await poll(job, $("encProgress"));
    enc.lastResult = res;
    renderEncResult();
  } catch (e) {
    showMsg($("encMsg"), "err", errText(e));
  } finally {
    $("encProgress").classList.add("hidden");
    // the uploaded medium is consumed by the job either way
    Object.assign(enc, { token: null, info: null, cap: null, busy: false });
    renderSrcInfo(); renderCap(); updateEncodeBtn();
  }
};

function renderEncResult() {
  const res = enc.lastResult; if (!res) return;
  const r = res.report, el = $("encResult");
  el.innerHTML = `<h2>${t("res_title")}</h2><dl class="kv">
    <dt>${t("th_name")}</dt><dd>${esc(res.filename)}</dd>
    <dt>${t("res_size")}</dt><dd>${fmtBytes(r.output_bytes)}</dd>
    <dt>${t("res_bits")}</dt><dd>${r.bits}${r.auto_adjusted && r.bits !== r.requested.bits ? ` <span class="badge bad">${t("res_auto")}</span>` : ""}</dd>
    ${enc.lastHasVideo ? `<dt>${t("res_k")}</dt><dd>${r.k}${r.auto_adjusted && r.k !== r.requested.k ? ` <span class="badge bad">${t("res_auto")}</span>` : ""}</dd>` : ""}
    <dt>${t("res_stream")}</dt><dd>${fmtBytes(r.stream_bytes)} / ${fmtBytes(r.capacity_bytes)} (${r.segments_used} ${t("segments")})</dd>
    <dt>${t("res_header")}</dt><dd>${fmtBytes(r.header_bytes)} (${r.header_segments} ${t("segments")})</dd>
    <dt>${t("res_enc")}</dt><dd>${r.encrypted ? "AES-256-GCM" : t("no")}</dd>
    <dt>${t("res_rs")}</dt><dd>${r.rs ? "RS(255,223)" : t("no")}</dd></dl>
    <div class="actions"><a class="button" id="dlResult" href="${res.download}" download>${t("res_download")}</a></div>
    <div class="msg warn">${t("res_note")}</div>`;
  el.classList.remove("hidden");
}
rerenders.push(renderSrcInfo, renderCap, renderEncResult);

/* ================================================================== DECODE */
const dec = { file: null, result: null, job: null, downloaded: new Set() };
setupDrop($("decDrop"), $("decInput"), fs => {
  dec.file = fs[0] || null;
  $("decName").textContent = dec.file ? `${dec.file.name} · ${fmtBytes(dec.file.size)}` : "";
  $("decodeBtn").disabled = !dec.file;
});

$("decodeBtn").onclick = async () => {
  if (!dec.file) return;
  $("decodeBtn").disabled = true;
  showMsg($("decMsg")); $("decResult").classList.add("hidden");
  const fd = new FormData(); fd.append("medium", dec.file); fd.append("password", $("decPassword").value);
  try {
    const { job } = await upload("/api/decode", fd, $("decProgress"));
    const res = await poll(job, $("decProgress"));
    Object.assign(dec, { job, result: res.result, downloaded: new Set() });
    renderDecode();
  } catch (e) {
    showMsg($("decMsg"), "err", errText(e));
    if (e && (e.code === "password_required" || e.code === "wrong_password")) $("decPassword").focus();
  } finally {
    $("decProgress").classList.add("hidden");
    $("decodeBtn").disabled = !dec.file;
  }
};

const COLORS = ["#3a7bea", "#d9952a", "#2fa36b", "#c4458c", "#7a5af5", "#1aa3b8", "#c9572c", "#8a9a1f"];
const color = i => COLORS[i % COLORS.length];

function renderDecode() {
  const r = dec.result; if (!r) return;
  const n = r.files.length, bad = r.files.filter(f => !f.valid).length;
  showMsg($("decMsg"), bad ? "err" : "ok", bad ? t("done_bad", { bad, n }) : t("done_ok", { n }));
  const rate = r.timeline.rate || 1;
  $("decFiles").innerHTML = `<div class="tablewrap"><table><thead><tr>
    <th>${t("th_name")}</th><th>${t("th_size")}</th><th>${t("th_sha")}</th><th>${t("th_pos")}</th><th>${t("th_status")}</th><th></th></tr></thead><tbody>
    ${r.files.map(f => {
      const aSec = f.audio.reduce((a, [x, y]) => a + (y - x), 0) / rate;
      const pos = [f.frames.length ? t("frames_n", { n: f.frames.length }) : "", f.audio.length ? t("audio_s", { s: aSec.toFixed(1) }) : ""].filter(Boolean).join(" + ");
      const dl = dec.downloaded.has(f.index) ? `<span class="muted">${t("downloaded")}</span>` :
        f.available ? `<a class="button small" href="/api/extract/${dec.job}/${f.index}" data-dl="${f.index}" download>${t("download")}</a>` : "";
      return `<tr><td><span class="swatch" style="background:${color(f.index)}"></span>${esc(f.name)}</td>
        <td>${fmtBytes(f.size)}</td>
        <td class="hash" title="${esc(f.sha256_actual || "")}">${esc(f.sha256)}</td>
        <td>${pos || "–"}${f.rs_corrected_blocks ? `<div class="muted">RS: ${f.rs_corrected_blocks}</div>` : ""}</td>
        <td><span class="badge ${f.valid ? "ok" : "bad"}">${f.valid ? "✓ " + t("valid") : "✗ " + t("invalid")}</span>${f.error ? `<div class="muted">${esc(f.error)}</div>` : ""}</td>
        <td>${dl}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  $("decFiles").querySelectorAll("[data-dl]").forEach(a => a.addEventListener("click", () => {
    setTimeout(() => { dec.downloaded.add(+a.dataset.dl); renderDecode(); }, 300);
  }));
  renderTimeline();
  const p = r.params, yes = t("yes"), no = t("no");
  $("decParams").innerHTML = `<dl class="kv">
    <dt>${t("th_name")}</dt><dd>${esc(r.source || "–")}</dd>
    ${p.video ? `<dt>${t("p_video")}</dt><dd>${p.video.w}×${p.video.h} · ${(p.video.fps[0] / p.video.fps[1]).toFixed(3)} fps · ${p.video.frames} Frames</dd>` : ""}
    ${p.audio ? `<dt>${t("p_audio")}</dt><dd>${p.audio.rate} Hz · ${p.audio.ch} ch · ${fmtTime(p.audio.samples / p.audio.rate)}</dd>` : ""}
    <dt>${t("p_bits")}</dt><dd>${p.bits}</dd>
    ${p.video ? `<dt>${t("p_k")}</dt><dd>${p.k}</dd>` : ""}
    <dt>${t("p_seed")}</dt><dd>${t("seed_" + p.seed_mode)}</dd>
    <dt>${t("p_comp")}</dt><dd>${esc(p.compression)}</dd>
    <dt>${t("p_enc")}</dt><dd>${p.enc ? esc(p.enc) : no}</dd>
    ${p.kdf ? `<dt>${t("p_kdf")}</dt><dd>${esc(p.kdf.name)}</dd>` : ""}
    <dt>${t("p_rs")}</dt><dd>${r.header.flags & 2 ? esc(p.rs) : no}</dd>
    <dt>${t("p_stream")}</dt><dd>${fmtBytes(p.stream_len)}</dd>
    <dt>${t("p_hdr")}</dt><dd>${fmtBytes(r.header.header_bytes)} · ${p.hdr_segs} ${t("segments")}</dd>
    <dt>${t("p_hdrsha")}</dt><dd class="hash">${esc(r.header.header_sha256)} ✓</dd>
    ${r.header.rs_corrected_blocks ? `<dt>${t("p_rsfix")}</dt><dd>${r.header.rs_corrected_blocks}</dd>` : ""}
    </dl>`;
  $("decRaw").textContent = JSON.stringify({ source: r.source, params: p, header: r.header, files: r.files }, null, 2);
  $("decResult").classList.remove("hidden");
}

function renderTimeline() {
  const r = dec.result; const tl = r.timeline;
  const W = 1000, L = 150, R = 10, rowH = 22, top = 8, axisH = 24;
  const dur = tl.duration || 1, x = s => L + (W - L - R) * (s / dur);
  const rows = [{ label: t("tl_header"), color: "var(--muted)", frames: tl.header.frames || [], audio: tl.header.audio || [] },
    ...r.files.map(f => ({ label: f.name, color: color(f.index), frames: f.frames, audio: f.audio }))];
  const fw = tl.fps ? Math.max(1.5, (W - L - R) / (dur * tl.fps)) : 2;
  let svg = "";
  rows.forEach((row, i) => {
    const y = top + i * rowH;
    const lbl = row.label.length > 22 ? row.label.slice(0, 21) + "…" : row.label;
    svg += `<text x="0" y="${y + 15}">${esc(lbl)}</text>`;
    svg += `<rect x="${L}" y="${y + 3}" width="${W - L - R}" height="${rowH - 6}" fill="var(--track)" rx="3"/>`;
    for (const [a, b] of row.audio) {
      svg += `<rect x="${x(a / tl.rate)}" y="${y + 11}" width="${Math.max(1.5, x(b / tl.rate) - x(a / tl.rate))}" height="${rowH - 14}" fill="${row.color}" opacity=".55"><title>${t("tl_audio")}: ${fmtTime(a / tl.rate)}–${fmtTime(b / tl.rate)}</title></rect>`;
    }
    for (const f of row.frames) {
      svg += `<rect x="${x(f / tl.fps)}" y="${y + 3}" width="${fw}" height="${row.audio.length ? 8 : rowH - 6}" fill="${row.color}"><title>${t("tl_video")} #${f} @ ${fmtTime(f / tl.fps)}</title></rect>`;
    }
  });
  const yA = top + rows.length * rowH + 4;
  const ticks = 8;
  for (let i = 0; i <= ticks; i++) {
    const s = dur * i / ticks;
    svg += `<line x1="${x(s)}" x2="${x(s)}" y1="${top}" y2="${yA}" stroke="var(--line)"/>`;
    svg += `<text x="${x(s)}" y="${yA + 14}" text-anchor="${i === 0 ? "start" : i === ticks ? "end" : "middle"}">${fmtTime(s)}</text>`;
  }
  const H = yA + axisH;
  $("decTimeline").innerHTML = `<div class="timeline"><svg viewBox="0 0 ${W} ${H}" role="img">${svg}</svg></div>
    <div class="legend"><span><span class="swatch" style="background:var(--accent)"></span>${t("tl_video")} (▮)</span>
    <span><span class="swatch" style="background:var(--accent);opacity:.55"></span>${t("tl_audio")} (▬)</span></div>`;
}
rerenders.push(renderDecode);

applyLang();
