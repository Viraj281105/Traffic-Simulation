import { useEffect } from "react";
import { UrbanFlowLockup } from "../ui/UrbanFlowLogo";
import { StatusState } from "../ui/StatusState";
import { VIEW_ROUTES, followLink } from "../../routing";
import { applyThemeClasses, storedThemeIsLight } from "../../theme/mode";

export function NotFound({ path }: { path: string }) {
  useEffect(() => {
    applyThemeClasses(storedThemeIsLight());
  }, []);

  const home = VIEW_ROUTES.comparative;
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <a className="brand" href="/" data-testid="link-brand">
            <UrbanFlowLockup size={30} />
          </a>
        </div>
      </header>
      <main className="app-main full-screen not-found" role="main">
        <StatusState
          tone="empty"
          headingLevel={1}
          title="Page not found"
          actions={
            <>
              <a
                href={home}
                className="pb-btn pb-primary"
                onClick={(event) => {
                  followLink(event, home);
                }}
              >
                Start a comparison
              </a>
              <a href="/" className="pb-btn pb-secondary">
                Back to the landing page
              </a>
            </>
          }
        >
          <p>
            There is no page at <code>{path}</code>.
          </p>
        </StatusState>
      </main>
    </div>
  );
}
