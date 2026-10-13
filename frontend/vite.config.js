import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// En desarrollo, /api se reenvía al backend local: mismo origen, igual que en
// producción (donde nginx hace el proxy). Así la cookie de sesión funciona sin CORS.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_BACKEND_URL || "http://localhost:8000",
    },
  },
});
