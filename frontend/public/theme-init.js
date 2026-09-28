// Applies the saved theme before the first paint, so neither document flashes
// the wrong palette while React loads. Light is the default (<html
// class="light"> in index.html and app.html); dark only when the visitor chose
// it, which the theme toggles store under "signals-theme". A same-origin file
// rather than an inline script because the production CSP is script-src 'self'.
try {
  if (sessionStorage.getItem("signals-theme") === "dark") {
    document.documentElement.classList.replace("light", "dark");
  }
} catch {
  // Storage unavailable: keep the light default.
}
