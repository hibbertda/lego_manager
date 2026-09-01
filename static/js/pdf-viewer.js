// Minimal custom PDF viewer built on Mozilla's PDF.js, self-hosted (no CDN) so
// it fits the app's strict script-src 'self' CSP. Renders one page at a time
// on a <canvas>, with prev/next/page-jump controls. When a viewer has
// data-track-progress="true" it auto-saves the current page back to the
// server (debounced) so "Build progress" reflects where the user left off,
// without requiring them to type a page number manually.
import * as pdfjsLib from "/static/js/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/js/pdfjs/pdf.worker.min.mjs";

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
}

function debounce(fn, delayMs) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delayMs);
    };
}

async function initViewer(root) {
    const canvas = root.querySelector(".pdf-viewer-canvas");
    const pageIndicator = root.querySelector(".pdf-viewer-page-indicator");
    const pageInput = root.querySelector(".pdf-viewer-page-input");
    const prevBtn = root.querySelector(".pdf-viewer-prev");
    const nextBtn = root.querySelector(".pdf-viewer-next");
    const zoomInBtn = root.querySelector(".pdf-viewer-zoom-in");
    const zoomOutBtn = root.querySelector(".pdf-viewer-zoom-out");
    const statusEl = root.querySelector(".pdf-viewer-status");
    const ctx = canvas.getContext("2d");

    const url = root.dataset.pdfUrl;
    const trackProgress = root.dataset.trackProgress === "true";
    const progressUrl = root.dataset.progressUrl;
    let currentPage = Math.max(1, parseInt(root.dataset.initialPage || "1", 10) || 1);
    let scale = 1.25;
    let pdfDoc = null;
    let renderTask = null;
    let lastSavedPage = currentPage;

    const saveProgress = debounce(async (page) => {
        if (!trackProgress || !progressUrl || page === lastSavedPage) return;
        try {
            const resp = await fetch(progressUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({ build_page: page }),
            });
            if (resp.ok) {
                lastSavedPage = page;
                if (statusEl) {
                    statusEl.textContent = "Progress saved";
                    setTimeout(() => { statusEl.textContent = ""; }, 1500);
                }
            }
        } catch (err) {
            // Best-effort only; a failed autosave shouldn't interrupt reading.
            console.warn("Failed to save reading progress", err);
        }
    }, 800);

    async function renderPage(num) {
        if (!pdfDoc) return;
        num = Math.min(Math.max(1, num), pdfDoc.numPages);
        currentPage = num;

        const page = await pdfDoc.getPage(num);
        const viewport = page.getViewport({ scale });
        canvas.width = viewport.width;
        canvas.height = viewport.height;

        if (renderTask) {
            renderTask.cancel();
        }
        renderTask = page.render({ canvasContext: ctx, viewport });
        try {
            await renderTask.promise;
        } catch (err) {
            if (err && err.name !== "RenderingCancelledException") throw err;
        }

        pageIndicator.textContent = `Page ${num} of ${pdfDoc.numPages}`;
        pageInput.value = num;
        pageInput.max = pdfDoc.numPages;
        prevBtn.disabled = num <= 1;
        nextBtn.disabled = num >= pdfDoc.numPages;
        saveProgress(num);
    }

    prevBtn.addEventListener("click", () => renderPage(currentPage - 1));
    nextBtn.addEventListener("click", () => renderPage(currentPage + 1));
    pageInput.addEventListener("change", () => {
        const val = parseInt(pageInput.value, 10);
        if (!Number.isNaN(val)) renderPage(val);
    });
    zoomInBtn.addEventListener("click", () => {
        scale = Math.min(scale + 0.25, 3);
        renderPage(currentPage);
    });
    zoomOutBtn.addEventListener("click", () => {
        scale = Math.max(scale - 0.25, 0.5);
        renderPage(currentPage);
    });

    try {
        if (statusEl) statusEl.textContent = "Loading…";
        pdfDoc = await pdfjsLib.getDocument(url).promise;
        if (statusEl) statusEl.textContent = "";
        await renderPage(currentPage);
    } catch (err) {
        console.error("Failed to load PDF", err);
        if (statusEl) statusEl.textContent = "Failed to load this PDF.";
    }
}

document.querySelectorAll(".pdf-viewer").forEach(initViewer);
