import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server only proxies to the backend (FastAPI, GPU model, LLM).
// Set FRESHEYE_BACKEND to point at a backend on another machine, e.g. a GPU server.
const BACKEND = process.env.FRESHEYE_BACKEND ?? "http://localhost:8200";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    proxy: {
      "/api": BACKEND,
      "/media": BACKEND,
    },
  },
});
