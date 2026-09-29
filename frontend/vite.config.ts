import { defineConfig, type Connect, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";
import { fileURLToPath } from "url";
import type { InlineConfig as VitestInlineConfig } from "vitest/node";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

declare module "vite" {
  interface UserConfig {
    test?: VitestInlineConfig;
  }
}

/**
 * History-API fallback for the two-document build, matching production nginx
 * (templates/default.conf.template): "/" is the landing page (index.html) and
 * every other page navigation is served the dashboard document (app.html),
 * whose client router shows the requested view — or its not-found page.
 * Without this, Vite's default fallback serves index.html, so refreshing a
 * dashboard URL would land on the landing page.
 */
function dashboardFallback(): Plugin {
  const passthrough = /^\/(?:api|ws|health|@|src\/|node_modules\/)/;
  const rewrite: Connect.NextHandleFunction = (req, _res, next) => {
    const path = (req.url ?? "/").split("?")[0];
    const isPageNavigation =
      (req.method === "GET" || req.method === "HEAD") &&
      (req.headers.accept ?? "").includes("text/html") &&
      !passthrough.test(path) &&
      !path.split("/").pop()?.includes(".");
    if (isPageNavigation && path !== "/") req.url = "/app.html";
    next();
  };
  return {
    name: "dashboard-history-fallback",
    configureServer(server) {
      server.middlewares.use(rewrite);
    },
    configurePreviewServer(server) {
      server.middlewares.use(rewrite);
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  // Two HTML entry points with page routing handled by dashboardFallback();
  // Vite's own SPA fallback would answer every unknown path with index.html.
  appType: "mpa",
  define: {
    global: "window",
  },
  plugins: [react(), tailwindcss(), dashboardFallback()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        app: resolve(__dirname, "app.html"),
      },
      output: {
        // Rolldown chunk groups. React is claimed first (higher priority):
        // with the old manualChunks function Recharts' group pulled React in
        // as a dependency, so the React core lived in the charts chunk and
        // every page had to download Recharts to start.
        codeSplitting: {
          groups: [
            {
              name: "vendor",
              test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              priority: 2,
            },
            {
              name: "charts",
              test: /node_modules[\\/]recharts[\\/]/,
              priority: 1,
            },
          ],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Tests run in DEV mode, where the dashboard would bypass sign-in
    // (src/auth/cognito.ts). Keep the real Cognito flow under test by
    // default; devAuthBypass.test.tsx switches the bypass on explicitly.
    env: { VITE_DEV_AUTH_BYPASS: "false" },
    pool: "vmThreads",
    server: {
      deps: {
        inline: ["@reduxjs/toolkit", "recharts"],
      },
    },
    coverage: {
      reporter: ["text", "lcov"],
      include: ["src/components/**", "src/services/**"],
    },
  },
});
