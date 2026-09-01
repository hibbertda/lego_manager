# Dev: Frontend Build

The UI is built on Bootstrap 5, compiled ahead of time from Sass and served
as a plain, same-origin static file — no CDN or external font requests are
made by the browser at runtime. Run this once after cloning (and again any
time you change `static/src/custom-bootstrap.scss` or template markup):

```bash
npm install
npm run build
```

This generates:

- `static/css/app.css` — compiled Sass, including Bootstrap + custom theme
  (color palette, typography, component styles)
- `static/js/bootstrap.bundle.min.js` — copied from `node_modules`
- `static/js/pdfjs/*.mjs` — Mozilla's PDF.js library, copied from
  `node_modules/pdfjs-dist` (see below)

All of these are self-hosted so no CDN requests happen at runtime. Node is
only needed for this build step — it is not required to run the app.

Built assets are committed to the repo, matching the existing pattern for
this project — the Docker image does not run `npm` at build time, it just
copies the already-built `static/` tree. Re-run `npm run build` (or the more
targeted `npm run build:css` / `npm run build:pdfjs`) and commit the result
whenever you bump `pdfjs-dist` or change
`static/src/custom-bootstrap.scss`/`static/js/*.js`.

## Instruction PDF viewer

Instruction PDFs are rendered on the set detail page with a small custom
viewer (`static/js/pdf-viewer.js`) built on self-hosted PDF.js
(`static/js/pdfjs/`), rather than the browser's native PDF plugin. This gives
page navigation controls and lets the app auto-save the current page back to
the server (`POST /set/<id>/progress/page`) as you read, so "Build progress"
tracks where you left off without manual entry. Only the first instructions
PDF for a set auto-saves progress; additional PDFs (multi-book sets) get the
same viewer without progress tracking, since `build_page` is a single value
per set. The viewer panel can be resized by dragging its bottom edge, in
addition to the zoom controls.

## CSP-safe interactivity

The app sets a strict `Content-Security-Policy` with no `unsafe-inline`
exception (see [Security](Security.md)), so inline `onclick`/`onchange`/
`onsubmit` HTML attributes are silently blocked by the browser and must never
be used. All interactivity instead goes through delegated
`document.addEventListener` handlers in `static/js/app.js`, keyed off `data-*`
attributes, for example:

- `data-confirm-popover="delete"` — a reusable Bootstrap Popover-based
  confirmation prompt before a destructive form submit (used for deleting
  sets and users). Popover content is teleported to a separate DOM node by
  Bootstrap, so the handler tracks the currently-open trigger element
  (`shown.bs.popover`) to know which form to submit on confirm.
- `data-auto-submit` — submits the closest `<form>` automatically when a
  `<select>`/input's value changes (used for the admin role selector and the
  quick build-status dropdown on set cards).

When adding new interactive markup, add a new `data-*` attribute + delegated
listener rather than an inline event handler.
