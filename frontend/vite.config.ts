import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // index.html injects the manifest link / registers the service worker
      // itself; nothing extra is needed in app code.
      injectRegister: 'auto',
      includeAssets: ['apple-touch-icon.png'],
      manifest: {
        name: 'LEGO Manager',
        short_name: 'LEGO Manager',
        description: 'Track your LEGO set collection, builds, and instructions.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#f5f6fa',
        theme_color: '#d6271c',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Precache the built app shell; everything under /api is live data
        // (collection/auth state) so it's explicitly excluded from
        // precaching and instead handled by the runtime rules below.
        globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
        navigateFallbackDenylist: [/^\/api\//, /^\/files\//],
        runtimeCaching: [
          {
            // Set cover images / instruction thumbnails: fine to serve a
            // stale copy instantly while refreshing in the background. This
            // is purely reactive (only caches what's actually opened, never
            // the whole collection) but is capped here so it can't grow
            // unbounded as more of the collection gets browsed over time.
            urlPattern: /^\/files\/.*/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'lego-manager-files',
              expiration: { maxEntries: 150, maxAgeSeconds: 30 * 24 * 60 * 60 },
            },
          },
          {
            // API data (sets, search, admin): prefer the network, but fall
            // back to the last-known response so the app isn't blank when
            // offline. Small/short-lived cache — just enough to survive a
            // dropped connection, not a data store.
            urlPattern: /^\/api\/.*/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'lego-manager-api',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 50, maxAgeSeconds: 24 * 60 * 60 },
            },
          },
        ],
      },
    }),
  ],
  // The React SPA now owns the site root (see app/blueprints/spa.py), so
  // built asset URLs are unprefixed.
  base: '/',
  server: {
    port: 5173,
    proxy: {
      // Proxy API + file-serving + OIDC + label-rendering calls to the Flask
      // dev server so the browser sees everything as same-origin — this
      // avoids CORS entirely and lets Flask's session cookie + CSRF token
      // work exactly like production.
      '/api': 'http://127.0.0.1:5000',
      '/files': 'http://127.0.0.1:5000',
      '/set': 'http://127.0.0.1:5000',
      '/login/oidc': 'http://127.0.0.1:5000',
    },
  },
  build: {
    // Build straight into Flask's static folder under a dedicated
    // sub-directory, so Flask can serve the compiled SPA assets without any
    // new static-file route.
    outDir: '../static/app',
    emptyOutDir: true,
  },
})
