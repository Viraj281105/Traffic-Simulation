import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { AppRouteLoader } from "./components/ui/RouteLoader";
import "./styles/tokens.css";
import "./styles/components.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppRouteLoader />
    <App />
  </React.StrictMode>,
);
