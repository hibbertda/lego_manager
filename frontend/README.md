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

## Stack

- React 19 + TypeScript
- React Router (client-side routing)
- TanStack Query (data fetching/caching, infinite scroll)
- Axios (HTTP client, with a CSRF-token interceptor matching Flask-WTF)
- Hand-rolled CSS design system (`src/index.css`) — no UI framework

## Notes / known scope reductions vs. the legacy Jinja UI

- The PDF instructions viewer opens PDFs in the browser's native viewer via
  plain links, rather than the legacy custom PDF.js canvas viewer with page
  tracking (`static/js/pdf-viewer.js`).
