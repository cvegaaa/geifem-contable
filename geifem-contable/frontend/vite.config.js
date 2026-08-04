import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  build: { outDir: path.resolve(__dirname, "../../dist"), emptyOutDir: true },
  server: { port: 8080, host: "0.0.0.0" },
});
