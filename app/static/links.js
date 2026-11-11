const grid = document.getElementById("links-grid");
const emptyMsg = document.getElementById("links-empty");
const search = document.getElementById("search");
const categoryFilter = document.getElementById("category-filter");

const modal = document.getElementById("submit-modal");
const form = document.getElementById("submit-form");
const inviteInput = form.elements.invite;
const checkBtn = document.getElementById("check-btn");
const submitBtn = document.getElementById("submit-btn");
const preview = document.getElementById("server-preview");

// The invite text that last passed "Check" (and is not a duplicate). Submit is only enabled for it.
let checkedInvite = null;

// ---------- list ----------

function linkCard(link) {
  const icon = link.icon_url
    ? el("img", { class: "server-icon", src: link.icon_url, alt: "", loading: "lazy" })
    : el("div", { class: "server-icon placeholder", text: (link.guild_name || "?").charAt(0).toUpperCase() });

  const source = isHttpUrl(link.source)
    ? el("a", { href: link.source, target: "_blank", rel: "noopener noreferrer nofollow", text: link.source })
    : el("span", { text: link.source });

  return el("article", { class: "card link-card" },
    el("div", { class: "link-head" },
      icon,
      el("div", { class: "link-title" },
        el("h3", { text: link.guild_name }),
        el("span", { class: "muted small", text: `${formatNumber(link.member_count)} members` }),
      ),
      el("span", { class: "badge", text: link.category }),
    ),
    el("p", { class: "link-desc", text: link.description }),
    el("div", { class: "link-foot" },
      el("span", { class: "muted small" }, "Source: ", source),
      el("a", { class: "btn btn-primary btn-sm", href: link.invite_url, target: "_blank", rel: "noopener noreferrer", text: "Join" }),
    ),
  );
}

async function loadLinks() {
  const params = new URLSearchParams();
  if (search.value.trim()) params.set("q", search.value.trim());
  if (categoryFilter.value) params.set("category", categoryFilter.value);
  try {
    const links = await api(`/api/links?${params}`);
    grid.replaceChildren(...links.map(linkCard));
    emptyMsg.textContent = params.toString() ? "No links match your filters." : "No links yet. Be the first to submit one!";
    emptyMsg.hidden = links.length > 0;
  } catch (err) {
    toast(err.message, "error");
  }
}

let searchTimer;
search.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadLinks, 250); });
categoryFilter.addEventListener("change", loadLinks);

async function loadCategories() {
  const categories = await api("/api/links/categories");
  for (const c of categories) {
    categoryFilter.append(el("option", { value: c, text: c }));
    form.elements.category.append(el("option", { value: c, text: c }));
  }
}

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
  form.elements.category.focus();
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
      ? el("div", { class: "error small strong", text: "This server is already registered. Duplicate entries are not allowed." })
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
      body: { category: fd.get("category"), invite: checkedInvite, description: fd.get("description"), source: fd.get("source") },
    });
    modal.close();
    toast("Link submitted!", "success");
    loadLinks();
  } catch (err) {
    showFormMessage(form, ".form-error", err.message);
    submitBtn.disabled = err.status === 409; // duplicate: keep disabled
  }
});

loadCategories().then(loadLinks).catch((err) => toast(err.message, "error"));
