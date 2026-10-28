import { useEffect, useState } from "react";

/** Light/dark preference, shared by the landing page and the dashboard for
 *  the browser tab's session. Light unless the visitor chose dark. */
const THEME_STORAGE_KEY = "signals-theme";

export function storedThemeIsLight(): boolean {
  return sessionStorage.getItem(THEME_STORAGE_KEY) !== "dark";
}

/** Puts the theme's class on the document root (tokens.css keys off it). */
export function applyThemeClasses(isLight: boolean): void {
  document.documentElement.classList.toggle("light", isLight);
  document.documentElement.classList.toggle("dark", !isLight);
}

/** The current theme, applied to the document and remembered for the tab. */
export function useThemeMode() {
  const [isLight, setIsLight] = useState(storedThemeIsLight);

  useEffect(() => {
    applyThemeClasses(isLight);
    sessionStorage.setItem(THEME_STORAGE_KEY, isLight ? "light" : "dark");
  }, [isLight]);

  const toggleTheme = () => {
    setIsLight((current) => !current);
  };

  return { isLight, toggleTheme };
}
