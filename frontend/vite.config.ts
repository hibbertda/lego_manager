import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Served by Flask under /app/* (see app/blueprints/spa.py) rather than
  // from the domain root, so every built asset URL must be prefixed to match.
  base: '/app/',
  server: {
    port: 5173,
    proxy: {
      // Proxy API + file-serving + static (Flask-rendered label images etc.)
      // calls to the Flask dev server so the browser sees everything as
      // same-origin — this avoids CORS entirely and lets Flask's session
      // cookie + CSRF token work exactly like the existing Jinja app.
      '/api': 'http://127.0.0.1:5000',
      '/sets': 'http://127.0.0.1:5000',
    },
  },
  build: {
    // Build straight into Flask's static folder under a dedicated
    // sub-directory, so Flask can serve the compiled SPA assets without any
    // new static-file route, and without touching the existing static/js,
    // static/css used by the legacy Jinja UI.
    outDir: '../static/app',
    emptyOutDir: true,
  },
})
