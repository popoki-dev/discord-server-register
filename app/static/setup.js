const setupForm = document.getElementById("setup-form");
setupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(setupForm, ".form-error", "");
  const fd = new FormData(setupForm);
  if (fd.get("password") !== fd.get("confirm")) {
    showFormMessage(setupForm, ".form-error", "Passwords do not match.");
    return;
  }
  const btn = setupForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api("/api/auth/setup", { method: "POST", body: { full_name: fd.get("full_name"), password: fd.get("password") } });
    window.location.href = "/";
  } catch (err) {
    showFormMessage(setupForm, ".form-error", err.message);
    btn.disabled = false;
  }
});
