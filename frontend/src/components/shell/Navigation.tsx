import { Fragment } from "react";
import type { MouseEvent, ReactNode } from "react";
import { ArrowUpRight, ChevronRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useNavIndicator } from "../ui/useNavIndicator";
import {
  VIEW_ROUTES,
  followLink,
  navigate,
  type RoutedView,
} from "../../routing";
import {
  PRIMARY_SECTIONS,
  SECTIONS,
  sectionItems,
  type Section,
  type ViewMode,
} from "./sections";
import "./Navigation.css";

type RequireAuth = (action: () => void) => void;

/** The workflows, with a sliding indicator under the current one. Sections
 *  that need an account ask a signed-out visitor to sign in first. */
export function MainNav({
  section,
  requireAuth,
}: {
  section: Section;
  requireAuth: RequireAuth;
}) {
  const ref = useNavIndicator<HTMLElement>(section);
  return (
    <nav className="header-tabs" aria-label="Main" ref={ref}>
      {PRIMARY_SECTIONS.map((id) => {
        const def = SECTIONS[id];
        return (
          <NavLink
            key={id}
            view={def.home}
            current={section === id}
            icon={def.icon}
            requireAuth={def.requiresAuth ? requireAuth : undefined}
          >
            {def.label}
          </NavLink>
        );
      })}
    </nav>
  );
}

/** Utilities that are not part of a workflow: developer access (API tokens)
 *  for everyone and the admin panel for admins. One click from any page. */
export function UtilityNav({
  section,
  requireAuth,
  isAdmin,
}: {
  section: Section;
  requireAuth: RequireAuth;
  isAdmin: boolean;
}) {
  const ids: Section[] = isAdmin ? ["developer", "admin"] : ["developer"];
  return (
    <nav className="utility-nav" aria-label="Developer and admin">
      {ids.map((id) => {
        const def = SECTIONS[id];
        return (
          <NavLink
            key={id}
            view={def.home}
            current={section === id}
            icon={def.icon}
            className="utility-link"
            title={
              id === "developer"
                ? "Developer: API tokens for the Python client and scripts"
                : "Admin panel"
            }
            requireAuth={def.requiresAuth ? requireAuth : undefined}
          >
            <span className="utility-label">{def.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

/** A section's own pages, in labelled groups. On a page with no tab of its
 *  own (an experiment), `trail` names it after the tabs so the visitor
 *  still sees where they are. */
export function SectionNav({
  section,
  viewMode,
  trail,
}: {
  section: Section;
  viewMode: ViewMode;
  trail?: string;
}) {
  const def = SECTIONS[section];
  const active = trail ? `trail:${trail}` : viewMode;
  const ref = useNavIndicator<HTMLElement>(active);
  if (def.groups.length === 0) return null;
  return (
    <nav
      className="sub-nav"
      aria-label={
        section === "research" ? "Research tools" : "Experiment tools"
      }
      ref={ref}
    >
      {def.groups.map((group, i) => (
        <Fragment key={group.label ?? i}>
          {i > 0 && <span className="sub-nav__divider" aria-hidden="true" />}
          {group.label && (
            <span className="sub-nav__group" aria-hidden="true">
              {group.label}
            </span>
          )}
          {group.items.map((item) => (
            <NavLink
              key={item.view}
              view={item.view}
              current={!trail && item.view === viewMode}
              title={item.description}
            >
              {item.label}
            </NavLink>
          ))}
        </Fragment>
      ))}
      {trail && (
        <>
          <ChevronRight
            size={14}
            className="sub-nav__chevron"
            aria-hidden="true"
          />
          <span className="tab-btn sub-nav__trail" aria-current="page">
            {trail}
          </span>
        </>
      )}
    </nav>
  );
}

/** The other pages of a section, each with what it is for, at the end of a
 *  page: the next study or tool is one click away without going back to an
 *  overview. */
export function RelatedTools({
  section,
  viewMode,
}: {
  section: Section;
  viewMode: ViewMode;
}) {
  const others = sectionItems(section).filter(
    (item) => item.view !== viewMode && item.view !== "research",
  );
  if (others.length === 0) return null;
  const title =
    section === "research" ? "Other studies" : "Other experiment tools";
  return (
    <aside className="related-tools" aria-labelledby="related-tools-title">
      <h2 id="related-tools-title">{title}</h2>
      <ul>
        {others.map((item) => (
          <li key={item.view}>
            <a
              href={VIEW_ROUTES[item.view]}
              onClick={(event) => {
                followLink(event, VIEW_ROUTES[item.view]);
              }}
            >
              <span className="related-tools__label">
                {item.label}
                <ArrowUpRight size={14} aria-hidden="true" />
              </span>
              <span className="related-tools__body">{item.description}</span>
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/** A same-document link: client-side navigation for a plain left click,
 *  modified clicks (new tab/window) left to the browser. With requireAuth,
 *  a signed-out visitor signs in before it opens. */
function NavLink({
  view,
  current: isActive,
  children,
  icon: Icon,
  title,
  className = "",
  requireAuth,
}: {
  view: RoutedView;
  current: boolean;
  children: ReactNode;
  icon?: LucideIcon;
  title?: string;
  className?: string;
  requireAuth?: RequireAuth;
}) {
  const href = VIEW_ROUTES[view];
  return (
    <a
      href={href}
      className={`tab-btn ${className} ${isActive ? "active" : ""}`}
      aria-current={isActive ? "page" : undefined}
      title={title}
      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
        if (!requireAuth) {
          followLink(event, href);
          return;
        }
        event.preventDefault();
        requireAuth(() => {
          navigate(href);
        });
      }}
    >
      {Icon && <Icon size={15} aria-hidden="true" className="tab-icon" />}
      {children}
    </a>
  );
}
