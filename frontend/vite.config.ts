import { defineConfig } from "vite";
export default defineConfig(({ command }) => ({
  base: command === "serve" ? "/" : "/static/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/accounts": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: {
    rollupOptions: {
      output: {
        entryFileNames: "assets/main.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: (asset) =>
          asset.names.some((n) => n.endsWith(".css"))
            ? "assets/style.css"
            : "assets/[name][extname]",
      },
    },
  },
}));
