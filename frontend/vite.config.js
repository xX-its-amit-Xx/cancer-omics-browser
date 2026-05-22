import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker the API is reachable at the `backend` service; the dev/preview server
// proxies /api there so the browser only ever talks to the frontend origin.
const API_TARGET = process.env.VITE_API_TARGET || "http://backend:8000";

// Base public path. "/" for local/Docker; for GitHub project Pages it must be
// "/<repo>/", injected by the deploy workflow via VITE_BASE.
const BASE = process.env.VITE_BASE || "/";

export default defineConfig({
  base: BASE,
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Allow Codespaces / proxied forwarded hosts (e.g. *.app.github.dev).
    allowedHosts: true,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true } },
  },
  preview: {
    host: true,
    port: 5173,
    allowedHosts: true,
    proxy: { "/api": { target: API_TARGET, changeOrigin: true } },
  },
});
