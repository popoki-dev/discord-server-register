const loginForm = document.getElementById("login-form");
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showFormMessage(loginForm, ".form-error", "");
  const btn = loginForm.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const fd = new FormData(loginForm);
    const user = await api("/api/auth/login", { method: "POST", body: { email: fd.get("email"), password: fd.get("password") } });
    // First sign-in: the user sets their name and a new password before anything else.
    window.location.href = user.needs_setup ? "/setup" : "/";
  } catch (err) {
    showFormMessage(loginForm, ".form-error", err.message);
  } finally {
    btn.disabled = false;
  }
});
