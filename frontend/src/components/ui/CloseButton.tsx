/** The one close control for every dialog, drawer and panel: a compact
 *  32 px icon button with a 16 px cross (see .uf-icon-btn). */
export function CloseButton({
  label = "Close",
  onClick,
  className = "",
}: {
  label?: string;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={`uf-icon-btn uf-close-btn ${className}`.trim()}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      <svg
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d="M4 4l8 8M12 4l-8 8" />
      </svg>
    </button>
  );
}
