import { useEffect } from "react";
import { Login } from "../Login";
import { useExitTransition } from "../ui/motion";

/** The sign-in form in the shared dialog frame: Escape or the backdrop
 *  closes it, focus starts in the form. */
export function LoginDialog({
  onClose,
  onLogin,
}: {
  onClose: () => void;
  onLogin: () => void;
}) {
  // The dialog fades out before it unmounts (ui/motion.ts).
  const { overlay, panel, close } = useExitTransition(onClose);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [close]);

  return (
    <div
      ref={overlay}
      className="uf-dialog-overlay login-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        ref={panel}
        className="uf-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
      >
        <Login onLogin={onLogin} onClose={close} />
      </div>
    </div>
  );
}
