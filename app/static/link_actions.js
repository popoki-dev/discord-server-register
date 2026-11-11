// Icon action buttons for a link row, shown to admins only: Joined/Unjoined, Copy, Delete and Restore.

const ICONS = {
  copy: [
    ["rect", { x: 9, y: 9, width: 13, height: 13, rx: 2 }],
    ["path", { d: "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" }],
  ],
  trash: [
    ["path", { d: "M3 6h18" }],
    ["path", { d: "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" }],
    ["path", { d: "M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" }],
    ["path", { d: "M10 11v6M14 11v6" }],
  ],
  joined: [ // user with a check mark
    ["path", { d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" }],
    ["circle", { cx: 9, cy: 7, r: 4 }],
    ["path", { d: "M16 11l2 2 4-4" }],
  ],
  unjoined: [ // user with a plus
    ["path", { d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" }],
    ["circle", { cx: 9, cy: 7, r: 4 }],
    ["path", { d: "M19 8v6M22 11h-6" }],
  ],
  check: [["path", { d: "M20 6L9 17l-5-5" }]],
  restore: [ // counter-clockwise arrow
    ["path", { d: "M3 12a9 9 0 1 0 3-6.7L3 8" }],
    ["path", { d: "M3 3v5h5" }],
  ],
};

function icon(name) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  for (const [k, v] of Object.entries({
    viewBox: "0 0 24 24", width: 18, height: 18, fill: "none", stroke: "currentColor",
    "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true",
  })) svg.setAttribute(k, v);
  for (const [tag, attrs] of ICONS[name]) {
    const shape = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) shape.setAttribute(k, v);
    svg.append(shape);
  }
  return svg;
}

function iconButton(name, label, onclick, extraClass = "") {
  const btn = el("button", { class: `icon-action ${extraClass}`.trim(), type: "button", title: label, "aria-label": label, onclick });
  btn.append(icon(name));
  return btn;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Fallback where the async clipboard API is unavailable (e.g. plain http on a LAN IP).
    const area = el("textarea", { readonly: true, class: "offscreen" });
    area.value = text;
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    if (!ok) throw new Error("Copy failed");
  }
}

function copyButton(link) {
  const btn = iconButton("copy", "Copy invite link", async () => {
    try {
      await copyText(link.invite_url);
      toast(`Copied ${link.invite_url}`, "success");
      btn.replaceChildren(icon("check"));
      btn.classList.add("on");
      setTimeout(() => { btn.replaceChildren(icon("copy")); btn.classList.remove("on"); }, 1500);
    } catch {
      toast("Could not copy to clipboard", "error");
    }
  });
  return btn;
}

function joinedButton(link, onChange = () => {}) {
  const label = link.joined ? "Joined — click to mark as unjoined" : "Not joined — click to mark as joined";
  const btn = iconButton(link.joined ? "joined" : "unjoined", label, async () => {
    btn.disabled = true;
    try {
      const updated = await api(`/api/admin/links/${link.id}/joined`, { method: link.joined ? "DELETE" : "POST" });
      link.joined = updated.joined;
      const row = btn.closest("tr");
      btn.replaceWith(joinedButton(link, onChange));
      onChange(row);
      toast(`${link.name} marked as ${link.joined ? "joined" : "unjoined"}`, "success");
    } catch (err) {
      btn.disabled = false;
      toast(err.message, "error");
    }
  }, link.joined ? "on" : "");
  btn.setAttribute("aria-pressed", link.joined ? "true" : "false");
  return btn;
}

function deleteButton(link, onDeleted) {
  return iconButton("trash", "Delete link", async () => {
    if (!confirm(`Delete "${link.name}"?\n\nIt will be removed from the list and this server can never be submitted again.`)) return;
    try {
      await api(`/api/admin/links/${link.id}`, { method: "DELETE" });
      toast(`Deleted ${link.name}`, "success");
      onDeleted();
    } catch (err) {
      toast(err.message, "error");
    }
  }, "danger");
}

function restoreButton(link, onRestored) {
  return iconButton("restore", "Restore link", async () => {
    if (!confirm(`Restore "${link.name}"?\n\nIt will be listed again.`)) return;
    try {
      await api(`/api/admin/links/${link.id}/restore`, { method: "POST" });
      toast(`Restored ${link.name}`, "success");
      onRestored();
    } catch (err) {
      toast(err.message, "error");
    }
  }, "restore");
}

// Active links: Joined/Unjoined, Copy, Delete. Deleted links: Copy, Restore.
function linkActions(link, { admin = false, onDeleted = () => {}, onRestored = () => {}, onJoinedChange } = {}) {
  if (!admin) return null;
  if (link.removed) {
    return el("div", { class: "icon-actions" }, copyButton(link), restoreButton(link, onRestored));
  }
  return el("div", { class: "icon-actions" },
    joinedButton(link, onJoinedChange),
    copyButton(link),
    deleteButton(link, onDeleted),
  );
}
