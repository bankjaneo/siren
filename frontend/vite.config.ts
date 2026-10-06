import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Proxy the Flask API in dev so `npm run dev` works with hot reload
// against the backend started by start.sh (default port 5067).
const flaskTarget = process.env.SIREN_BACKEND ?? "http://localhost:5067";

const apiRoutes = [
  "/status",
  "/play",
  "/play-file",
  "/pause",
  "/resume",
  "/stop",
  "/previous",
  "/next",
  "/connect",
  "/disconnect",
  "/devices",
  "/files",
  "/volume",
  "/config",
  "/stream",
];

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: Object.fromEntries(
      apiRoutes.map((route) => [route, { target: flaskTarget }]),
    ),
  },
});
