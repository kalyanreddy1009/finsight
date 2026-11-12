import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The API runs on the FastAPI dev server; the browser only ever calls same-origin /api/v1/...
const API_TARGET = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: API_TARGET },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Vitest blanks stylesheet imports by default; the contrast test reads tokens.css as raw text.
    css: { include: [/\.css(\?|$)/] },
  },
});
