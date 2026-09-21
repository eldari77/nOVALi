import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/shell/",
  plugins: [react()],
  build: {
    outDir: "build",
    emptyOutDir: true,
  },
});
