# LEGO Manager — React SPA

A React + TypeScript + Vite rewrite of the LEGO Manager UI. It is entirely
additive: the existing Flask/Jinja UI (templates/, static/js/) is untouched
and keeps working at its original URLs. This app is a separate, modern
client that talks to a new JSON API (`app/blueprints/api.py`) and is served
by Flask under `/app/*` (`app/blueprints/spa.py`) once built.

## Development

Run both servers side by side (same-origin via the Vite dev proxy, so
session cookies/CSRF "just work" with no CORS setup):

```bash
# Terminal 1 — Flask API + legacy UI, port 5000
python wsgi.py

# Terminal 2 — Vite dev server w/ HMR, port 5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/app/.

## Building for production

```bash
cd frontend
npm run build
```

This outputs static assets into `../static/app/`, which `app/blueprints/spa.py`
serves at `/app/*` (with SPA history-mode fallback to `index.html`). No
separate Node server is needed in production — Flask serves everything.

## Progressive Web App

The build is a PWA via `vite-plugin-pwa` (configured in `vite.config.ts`):
a web app manifest + icons (`frontend/public/pwa-*.png`,
`apple-touch-icon.png`) make it installable to a phone's home screen, and a
generated service worker (`sw.js`) precaches the app shell and serves
`/files/*` (stale-while-revalidate) and `/api/*` (network-first) so recently
viewed data still renders if the network drops. Regenerate the icons from
`frontend/public/icon.svg` / `icon-maskable.svg` with ImageMagick
(`convert -background none icon.svg -resize <size> <out>.png`) if the brand
color/logo ever changes.

## Stack

- React 19 + TypeScript
- React Router (client-side routing)
- TanStack Query (data fetching/caching, infinite scroll)
- Axios (HTTP client, with a CSRF-token interceptor matching Flask-WTF)
- pdfjs-dist (canvas-based instructions viewer, lazy-loaded as its own chunk
  so the ~450KB PDF engine is only fetched when a set-detail page with
  instructions is actually opened)
- Hand-rolled CSS design system (`src/index.css`) — no UI framework

## PDF instructions viewer

`src/components/PdfViewer.tsx` is a from-scratch React port of the legacy
`static/js/pdf-viewer.js`, with full feature parity:

- Canvas-based single-page rendering via `pdfjs-dist` (self-contained in the
  SPA bundle — no reliance on Flask's `/static/js/pdfjs/*`).
- Prev/next page buttons, a page-number input you can type/jump to, and
  zoom in/out (0.5x–3x).
- Multi-booklet switcher for sets with more than one instructions PDF;
  switching booklets always resets to page 1 (matches the legacy behavior —
  `build_page` tracks a single page for the whole set, not per booklet).
- Debounced (800ms) auto-save of the current page back to
  `POST /api/sets/<id>/progress/page`, with a transient "Progress saved"
  status message, so "Build progress" reflects where the user left off.
