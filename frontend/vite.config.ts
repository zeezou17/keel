/** Vite build config: compiles React app into keel/static/ for `keel dev`. */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../keel/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          xyflow: ["@xyflow/react"],
          markdown: ["react-markdown", "remark-gfm"],
        },
      },
    },
  },
});
