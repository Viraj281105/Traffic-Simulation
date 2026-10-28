import { useEffect, useRef, useState } from "react";
import { LogIn, Moon, Sun } from "lucide-react";
import { UrbanFlowLockup } from "../components/ui/UrbanFlowLogo";
import { RouteLoader } from "../components/ui/RouteLoader";
import { useThemeMode } from "../theme/mode";
import { SceneContext, ThemeContext } from "./scene/SceneContext";
import { useScene } from "./scene/sceneData";
import { Hero } from "./sections/Hero";
import { Story } from "./sections/Story";
import { CompareStudio } from "./sections/CompareStudio";
import { Evidence } from "./sections/Evidence";
import { Platform } from "./sections/Platform";
import { Developers, FinalCta, Limits } from "./sections/Closing";
import "./cinematic.css";

declare global {
  interface Window {
    openAuthModal: () => void;
  }
}

/** True while the header sits over one of the dark, full-bleed scenes, so it
 *  can switch to light-on-dark and the page reads as one continuous story. */
function useHeaderOnDark(): boolean {
  const [onDark, setOnDark] = useState(true);
  const raf = useRef(0);
  useEffect(() => {
    const check = () => {
      raf.current = 0;
      const line = 32;
      const dark = Array.from(
        document.querySelectorAll<HTMLElement>('[data-surface="dark"]'),
      ).some((el) => {
        const r = el.getBoundingClientRect();
        return r.top <= line && r.bottom >= line;
      });
      setOnDark((cur) => (cur === dark ? cur : dark));
    };
    const onScroll = () => {
      if (!raf.current) raf.current = requestAnimationFrame(check);
    };
    check();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, []);
  return onDark;
}

function App() {
  useEffect(() => {
    document.title = "UrbanFlow — Signal or roundabout?";
  }, []);
  const { isLight, toggleTheme } = useThemeMode();
  const scene = useScene();
  const onDark = useHeaderOnDark();

  return (
    <ThemeContext.Provider value={isLight ? "light" : "dark"}>
      <SceneContext.Provider value={scene}>
        <main className="site-shell cine">
          {/* The app's loader, for the first load of the page. */}
          <RouteLoader routeKey="/" />
          <header className={`top-nav${onDark ? " on-dark" : ""}`}>
            <a className="brand" href="#top" data-testid="link-brand">
              <UrbanFlowLockup size={30} />
              <span className="sr-only">Home</span>
            </a>
            <nav className="nav-links" aria-label="Primary navigation">
              <a href="#story" data-testid="link-compare">
                The story
              </a>
              <a href="#compare" data-testid="link-metrics">
                Compare
              </a>
              <a href="#platform" data-testid="link-platform">
                Platform
              </a>
              <a href="#developers" data-testid="link-developers">
                Developers
              </a>
              <button
                className="theme-button"
                type="button"
                onClick={toggleTheme}
                aria-label={
                  isLight ? "Switch to dark mode" : "Switch to light mode"
                }
                title={isLight ? "Dark mode" : "Light mode"}
                data-testid="button-theme-toggle"
              >
                <span className="theme-icon" key={isLight ? "moon" : "sun"}>
                  {isLight ? <Moon size={16} /> : <Sun size={16} />}
                </span>
              </button>
              <button
                type="button"
                className="header-signin"
                onClick={() => {
                  window.openAuthModal();
                }}
              >
                <LogIn size={15} aria-hidden="true" />
                Login
              </button>
            </nav>
          </header>

          <Hero />
          <div className="scene-fade" aria-hidden="true" />
          <Story />
          <CompareStudio />
          <Evidence />
          <Platform />
          <Developers />
          <Limits />
          <FinalCta />

          <footer className="footer">
            <div className="section-wrap footer-inner">
              <span>URBANFLOW — SIGNAL OR ROUNDABOUT, TESTED</span>
              <span>EVIDENCE FOR THE PEOPLE WHO DECIDE</span>
            </div>
          </footer>
        </main>
      </SceneContext.Provider>
    </ThemeContext.Provider>
  );
}

export default App;
