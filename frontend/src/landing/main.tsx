import { createRoot } from "react-dom/client";
import { MotionConfig } from "framer-motion";

import App from "./App";
import { ErrorBoundary } from "./components/error-boundary";

import "../styles/tokens.css";
import "../styles/components.css";
import "./index.css";

createRoot(document.getElementById("root")!, {
  // Keeps caught errors off reportError(), which would raise the dev overlay.
  onCaughtError: (error, errorInfo) => {
    console.error(error, errorInfo.componentStack);
  },
}).render(
  <ErrorBoundary>
    {/* Scroll reveals follow prefers-reduced-motion, as the app does. */}
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </ErrorBoundary>,
);
