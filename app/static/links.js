const tbody = document.getElementById("links-body");
const emptyMsg = document.getElementById("links-empty");
const countMsg = document.getElementById("result-count");
const filters = document.getElementById("filters");
// Admins see every link plus the submitter filter/columns and the action buttons. Other users see
// only their own links. The server enforces both: the list is scoped per user, admin endpoints check the role.
const isAdmin = document.getElementById("links-table").dataset.admin === "true";

const modal = document.getElementById("submit-modal");
const form = document.getElementById("submit-form");
const inviteInput = form.elements.invite;
const checkBtn = document.getElementById("check-btn");
const submitBtn = document.getElementById("submit-btn");
const preview = document.getElementById("server-preview");

// The invite text that last passed "Check" (and is not a duplicate). Submit is only enabled for it.
let checkedInvite = null;

// ---------- list ----------

function serverCell(link) {
  const icon = link.icon_url
    ? el("img", { class: "server-icon sm", src: link.icon_url, alt: "", loading: "lazy" })
    : el("div", { class: "server-icon sm placeholder", text: (link.name || "?").charAt(0).toUpperCase() });
  return el("div", { class: "server-cell" },
    icon,
    el("div", {},
      el("span", { class: "strong", text: link.name }),
      link.removed ? el("span", { class: "badge badge-rejected", text: "deleted" }) : null,
      isAdmin ? el("div", { class: "mono small muted", text: link.guild_id, title: "Server ID" }) : null,
      link.expires_at ? el("div", { class: "warn small", text: `Invite expires ${formatDate(link.expires_at)}` }) : null,
    ),
  );
}

function statusBadge(link) {
  return link.joined
    ? el("span", { class: "badge badge-approved", text: "Joined" })
    : el("span", { class: "badge", text: "Unjoined" });
}

function linkRow(link) {
  const source = isHttpUrl(link.source)
    ? el("a", { href: link.source, target: "_blank", rel: "noopener noreferrer nofollow", text: link.source })
    : el("span", { text: link.source });

  return el("tr", { class: link.removed ? "row-deleted" : null },
    el("td", {}, serverCell(link)),
    el("td", { class: "small desc-cell", text: link.description || "—" }),
    el("td", { class: "right nowrap", text: formatNumber(link.member_count) }),
    el("td", { class: "right nowrap", text: formatNumber(link.online_count) }),
    el("td", { class: "small source-cell" }, source),
    isAdmin ? el("td", { class: "status-cell" }, statusBadge(link)) : null,
    el("td", { class: "small nowrap", text: formatDate(link.register_time) }),
    isAdmin ? el("td", {},
      el("div", { text: link.register_account.full_name || "—" }),
      el("div", { class: "small muted", text: link.register_account.email }),
    ) : null,
    isAdmin ? el("td", { class: "right" }, linkActions(link, {
      admin: true,
      onDeleted: loadLinks,
      onRestored: loadLinks,
      // Keep the Status column in step with the Joined/Unjoined toggle.
      onJoinedChange: (row) => row.querySelector(".status-cell").replaceChildren(statusBadge(link)),
    })) : null,
  );
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
  if (fd.get("q").trim()) params.set("q", fd.get("q").trim());
  if (fd.get("submitter_id")) params.set("submitter_id", fd.get("submitter_id"));
  if (fd.get("date_from")) params.set("date_from", dayStart(fd.get("date_from")));
  if (fd.get("date_to")) params.set("date_to", dayStart(fd.get("date_to"), 1)); // inclusive of the "to" day
  if (fd.get("joined")) params.set("joined", fd.get("joined")); // admin-only filter
  params.set("deletion", fd.get("deletion"));
  return params.toString();
}

function filtersAreDefault() {
  const fd = new FormData(filters);
  return !fd.get("q").trim() && !fd.get("submitter_id") && !fd.get("date_from") && !fd.get("date_to")
    && (fd.get("joined") ?? "all") === "all" && fd.get("deletion") === "active";
}

async function loadLinks() {
  const fd = new FormData(filters);
  if (fd.get("date_from") && fd.get("date_to") && fd.get("date_from") > fd.get("date_to")) {
    toast("“Submitted from” must be on or before “Submitted to”", "error");
    return;
  }
  try {
    const links = await api(`/api/links?${queryString()}`);
    tbody.replaceChildren(...links.map(linkRow));
    emptyMsg.textContent = !filtersAreDefault() ? "No links match these filters."
      : isAdmin ? "No links yet." : "You haven't submitted any links yet.";
    emptyMsg.hidden = links.length > 0;
    countMsg.textContent = `${links.length} link${links.length === 1 ? "" : "s"}`;
  } catch (err) {
    toast(err.message, "error");
  }
}

async function loadSubmitters() {
  const select = filters.elements.submitter_id;
  if (!select) return;
  for (const s of await api("/api/admin/submitters")) {
    select.append(el("option", { value: s.id, text: s.full_name ? `${s.full_name} (${s.email})` : s.email }));
  }
}

filters.addEventListener("change", (e) => { if (e.target.name !== "q") loadLinks(); });
filters.addEventListener("reset", () => setTimeout(loadLinks)); // after the form clears
filters.addEventListener("submit", (e) => e.preventDefault());
let searchTimer;
filters.elements.q.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadLinks, 250); });

// ---------- submit modal ----------

function resetCheck() {
  checkedInvite = null;
  submitBtn.disabled = true;
  preview.hidden = true;
  preview.replaceChildren();
}

function openModal() {
  form.reset();
  resetCheck();
  showFormMessage(form, ".form-error", "");
  modal.showModal();
  inviteInput.focus();
}

document.getElementById("open-submit").addEventListener("click", openModal);
modal.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => modal.close()));
inviteInput.addEventListener("input", resetCheck);

function renderPreview(info) {
  const icon = info.icon_url
    ? el("img", { class: "server-icon lg", src: info.icon_url, alt: "" })
    : el("div", { class: "server-icon lg placeholder", text: info.name.charAt(0).toUpperCase() });

  const stats = el("div", { class: "muted small" },
    `${formatNumber(info.member_count)} members · ${formatNumber(info.online_count)} online`);

  preview.className = `preview ${info.already_registered ? "preview-dup" : "preview-ok"}`;
  preview.replaceChildren(...[
    el("div", { class: "link-head" },
      icon,
      el("div", { class: "link-title" }, el("h3", { text: info.name }), stats),
    ),
    info.description ? el("p", { class: "small", text: info.description }) : null,
    el("div", { class: "muted small", text: `Server ID: ${info.guild_id}` }),
    info.expires_at ? el("div", { class: "warn small", text: `⚠ This invite expires on ${formatDate(info.expires_at)}. Consider using a permanent invite.` }) : null,
    info.already_registered
      ? el("div", { class: "error small strong", text: info.removed
          ? "This server was removed by an administrator and cannot be submitted again."
          : "This server is already registered. Duplicate entries are not allowed." })
      : el("div", { class: "ok small strong", text: "✓ Valid invite — ready to submit." }),
  ].filter(Boolean));
  preview.hidden = false;
}

checkBtn.addEventListener("click", async () => {
  const invite = inviteInput.value.trim();
  showFormMessage(form, ".form-error", "");
  if (!invite) { showFormMessage(form, ".form-error", "Enter an invite link first."); return; }
  resetCheck();
  checkBtn.disabled = true;
  checkBtn.textContent = "Checking…";
  try {
    const info = await api("/api/links/check", { method: "POST", body: { invite } });
    renderPreview(info);
    if (!info.already_registered && inviteInput.value.trim() === invite) {
      checkedInvite = invite;
      submitBtn.disabled = false;
    }
  } catch (err) {
    preview.className = "preview preview-dup";
    preview.replaceChildren(el("div", { class: "error small strong", text: err.message }));
    preview.hidden = false;
  } finally {
    checkBtn.disabled = false;
    checkBtn.textContent = "Check";
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(form, ".form-error", "");
  const fd = new FormData(form);
  if (fd.get("invite").trim() !== checkedInvite) {
    showFormMessage(form, ".form-error", "Please check the invite link first.");
    return;
  }
  submitBtn.disabled = true;
  try {
    await api("/api/links", {
      method: "POST",
      body: { invite: checkedInvite, source: fd.get("source") },
    });
    modal.close();
    toast("Link submitted!", "success");
    loadLinks();
  } catch (err) {
    showFormMessage(form, ".form-error", err.message);
    submitBtn.disabled = err.status === 409; // duplicate: keep disabled
  }
});

loadSubmitters().then(loadLinks).catch((err) => toast(err.message, "error"));
