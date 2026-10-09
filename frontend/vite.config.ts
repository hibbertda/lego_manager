import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
