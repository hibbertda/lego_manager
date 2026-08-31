// LEGO Manager — shared app JS (Add-Set modal toggle + top-bar predictive
// search). Kept in an external file (rather than an inline <script> block in
// base.html) so the app can ship a strict Content-Security-Policy without a
// `script-src 'unsafe-inline'` exception.

(function () {
    const autoRadio = document.getElementById('addSetMethodAuto');
    const manualRadio = document.getElementById('addSetMethodManual');
    const autoPane = document.getElementById('addSetAutoPane');
    const manualPane = document.getElementById('addSetManualPane');
    if (autoRadio && manualRadio) {
        autoRadio.addEventListener('change', function () {
            autoPane.classList.remove('d-none');
            manualPane.classList.add('d-none');
        });
        manualRadio.addEventListener('change', function () {
            manualPane.classList.remove('d-none');
            autoPane.classList.add('d-none');
        });
    }
})();

(function () {
    const input = document.getElementById('topbar-search-input');
    if (!input) return;
    const resultsBox = document.getElementById('topbar-search-results');
    const suggestUrl = input.dataset.suggestUrl;
    let debounceTimer = null;
    let currentController = null;

    function renderResults(data) {
        const results = data.results || [];
        resultsBox.innerHTML = '';
        if (!results.length) {
            const empty = document.createElement('p');
            empty.className = 'px-3 py-2 mb-0 small text-muted';
            empty.textContent = 'No matching sets found.';
            resultsBox.appendChild(empty);
            resultsBox.classList.remove('d-none');
            return;
        }
        results.forEach(function (s) {
            // Build result rows with safe DOM APIs (textContent / setAttribute)
            // rather than innerHTML + string concatenation, since set names
            // originate from user-entered data (manual add) or third-party
            // API data and must never be interpreted as HTML.
            const link = document.createElement('a');
            link.href = s.url;
            link.className = 'd-flex align-items-center gap-2 px-3 py-2 text-decoration-none text-dark';

            let thumb;
            if (s.image) {
                thumb = document.createElement('img');
                thumb.src = s.image;
                thumb.alt = '';
                thumb.className = 'set-thumb flex-shrink-0';
                thumb.style.width = '2.5rem';
                thumb.style.height = '2.5rem';
            } else {
                thumb = document.createElement('span');
                thumb.className = 'set-thumb d-flex align-items-center justify-content-center flex-shrink-0';
                thumb.style.width = '2.5rem';
                thumb.style.height = '2.5rem';
                const icon = document.createElement('i');
                icon.className = 'bi bi-box-seam-fill text-secondary';
                thumb.appendChild(icon);
            }
            link.appendChild(thumb);

            const textWrap = document.createElement('span');
            textWrap.className = 'text-truncate';

            const nameEl = document.createElement('span');
            nameEl.className = 'd-block small fw-semibold text-truncate';
            nameEl.textContent = s.name;
            textWrap.appendChild(nameEl);

            const metaEl = document.createElement('span');
            metaEl.className = 'd-block small text-muted';
            metaEl.textContent = '#' + s.setNumber + (s.year ? ' \u00b7 ' + s.year : '');
            textWrap.appendChild(metaEl);

            link.appendChild(textWrap);
            resultsBox.appendChild(link);
        });
        resultsBox.classList.remove('d-none');
    }

    input.addEventListener('input', function () {
        const query = input.value.trim();
        clearTimeout(debounceTimer);
        if (!query) {
            resultsBox.classList.add('d-none');
            resultsBox.innerHTML = '';
            return;
        }
        debounceTimer = setTimeout(function () {
            if (currentController) currentController.abort();
            currentController = new AbortController();
            fetch(suggestUrl + '?query=' + encodeURIComponent(query), { signal: currentController.signal })
                .then(function (res) { return res.json(); })
                .then(renderResults)
                .catch(function (err) {
                    if (err.name !== 'AbortError') resultsBox.classList.add('d-none');
                });
        }, 200);
    });

    document.addEventListener('click', function (event) {
        if (!event.target.closest('#topbar-search-form') && !event.target.closest('#topbar-search-results')) {
            resultsBox.classList.add('d-none');
        }
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            resultsBox.classList.add('d-none');
        }
    });
})();
