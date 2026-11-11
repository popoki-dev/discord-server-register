const passwordForm = document.getElementById("password-form");
passwordForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(passwordForm, ".form-error", "");
  showFormMessage(passwordForm, ".form-success", "");
  const fd = new FormData(passwordForm);
  if (fd.get("new_password") !== fd.get("confirm")) {
    showFormMessage(passwordForm, ".form-error", "New passwords do not match.");
    return;
  }
  const btn = passwordForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const res = await api("/api/auth/password", {
      method: "POST",
      body: { current_password: fd.get("current_password"), new_password: fd.get("new_password") },
    });
    passwordForm.reset();
    showFormMessage(passwordForm, ".form-success", res.message);
  } catch (err) {
    showFormMessage(passwordForm, ".form-error", err.message);
  } finally {
    btn.disabled = false;
  }
});
