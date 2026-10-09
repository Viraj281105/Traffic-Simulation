import type { MouseEvent, ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { followLink } from "../../routing";

/** An in-app link in the Research lab's "see also" style. Plain left clicks
 *  navigate client-side; modified clicks are left to the browser. */
export function ResearchLink({
  to,
  children,
  className = "rl-link",
}: {
  to: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      className={className}
      href={to}
      onClick={(e: MouseEvent<HTMLAnchorElement>) => {
        followLink(e, to);
      }}
    >
      {children}
      <ArrowRight size={14} aria-hidden="true" />
    </a>
  );
}

/** A page section: heading, one-sentence lede, content, and the links that
 *  lead to the detailed page for it. */
export function LabSection({
  id,
  title,
  lede,
  links,
  children,
}: {
  id: string;
  title: string;
  lede?: ReactNode;
  links?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rl-section" id={id} aria-labelledby={`${id}-title`}>
      <header className="rl-section-head">
        <h2 id={`${id}-title`}>{title}</h2>
        {lede && <p className="rl-lede">{lede}</p>}
      </header>
      {children}
      {links && <div className="rl-links">{links}</div>}
    </section>
  );
}
