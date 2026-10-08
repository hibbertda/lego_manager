import { useEffect, useMemo, useRef, useState } from 'react';
import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist';
// Vite bundles the worker as its own asset and gives us a served URL for it;
// self-contained within the SPA bundle (mirrors the legacy self-hosted
// static/js/pdfjs/pdf.worker.min.mjs, which avoided a CDN for CSP reasons).
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { api } from '../api/client';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const SCALE_STEP = 0.25;
const DEFAULT_SCALE = 1.25;
const PROGRESS_SAVE_DEBOUNCE_MS = 800;

interface PdfViewerProps {
  /** One entry per instruction booklet, in the same order as the set's
   * local_instructions, so a multi-book set gets a switcher. */
  urls: string[];
  /** setID whose build_page progress this viewer should auto-save to. */
  setId: number;
  /** Page to open the first booklet on (usually set.build_page). Switching
   * to a different booklet always resets to page 1, matching the legacy
   * viewer — build_page tracks a single page number for the whole set, not
   * per-booklet. */
  initialPage: number;
}

function debounce<Args extends unknown[]>(fn: (...args: Args) => void, delayMs: number) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

export default function PdfViewer({ urls, setId, initialPage }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pdfDocRef = useRef<PDFDocumentProxy | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const loadTokenRef = useRef(0);
  const lastSavedPageRef = useRef<number | null>(null);

  const [activeIndex, setActiveIndex] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [pageInputValue, setPageInputValue] = useState('1');
  const [scale, setScale] = useState(DEFAULT_SCALE);
  const [status, setStatus] = useState('Loading…');

  const saveProgress = useMemo(
    () =>
      debounce((page: number) => {
        if (page === lastSavedPageRef.current) return;
        api
          .post(`/sets/${setId}/progress/page`, { build_page: page })
          .then(() => {
            lastSavedPageRef.current = page;
            setStatus('Progress saved');
            setTimeout(() => setStatus((s) => (s === 'Progress saved' ? '' : s)), 1500);
          })
          .catch((err) => {
            // Best-effort only; a failed autosave shouldn't interrupt reading.
            console.warn('Failed to save reading progress', err);
          });
      }, PROGRESS_SAVE_DEBOUNCE_MS),
    [setId],
  );

  async function renderPage(num: number, doc: PDFDocumentProxy, zoom: number) {
    const clamped = Math.min(Math.max(1, num), doc.numPages);
    const canvas = canvasRef.current;
    if (!canvas) return;

    const page = await doc.getPage(clamped);
    const viewport = page.getViewport({ scale: zoom });
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    renderTaskRef.current?.cancel();
    const task = page.render({ canvasContext: ctx, viewport, canvas });
    renderTaskRef.current = task;
    try {
      await task.promise;
    } catch (err) {
      if (!(err instanceof Error) || err.name !== 'RenderingCancelledException') throw err;
      return;
    }

    setCurrentPage(clamped);
    setPageInputValue(String(clamped));
    setNumPages(doc.numPages);
    saveProgress(clamped);
  }

  // Load (or reload) the active booklet whenever the active index changes.
  // Switching booklets always starts at page 1 (see initialPage doc above);
  // the very first load honors `initialPage` (the set's saved build_page).
  useEffect(() => {
    const myToken = ++loadTokenRef.current;
    const url = urls[activeIndex];
    if (!url) return;

    pdfDocRef.current = null;
    lastSavedPageRef.current = null;
    setStatus('Loading…');
    setNumPages(0);

    getDocument({ url })
      .promise.then(async (doc) => {
        if (myToken !== loadTokenRef.current) return; // a newer switch happened meanwhile
        pdfDocRef.current = doc;
        setStatus('');
        const startPage = activeIndex === 0 ? Math.max(1, initialPage || 1) : 1;
        await renderPage(startPage, doc, scale);
      })
      .catch((err) => {
        console.error('Failed to load PDF', err);
        if (myToken === loadTokenRef.current) setStatus('Failed to load this PDF.');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIndex, urls]);

  function goToPage(num: number) {
    const doc = pdfDocRef.current;
    if (!doc) return;
    renderPage(num, doc, scale);
  }

  function zoom(delta: number) {
    const doc = pdfDocRef.current;
    const nextScale = Math.min(Math.max(scale + delta, MIN_SCALE), MAX_SCALE);
    setScale(nextScale);
    if (doc) renderPage(currentPage, doc, nextScale);
  }

  function handlePageInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setPageInputValue(e.target.value);
  }

  function handlePageInputCommit() {
    const val = parseInt(pageInputValue, 10);
    if (!Number.isNaN(val)) goToPage(val);
    else setPageInputValue(String(currentPage));
  }

  return (
    <div className="card pdf-viewer-card">
      <div className="pdf-viewer-header">
        <span>Instructions</span>
        <span className="pdf-viewer-status text-muted">{status}</span>
      </div>

      {urls.length > 1 && (
        <div className="pdf-viewer-switcher">
          <span className="text-muted" style={{ fontSize: '0.82rem' }}>
            This set has {urls.length} instruction booklets:
          </span>
          {urls.map((url, i) => (
            <button
              key={url}
              type="button"
              className={`btn btn-sm ${i === activeIndex ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setActiveIndex(i)}
              disabled={i === activeIndex}
            >
              Book {i + 1}
            </button>
          ))}
        </div>
      )}

      <div className="pdf-viewer-toolbar">
        <button
          type="button"
          className="btn btn-sm btn-outline"
          aria-label="Previous page"
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          ◀
        </button>
        <span className="pdf-viewer-page-controls">
          <input
            type="number"
            min={1}
            max={numPages || undefined}
            className="pdf-viewer-page-input"
            aria-label="Page number"
            value={pageInputValue}
            onChange={handlePageInputChange}
            onBlur={handlePageInputCommit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handlePageInputCommit();
              }
            }}
          />
          <span className="pdf-viewer-page-indicator text-muted">
            {numPages ? `Page ${currentPage} of ${numPages}` : ''}
          </span>
        </span>
        <button
          type="button"
          className="btn btn-sm btn-outline"
          aria-label="Next page"
          onClick={() => goToPage(currentPage + 1)}
          disabled={!numPages || currentPage >= numPages}
        >
          ▶
        </button>
        <div className="pdf-viewer-divider" />
        <button type="button" className="btn btn-sm btn-outline" aria-label="Zoom out" onClick={() => zoom(-SCALE_STEP)}>
          −
        </button>
        <button type="button" className="btn btn-sm btn-outline" aria-label="Zoom in" onClick={() => zoom(SCALE_STEP)}>
          +
        </button>
      </div>

      <div className="pdf-viewer-canvas-wrap">
        <canvas ref={canvasRef} className="pdf-viewer-canvas" />
      </div>
    </div>
  );
}
