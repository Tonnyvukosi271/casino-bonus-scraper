"use strict";
// Reads casinos.json (schema documented in README). All scraped text is written
// with textContent, never innerHTML, so it cannot inject markup.

const DATA_URL = "casinos.json";
const STATUS_LABELS = { complete: "Complete", partial: "Partial", not_found: "Not found", failed: "Failed" };
const RECORD_FIELDS = ["welcome_bonus", "wagering_requirement", "minimum_deposit"];
const $ = (id) => document.getElementById(id);
let casinos = [];

function isRecord(record) {
  return record !== null && typeof record === "object" && !Array.isArray(record) &&
    typeof record.casino_name === "string" &&
    RECORD_FIELDS.every((field) => record[field] === null || typeof record[field] === "string") &&
    typeof record.source_url === "string" &&
    Object.hasOwn(STATUS_LABELS, record.extraction_status) &&
    typeof record.notes === "string";
}

function isDataset(data) {
  return data !== null && typeof data === "object" && !Array.isArray(data) &&
    Array.isArray(data.casinos) && data.casinos.every(isRecord) &&
    typeof data.source_url === "string" &&
    (data.last_updated === null || typeof data.last_updated === "string");
}

function showMessage(title, body, kind) {
  const box = $("message");
  box.className = "message" + (kind === "error" ? " error" : "");
  box.replaceChildren();
  if (kind === "loading") {
    const spin = document.createElement("div");
    spin.className = "spinner";
    box.append(spin);
  }
  const strong = document.createElement("strong");
  strong.textContent = title;
  box.append(strong, document.createTextNode(body || ""));
  box.hidden = false;
  $("table-wrap").hidden = true;
}

function safeHref(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch (e) {
    return null;
  }
}

function isComplete(c) {
  return ["welcome_bonus", "wagering_requirement", "minimum_deposit"].every((k) => c[k]);
}

function cell(label, value, className) {
  const td = document.createElement("td");
  td.dataset.label = label;
  if (className) td.className = className;
  if (value) {
    td.textContent = value;
  } else {
    const span = document.createElement("span");
    span.className = "na";
    span.textContent = "Not available";
    td.append(span);
  }
  return td;
}

function renderRow(c) {
  const tr = document.createElement("tr");
  tr.append(cell("Casino", c.casino_name, "name"),
            cell("Welcome bonus", c.welcome_bonus),
            cell("Wagering", c.wagering_requirement),
            cell("Min. deposit", c.minimum_deposit));

  const status = document.createElement("td");
  status.dataset.label = "Status";
  const badge = document.createElement("span");
  const key = STATUS_LABELS[c.extraction_status] ? c.extraction_status : "failed";
  badge.className = "badge " + key;
  badge.textContent = STATUS_LABELS[key];
  status.append(badge);
  if (c.notes) {
    const note = document.createElement("span");
    note.className = "note";
    note.textContent = c.notes;
    status.append(note);
  }

  const src = document.createElement("td");
  src.dataset.label = "Source";
  const href = safeHref(c.source_url);
  if (href) {
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = new URL(href).hostname;
    src.append(a);
  } else {
    src.textContent = "No valid link";
  }
  tr.append(status, src);
  return tr;
}

function renderTable() {
  const q = $("search").value.trim().toLowerCase();
  const shown = casinos.filter((c) => !q || Object.values(c).join(" ").toLowerCase().includes(q));
  if (casinos.length === 0) {
    return showMessage("No verified records yet", "Run scraper.py to populate casinos.json, then refresh.");
  }
  if (shown.length === 0) {
    return showMessage("No matches", "Nothing matches your search.");
  }
  $("message").hidden = true;
  $("rows").replaceChildren(...shown.map(renderRow));
  $("table-wrap").hidden = false;
}

function renderSummary(data) {
  $("stat-total").textContent = casinos.length;
  $("stat-complete").textContent = casinos.filter(isComplete).length;
  const when = data.last_updated ? new Date(data.last_updated) : null;
  $("stat-updated").textContent = when && !isNaN(when) ? when.toLocaleString() : "Never";
  const href = safeHref(data.source_url);
  const box = $("source-text");
  box.replaceChildren();
  if (href) {
    box.append(document.createTextNode("All records were extracted from "));
    const a = document.createElement("a");
    a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = href;
    box.append(a, document.createTextNode("."));
  } else {
    box.textContent = "No source recorded yet.";
  }
}

async function loadData() {
  const btn = $("refresh");
  btn.disabled = true;
  showMessage("Loading data…", "", "loading");
  try {
    const res = await fetch(DATA_URL + "?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    if (!isDataset(data)) throw new Error("Unexpected JSON structure or invalid casino record");
    casinos = data.casinos;
    renderSummary(data);
    renderTable();
  } catch (err) {
    casinos = [];
    $("stat-total").textContent = $("stat-complete").textContent = $("stat-updated").textContent = "–";
    showMessage("Could not load casinos.json", err.message + ". If you opened this file directly, serve it with: python -m http.server", "error");
  } finally {
    btn.disabled = false;
  }
}

$("refresh").addEventListener("click", loadData);
$("search").addEventListener("input", () => { if (casinos.length) renderTable(); });
loadData();
