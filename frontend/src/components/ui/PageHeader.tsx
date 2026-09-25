import type { ReactNode } from "react";

/** Standard page header: eyebrow, title, one-paragraph lead, actions. */
export function PageHeader({
  eyebrow,
  title,
  lead,
  actions,
  titleId,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  actions?: ReactNode;
  titleId?: string;
}) {
  return (
    <header className="uf-page-header">
      <div className="uf-page-header__text">
        {eyebrow && <p className="uf-eyebrow">{eyebrow}</p>}
        <h1 className="uf-page-title" id={titleId}>
          {title}
        </h1>
        {lead && <div className="uf-lead">{lead}</div>}
      </div>
      {actions && <div className="uf-page-actions">{actions}</div>}
    </header>
  );
}
