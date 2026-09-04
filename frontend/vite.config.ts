import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
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
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/recharts")) {
            return "charts";
          }
          if (
            id.includes("node_modules/react/") ||
            id.includes("node_modules/react-dom/")
          ) {
            return "vendor";
          }
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
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
