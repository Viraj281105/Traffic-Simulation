import type { ReactNode } from "react";
import {
  Bookmark,
  ClipboardList,
  FlaskConical,
  GitCompareArrows,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useNavIndicator } from "../ui/useNavIndicator";
import {
  VIEW_ROUTES,
  followLink,
  navigate,
  type RoutedView,
} from "../../routing";
import { RESEARCH_TABS, type Section, type ViewMode } from "./sections";

const MAIN_TABS: {
  view: RoutedView;
  section: Section;
  label: string;
  icon: LucideIcon;
}[] = [
  {
    view: "comparative",
    section: "compare",
    label: "Compare",
    icon: GitCompareArrows,
  },
  { view: "history", section: "saved", label: "Saved", icon: Bookmark },
  { view: "planner", section: "plan", label: "Plan", icon: ClipboardList },
  {
    view: "research",
    section: "research",
    label: "Research lab",
    icon: FlaskConical,
  },
];

/** The sections, with a sliding indicator under the current one. The
 *  Research lab asks a signed-out visitor to sign in first. The Admin
 *  tab is only rendered for admin users. */
export function MainNav({
  section,
  requireAuth,
  isAdmin,
}: {
  section: Section;
  requireAuth: (action: () => void) => void;
  isAdmin: boolean;
}) {
  const ref = useNavIndicator<HTMLElement>(section);
  return (
    <nav className="header-tabs" aria-label="Main" ref={ref}>
      {MAIN_TABS.map((tab) => (
        <ViewTab
          key={tab.view}
          view={tab.view}
          current={section === tab.section}
          icon={tab.icon}
          onIntercept={
            tab.section === "research" || tab.section === "plan"
              ? (e, href) => {
                  e.preventDefault();
                  requireAuth(() => {
                    navigate(href);
                  });
                }
              : undefined
          }
        >
          {tab.label}
        </ViewTab>
      ))}
      {isAdmin && (
        <ViewTab view="admin" current={section === "admin"} icon={ShieldCheck}>
          Admin
        </ViewTab>
      )}
    </nav>
  );
}

export function ResearchNav({ viewMode }: { viewMode: ViewMode }) {
  const ref = useNavIndicator<HTMLElement>(viewMode);
  return (
    <nav className="sub-nav" aria-label="Research tools" ref={ref}>
      {RESEARCH_TABS.map((tab) => (
        <ViewTab key={tab.view} view={tab.view} current={tab.view === viewMode}>
          {tab.label}
        </ViewTab>
      ))}
    </nav>
  );
}

/** Client-side navigation for a same-document link, leaving modified clicks
 *  (new tab/window) to the browser. */
function ViewTab({
  view,
  current: isActive,
  children,
  icon: Icon,
  onIntercept,
}: {
  view: RoutedView;
  current: boolean;
  children: ReactNode;
  icon?: LucideIcon;
  onIntercept?: (e: React.MouseEvent, href: string) => void;
}) {
  const href = VIEW_ROUTES[view];
  return (
    <a
      href={href}
      className={`tab-btn ${isActive ? "active" : ""}`}
      aria-current={isActive ? "page" : undefined}
      onClick={(event) => {
        if (onIntercept) {
          onIntercept(event, href);
        } else {
          followLink(event, href);
        }
      }}
    >
      {Icon && <Icon size={15} aria-hidden="true" className="tab-icon" />}
      {children}
    </a>
  );
}
