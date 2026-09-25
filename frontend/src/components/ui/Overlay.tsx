/**
 * The one modal dialog and side drawer every page uses.
 *
 * Structure is fixed: header (title, optional description, close button),
 * scrolling body, optional footer. Escape and the backdrop close it; focus
 * moves into the panel on open, is kept inside while open and returns to
 * the opener on close. Opening and closing animate (see components.css);
 * reduced motion shortens both to an instant change.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CloseButton } from "./CloseButton";

interface OverlayProps {
  /** "dialog" is centred; "drawer" slides in from the right. */
  variant?: "dialog" | "drawer";
  /** Wider panel for dense content (full comparison, experiment settings). */
  wide?: boolean;
  title: ReactNode;
  description?: ReactNode;
  /** Extra header content next to the title (e.g. a view toggle, a badge). */
  headerExtra?: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  /** aria-label for the close button; defaults to "Close". */
  closeLabel?: string;
  children: ReactNode;
  className?: string;
  /** Render the body as a <form>; its submit handler. */
  onSubmit?: (event: React.SyntheticEvent) => void;
  testId?: string;
  /** "alertdialog" for confirmations that interrupt (e.g. delete). */
  role?: "dialog" | "alertdialog";
  /** Narrow panel for short confirmations. */
  narrow?: boolean;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function Overlay({
  variant = "dialog",
  wide = false,
  title,
  description,
  headerExtra,
  footer,
  onClose,
  closeLabel = "Close",
  children,
  className = "",
  onSubmit,
  testId,
  role = "dialog",
  narrow = false,
}: OverlayProps) {
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [closing, setClosing] = useState(false);

  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  const requestClose = () => {
    if (closing) return;
    // In tests (jsdom) and with reduced motion there is no exit animation
    // to wait for; close immediately.
    if (prefersReducedMotion() || typeof window.matchMedia !== "function") {
      onCloseRef.current();
      return;
    }
    setClosing(true);
  };
  const requestCloseRef = useRef(requestClose);
  useEffect(() => {
    requestCloseRef.current = requestClose;
  });

  // Close once the exit animation has played. The timeout is a fallback
  // for environments where animationend never fires.
  const closedRef = useRef(false);
  const finishClose = () => {
    if (closedRef.current) return;
    closedRef.current = true;
    onCloseRef.current();
  };
  useEffect(() => {
    if (!closing) return;
    const timer = window.setTimeout(finishClose, 320);
    return () => {
      window.clearTimeout(timer);
    };
  });

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(
      "[data-autofocus]",
    ) as HTMLElement | null;
    (first ?? panel)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        requestCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const items = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (items.length === 0) return;
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstItem) {
        e.preventDefault();
        lastItem.focus();
      } else if (!e.shiftKey && document.activeElement === lastItem) {
        e.preventDefault();
        firstItem.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, []);

  const panelClass = [
    variant === "drawer" ? "uf-drawer" : "uf-dialog",
    wide ? (variant === "drawer" ? "uf-drawer--wide" : "uf-dialog--wide") : "",
    narrow ? "uf-dialog--narrow" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const body = <div className="uf-panel-body">{children}</div>;

  return (
    <div
      className={`uf-overlay${variant === "drawer" ? " uf-overlay--drawer" : ""}${closing ? " is-closing" : ""}`}
      onClick={requestClose}
      onAnimationEnd={(e) => {
        if (closing && e.target === e.currentTarget) finishClose();
      }}
    >
      <div
        ref={panelRef}
        className={panelClass}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        data-testid={testId}
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <div className="uf-panel-header">
          <div className="uf-panel-header__text">
            <h2 className="uf-panel-title" id={titleId}>
              {title}
            </h2>
            {description && (
              <p className="uf-panel-description" id={descId}>
                {description}
              </p>
            )}
          </div>
          {headerExtra}
          <CloseButton label={closeLabel} onClick={requestClose} />
        </div>
        {onSubmit ? (
          <form className="uf-panel-form" onSubmit={onSubmit}>
            {body}
            {footer && <div className="uf-panel-footer">{footer}</div>}
          </form>
        ) : (
          <>
            {body}
            {footer && <div className="uf-panel-footer">{footer}</div>}
          </>
        )}
      </div>
    </div>
  );
}
