// Landing-page auth modal behaviour (markup and styles in index.html and
// src/landing/index.css). A same-origin file rather than an inline script or
// on* attributes because the production CSP is script-src 'self' (see
// templates/default.conf.template), which blocks both. Loaded at the end of
// <body>, so the modal markup already exists.
(function () {
  var overlay = document.getElementById("authOverlay");
  var modal = document.getElementById("authModal");
  if (!overlay || !modal) return;

  var lastFocus = null;

  // Dialog semantics; hidden from assistive technology and the Tab order
  // while closed (the overlay is only made transparent, not removed).
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "authTitle");
  overlay.inert = true;

  function openAuthModal() {
    lastFocus = document.activeElement;
    overlay.inert = false;
    overlay.classList.add("open");
    var email = document.getElementById("email");
    if (email) email.focus();
  }

  function closeAuthModal() {
    overlay.classList.remove("open");
    overlay.inert = true;
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  function switchAuthTab(tab) {
    var isLogin = tab === "login";
    document.getElementById("tabLogin").classList.toggle("active", isLogin);
    document.getElementById("tabRegister").classList.toggle("active", !isLogin);
    document.getElementById("authTitle").textContent = isLogin
      ? "Welcome Back"
      : "Create Account";
    document.getElementById("authSubtitle").textContent = isLogin
      ? "Sign in to access your simulation"
      : "Create a new account";
    document.getElementById("nameGroup").style.display = isLogin
      ? "none"
      : "flex";
    document.getElementById("forgotPassGroup").style.display = isLogin
      ? "flex"
      : "none";
    document.getElementById("submitBtn").textContent = isLogin
      ? "Sign In"
      : "Sign Up";
  }

  // Backdrop click closes; clicks inside the modal do not.
  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) closeAuthModal();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && overlay.classList.contains("open")) {
      closeAuthModal();
    }
  });

  document
    .getElementById("authClose")
    .addEventListener("click", closeAuthModal);

  modal.querySelectorAll("[data-auth-tab]").forEach(function (button) {
    button.addEventListener("click", function () {
      switchAuthTab(button.getAttribute("data-auth-tab"));
    });
  });

  // Placeholder actions (password reset, social sign-in) keep their notices.
  modal.querySelectorAll("[data-auth-notice]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      event.preventDefault();
      alert(el.getAttribute("data-auth-notice"));
    });
  });

  document.getElementById("authForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var email = document.getElementById("email").value;
    alert("Form submitted for: " + email);
    closeAuthModal();
  });

  // Called by the landing page's Login button (src/landing/App.tsx).
  window.openAuthModal = openAuthModal;
  window.closeAuthModal = closeAuthModal;
})();
