// Shared helpers. All user-supplied text is inserted with textContent, never innerHTML.

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    window.location.href = "/login";
  }
  if (!res.ok) {
    const err = new Error(errorMessage(data) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function errorMessage(data) {
  if (!data || data.detail === undefined) return null;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => {
      const field = (d.loc || []).filter((p) => p !== "body").join(".");
      const msg = (d.msg || "").replace(/^Value error, /, "");
      return field ? `${field}: ${msg}` : msg;
    }).join("; ");
  }
  return null;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function isHttpUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch { return false; }
}

// The API sends every time in UTC. Show it in the viewer's own time zone, with the zone named.
const VIEWER_TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;
// (dateStyle/timeStyle can't be combined with timeZoneName, so the parts are listed.)
const DATE_PARTS = { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" };
const localFormat = new Intl.DateTimeFormat(undefined, { ...DATE_PARTS, timeZoneName: "short" });
const utcFormat = new Intl.DateTimeFormat(undefined, { ...DATE_PARTS, timeZone: "UTC" });

function formatDate(iso) {
  return iso ? localFormat.format(new Date(iso)) : "—";
}

// A <time> element in the viewer's zone, with the UTC time in its tooltip.
function timeEl(iso, attrs = {}) {
  if (!iso) return el("span", { ...attrs, text: "—" });
  const d = new Date(iso);
  return el("time", { ...attrs, datetime: d.toISOString(), title: `${utcFormat.format(d)} UTC`, text: localFormat.format(d) });
}

function setTimeZoneNote() {
  for (const node of document.querySelectorAll("[data-timezone-note]")) {
    node.textContent = `Times are shown in your time zone (${VIEWER_TIME_ZONE}). Hover a time to see it in UTC.`;
  }
}
document.addEventListener("DOMContentLoaded", setTimeZoneNote);
setTimeZoneNote();

function formatNumber(n) {
  return typeof n === "number" ? n.toLocaleString() : "—";
}

let toastTimer;
function toast(message, kind = "info") {
  const t = document.getElementById("toast");
  t.textContent = message;
  t.className = `toast toast-${kind}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}

function showFormMessage(form, selector, message) {
  const node = form.querySelector(selector);
  if (!node) return;
  node.textContent = message || "";
  node.hidden = !message;
}

document.getElementById("logout-btn")?.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  window.location.href = "/login";
});
