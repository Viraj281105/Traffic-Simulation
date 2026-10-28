import { useRef, useState } from "react";

export type ToastTone = "success" | "error";

/** An in-app link offered with a message, such as the page of what was
 *  just saved. */
export interface ToastAction {
  label: string;
  href: string;
}

export interface Toast {
  message: string;
  tone: ToastTone;
  action?: ToastAction;
}

/** One transient status message at a time, cleared after three seconds
 *  (six when it offers a link, so there is time to follow it). */
export function useToast() {
  const [toast, setToast] = useState<Toast | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (
    message: string,
    tone: ToastTone = "success",
    action?: ToastAction,
  ) => {
    setToast({ message, tone, action });
    // A newer message restarts the timer instead of being cut short by the
    // previous one's.
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(
      () => {
        setToast(null);
      },
      action ? 6000 : 3000,
    );
  };

  return { toast, showToast };
}
