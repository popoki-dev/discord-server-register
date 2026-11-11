const body = document.getElementById("links-body");
const emptyMsg = document.getElementById("links-empty");
const countMsg = document.getElementById("result-count");
const filters = document.getElementById("filters");

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Fallback for browsers/contexts without the async clipboard API (e.g. plain http on a LAN IP).
    const area = el("textarea", { readonly: true, style: "position:fixed;opacity:0" });
    area.value = text;
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    if (!ok) throw new Error("Copy failed");
  }
}

function serverCell(link) {
  const icon = link.icon_url
    ? el("img", { class: "server-icon sm", src: link.icon_url, alt: "", loading: "lazy" })
    : el("div", { class: "server-icon sm placeholder", text: (link.name || "?").charAt(0).toUpperCase() });
  return el("div", { class: "server-cell" },
    icon,
    el("div", {},
      el("a", { href: link.invite_url, target: "_blank", rel: "noopener noreferrer", text: link.name }),
      link.removed ? el("span", { class: "badge badge-rejected", text: "removed" }) : null,
    ),
  );
}

function actions(link) {
  const copyBtn = el("button", {
    class: "btn btn-sm", type: "button", text: "Copy", title: link.invite_url,
    onclick: async () => {
      try {
        await copyText(link.invite_url);
        toast(`Copied ${link.invite_url}`, "success");
      } catch {
        toast("Could not copy to clipboard", "error");
      }
    },
  });
  const deleteBtn = link.removed ? null : el("button", {
    class: "btn btn-sm btn-danger", type: "button", text: "Delete",
    onclick: () => deleteLink(link),
  });
  return el("div", { class: "actions" }, copyBtn, deleteBtn);
}

function joinedCell(link) {
  if (link.joined) return el("span", { class: "badge badge-approved", text: "✓ Joined" });
  if (link.removed) return el("span", { class: "muted small", text: "—" });
  const btn = el("button", {
    class: "btn btn-sm btn-primary", type: "button", text: "Joined", title: "Mark this server as joined",
    onclick: async () => {
      btn.disabled = true;
      try {
        await api(`/api/admin/links/${link.id}/joined`, { method: "POST" });
        link.joined = true;
        btn.replaceWith(joinedCell(link));
        toast(`Marked ${link.name} as joined`, "success");
      } catch (err) {
        btn.disabled = false;
        toast(err.message, "error");
      }
    },
  });
  return btn;
}

async function deleteLink(link) {
  if (!confirm(`Delete "${link.name}"?\n\nIt will be removed from the list and this server can never be submitted again.`)) return;
  try {
    await api(`/api/admin/links/${link.id}`, { method: "DELETE" });
    toast(`Deleted ${link.name}`, "success");
    loadLinks();
  } catch (err) {
    toast(err.message, "error");
  }
}

// Date inputs are local calendar days; send the matching UTC instants.
function dayStart(value, offsetDays = 0) {
  const d = new Date(`${value}T00:00:00`);
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString();
}

function queryString() {
  const fd = new FormData(filters);
  const params = new URLSearchParams();
  if (fd.get("submitter_id")) params.set("submitter_id", fd.get("submitter_id"));
  if (fd.get("date_from")) params.set("date_from", dayStart(fd.get("date_from")));
  if (fd.get("date_to")) params.set("date_to", dayStart(fd.get("date_to"), 1)); // inclusive of the "To" day
  if (fd.get("include_removed")) params.set("include_removed", "true");
  return params.toString();
}

async function loadLinks() {
  const fd = new FormData(filters);
  if (fd.get("date_from") && fd.get("date_to") && fd.get("date_from") > fd.get("date_to")) {
    toast("“From” must be on or before “To”", "error");
    return;
  }
  try {
    const links = await api(`/api/admin/links?${queryString()}`);
    body.replaceChildren(...links.map((link) => el("tr", { class: link.removed ? "row-deleted" : null },
      el("td", {}, serverCell(link)),
      el("td", { class: "mono small", text: link.guild_id }),
      el("td", { class: "right nowrap", text: formatNumber(link.member_count) }),
      el("td", { text: link.register_account.full_name || "—" }),
      el("td", { class: "small", text: link.register_account.email }),
      el("td", { class: "small nowrap", text: formatDate(link.register_time) }),
      el("td", {}, joinedCell(link)),
      el("td", { class: "right" }, actions(link)),
    )));
    emptyMsg.hidden = links.length > 0;
    countMsg.textContent = `${links.length} link${links.length === 1 ? "" : "s"}`;
  } catch (err) {
    toast(err.message, "error");
  }
}

async function loadSubmitters() {
  const select = filters.elements.submitter_id;
  for (const s of await api("/api/admin/submitters")) {
    select.append(el("option", { value: s.id, text: s.full_name ? `${s.full_name} (${s.email})` : s.email }));
  }
}

filters.addEventListener("change", loadLinks);
filters.addEventListener("reset", () => setTimeout(loadLinks)); // after the form clears
filters.addEventListener("submit", (e) => e.preventDefault());

loadSubmitters().then(loadLinks).catch((err) => toast(err.message, "error"));
