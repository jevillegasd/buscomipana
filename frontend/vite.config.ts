import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        // Workbox's default NavigationRoute has no exclusions -- it treats
        // every top-level navigation (including a plain <a href> click) as
        // an SPA route and serves the cached index.html for it, offline or
        // not. Without this denylist it swallows navigations to
        // backend-served pages (notably GET /api/v1/manual, linked from the
        // login screen) and any admin/docs route too: the SPA shell loads,
        // React Router doesn't recognize the path, and RequireAuth bounces
        // an unauthenticated visitor to /login -- which looks exactly like
        // "the link doesn't work" even though the backend serves it fine.
        // Mirrors the same path set the Caddyfile already routes to the
        // backend in production (see ../Caddyfile's @backend matcher).
        navigateFallbackDenylist: [/^\/api\//, /^\/admin/, /^\/health/, /^\/docs/, /^\/redoc/, /^\/openapi\.json/],
      },
      manifest: {
        name: "BuscoMiPana",
        short_name: "BuscoMiPana",
        description: "Reportes de estado y búsqueda de panas desaparecidos",
        lang: "es",
        theme_color: "#17140F",
        background_color: "#17140F",
        display: "standalone",
        start_url: "/",
        // App icons intentionally omitted from this scaffold -- drop real
        // pwa-192.png/pwa-512.png into frontend/public/ and list them here
        // before shipping an installable build.
        icons: [],
      },
    }),
  ],
  server: {
    port: 5173,
    // Docker Desktop on Windows doesn't propagate native filesystem events
    // (inotify) from the host into the container for bind-mounted volumes, so
    // Vite's dev-server module cache never invalidates on host-side edits
    // without polling -- without this, the container silently keeps serving
    // stale transformed modules indefinitely, even across hard reloads.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
