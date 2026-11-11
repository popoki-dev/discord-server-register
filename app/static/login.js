const tabs = document.querySelectorAll(".tab[data-tab]");
const panels = document.querySelectorAll("[data-panel]");

function selectTab(name) {
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  panels.forEach((p) => { p.hidden = p.dataset.panel !== name; });
}
tabs.forEach((t) => t.addEventListener("click", () => selectTab(t.dataset.tab)));

const loginForm = document.getElementById("login-form");
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(loginForm, ".form-error", "");
  const btn = loginForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const fd = new FormData(loginForm);
    await api("/api/auth/login", { method: "POST", body: { email: fd.get("email"), password: fd.get("password") } });
    window.location.href = "/";
  } catch (err) {
    showFormMessage(loginForm, ".form-error", err.message);
  } finally {
    btn.disabled = false;
  }
});

const registerForm = document.getElementById("register-form");
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(registerForm, ".form-error", "");
  showFormMessage(registerForm, ".form-success", "");
  const fd = new FormData(registerForm);
  if (fd.get("password") !== fd.get("confirm")) {
    showFormMessage(registerForm, ".form-error", "Passwords do not match.");
    return;
  }
  const btn = registerForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const res = await api("/api/auth/register", { method: "POST", body: { email: fd.get("email"), password: fd.get("password") } });
    registerForm.reset();
    showFormMessage(registerForm, ".form-success", res.message);
  } catch (err) {
    showFormMessage(registerForm, ".form-error", err.message);
  } finally {
    btn.disabled = false;
  }
});
