const body = document.getElementById("users-body");
const emptyMsg = document.getElementById("users-empty");
const tabs = document.querySelectorAll("#status-tabs .tab");
let currentStatus = "";

function statusBadge(status) {
  return el("span", { class: `badge badge-${status}`, text: status });
}

function actionButtons(user) {
  if (user.is_admin) return el("span", { class: "muted small", text: "Administrator" });
  const wrap = el("div", { class: "actions" });
  if (user.status !== "approved") {
    wrap.append(el("button", { class: "btn btn-sm btn-primary", type: "button", text: "Approve", onclick: () => setStatus(user, "approve") }));
  }
  if (user.status !== "rejected") {
    wrap.append(el("button", { class: "btn btn-sm btn-danger", type: "button", text: "Reject", onclick: () => setStatus(user, "reject") }));
  }
  return wrap;
}

async function setStatus(user, action) {
  if (action === "reject" && user.status === "approved"
      && !confirm(`Revoke access for ${user.email}? They will be signed out immediately.`)) return;
  try {
    await api(`/api/admin/users/${user.id}/${action}`, { method: "POST" });
    toast(`${user.email} ${action === "approve" ? "approved" : "rejected"}`, "success");
    refresh();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function loadCounts() {
  const users = await api("/api/admin/users");
  for (const s of ["pending", "approved", "rejected"]) {
    const n = users.filter((u) => u.status === s).length;
    document.querySelector(`[data-count="${s}"]`).textContent = n ? `(${n})` : "";
  }
}

async function loadUsers() {
  const qs = currentStatus ? `?status=${currentStatus}` : "";
  const users = await api(`/api/admin/users${qs}`);
  body.replaceChildren(...users.map((u) => el("tr", {},
    el("td", {}, u.needs_setup ? el("span", { class: "muted", text: "Not signed in yet" }) : u.full_name),
    el("td", { text: u.email }),
    el("td", {}, statusBadge(u.status)),
    el("td", { class: "small nowrap" }, timeEl(u.created_at)),
    el("td", { class: "small nowrap" }, timeEl(u.reviewed_at)),
    el("td", { class: "right" }, actionButtons(u)),
  )));
  emptyMsg.hidden = users.length > 0;
}

function refresh() {
  Promise.all([loadUsers(), loadCounts()]).catch((err) => toast(err.message, "error"));
}

tabs.forEach((t) => t.addEventListener("click", () => {
  currentStatus = t.dataset.status;
  tabs.forEach((x) => x.classList.toggle("active", x === t));
  refresh();
}));

refresh();

// ---------- add user ----------
const addModal = document.getElementById("add-user-modal");
const addForm = document.getElementById("add-user-form");

document.getElementById("add-user-btn").addEventListener("click", () => {
  addForm.reset();
  showFormMessage(addForm, ".form-error", "");
  addModal.showModal();
});
addModal.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => addModal.close()));

addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(addForm, ".form-error", "");
  const fd = new FormData(addForm);
  if (fd.get("password") !== fd.get("confirm")) {
    showFormMessage(addForm, ".form-error", "Passwords do not match.");
    return;
  }
  const btn = addForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const user = await api("/api/admin/users", { method: "POST", body: { email: fd.get("email"), password: fd.get("password") } });
    addModal.close();
    toast(`Added ${user.email}. They can sign in now with the password you set.`, "success");
    refresh();
  } catch (err) {
    showFormMessage(addForm, ".form-error", err.message);
  } finally {
    btn.disabled = false;
  }
});
