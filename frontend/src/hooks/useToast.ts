import { useRef, useState } from "react";

export type ToastTone = "success" | "error";

export interface Toast {
  message: string;
  tone: ToastTone;
}

/** One transient status message at a time, cleared after three seconds. */
export function useToast() {
  const [toast, setToast] = useState<Toast | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (message: string, tone: ToastTone = "success") => {
    setToast({ message, tone });
    // A newer message restarts the timer instead of being cut short by the
    // previous one's.
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => {
      setToast(null);
    }, 3000);
  };

  return { toast, showToast };
}
