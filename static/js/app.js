// LEGO Manager — shared app JS (Add-Set modal toggle + top-bar predictive
// search). Kept in an external file (rather than an inline <script> block in
// base.html) so the app can ship a strict Content-Security-Policy without a
// `script-src 'unsafe-inline'` exception.

(function () {
    // Generic auto-submit for filter/sort <select> controls: avoids inline
    // onchange="" handlers (disallowed under our strict CSP) by delegating a
    // change listener that submits the control's enclosing <form>.
    document.addEventListener('change', function (event) {
        const control = event.target.closest('[data-auto-submit]');
        if (control) {
            control.closest('form').submit();
        }
    });
})();

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

(function () {
    // Delete-set confirmation popover (set_detail.html). Bootstrap doesn't
    // auto-initialize popovers, and its default content sanitizer strips
    // <button> tags from data-bs-content — safe to disable sanitization here
    // since the content is fully server-rendered/Jinja-escaped, not
    // user-controlled.
    const deleteBtn = document.getElementById('delete-set-btn');
    if (!deleteBtn || typeof bootstrap === 'undefined') return;

    const popover = new bootstrap.Popover(deleteBtn, {
        sanitize: false,
        trigger: 'click',
    });

    document.addEventListener('click', function (event) {
        if (event.target.closest('[data-popover-cancel]')) {
            popover.hide();
        } else if (event.target.closest('[data-popover-confirm-delete]')) {
            document.getElementById('delete-set-form').submit();
        }
    });
})();

(function () {
    // Quick actions on set list/grid cards: change build status from a
    // dropdown and toggle favorite, both without navigating into the set
    // detail page. Delegated on document since cards are rendered in a loop.
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    document.addEventListener('click', function (event) {
        const statusOption = event.target.closest('.set-status-option');
        if (statusOption) {
            event.preventDefault();
            const dropdown = statusOption.closest('.set-status-dropdown');
            const toggle = dropdown.querySelector('.set-status-toggle');
            const setId = toggle.dataset.setId;
            const newStatus = statusOption.dataset.status;

            fetch('/set/' + encodeURIComponent(setId) + '/status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({ build_status: newStatus }),
            })
                .then(function (resp) { return resp.ok ? resp.json() : Promise.reject(resp); })
                .then(function () {
                    const oldClasses = toggle.dataset.currentBadgeClass.split(' ').filter(Boolean);
                    const newClasses = statusOption.dataset.badgeClass.split(' ').filter(Boolean);
                    if (oldClasses.length) toggle.classList.remove(...oldClasses);
                    if (newClasses.length) toggle.classList.add(...newClasses);
                    toggle.dataset.currentBadgeClass = statusOption.dataset.badgeClass;
                    toggle.querySelector('.set-status-icon').className = 'bi ' + statusOption.dataset.icon + ' set-status-icon';
                    toggle.querySelector('.set-status-label').textContent = statusOption.dataset.label;
                    dropdown.querySelectorAll('.set-status-option').forEach(function (opt) {
                        opt.classList.remove('active');
                    });
                    statusOption.classList.add('active');
                })
                .catch(function () {
                    // Leave the pill unchanged on failure — no toast system in
                    // this app yet, so silently ignore rather than partially
                    // update the UI to something inconsistent with the server.
                });
            return;
        }

        const favBtn = event.target.closest('.set-favorite-btn');
        if (favBtn) {
            event.preventDefault();
            const setId = favBtn.dataset.setId;

            fetch('/set/' + encodeURIComponent(setId) + '/favorite', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
            })
                .then(function (resp) { return resp.ok ? resp.json() : Promise.reject(resp); })
                .then(function (data) {
                    const isFavorite = !!data.favorite;
                    favBtn.classList.toggle('active', isFavorite);
                    favBtn.classList.toggle('text-danger', isFavorite);
                    favBtn.classList.toggle('border-danger', isFavorite);
                    favBtn.setAttribute('aria-pressed', String(isFavorite));
                    favBtn.setAttribute('aria-label', isFavorite ? 'Remove from favorites' : 'Add to favorites');
                    const icon = favBtn.querySelector('i');
                    icon.className = isFavorite ? 'bi bi-heart-fill' : 'bi bi-heart';
                })
                .catch(function () {});
        }
    });
})();

(function () {
    // Infinite scroll for the sets list page: replaces click-to-paginate
    // with auto-loading the next page of set cards as the user scrolls near
    // the bottom, via IntersectionObserver on a sentinel element.
    const sentinel = document.getElementById('sets-scroll-sentinel');
    const container = document.getElementById('sets-items-container');
    if (!sentinel || !container || typeof IntersectionObserver === 'undefined') return;

    const loadingIndicator = sentinel.querySelector('.sets-scroll-loading');
    let loading = false;

    function hasMore() {
        return sentinel.dataset.hasMore === 'true';
    }

    function buildItemsUrl() {
        const params = new URLSearchParams({
            view: sentinel.dataset.view || '',
            theme: sentinel.dataset.theme || '',
            status: sentinel.dataset.status || '',
            favorite: sentinel.dataset.favorite || '',
            location: sentinel.dataset.location || '',
            sort: sentinel.dataset.sort || '',
            page: sentinel.dataset.nextPage || '1',
        });
        return sentinel.dataset.itemsUrl + '?' + params.toString();
    }

    function loadNextPage() {
        if (loading || !hasMore()) return;
        loading = true;
        if (loadingIndicator) loadingIndicator.classList.remove('d-none');

        fetch(buildItemsUrl(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (resp) { return resp.ok ? resp.json() : Promise.reject(resp); })
            .then(function (data) {
                container.insertAdjacentHTML('beforeend', data.html);
                sentinel.dataset.hasMore = String(!!data.has_more);
                sentinel.dataset.nextPage = String(data.next_page);
                if (!data.has_more) observer.disconnect();
            })
            .catch(function () {
                // Leave has_more as-is so a transient network failure doesn't
                // permanently stop the observer; the next intersection retries.
            })
            .finally(function () {
                loading = false;
                if (loadingIndicator) loadingIndicator.classList.add('d-none');
            });
    }

    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) loadNextPage();
        });
    }, { rootMargin: '400px' });

    if (hasMore()) observer.observe(sentinel);
})();

(function () {
    // Free-text "Location" field on the set detail page, with a dropdown of
    // previously-used locations (shown in full on focus, filtered live as
    // the user types, matched substring highlighted like breadcrumbs).
    function escapeHtml(str) {
        return str.replace(/[&<>"']/g, function (ch) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
        });
    }

    function highlightMatch(value, query) {
        if (!query) return escapeHtml(value);
        const idx = value.toLowerCase().indexOf(query.toLowerCase());
        if (idx === -1) return escapeHtml(value);
        const before = value.slice(0, idx);
        const match = value.slice(idx, idx + query.length);
        const after = value.slice(idx + query.length);
        return escapeHtml(before) + '<strong>' + escapeHtml(match) + '</strong>' + escapeHtml(after);
    }

    document.querySelectorAll('.location-combobox').forEach(function (combobox) {
        const input = combobox.querySelector('input');
        const menu = combobox.querySelector('.location-combobox-menu');
        if (!input || !menu) return;

        let locations = [];
        try {
            locations = JSON.parse(combobox.dataset.locations || '[]');
        } catch (e) {
            locations = [];
        }

        let activeIndex = -1;

        function closeMenu() {
            menu.classList.add('d-none');
            menu.innerHTML = '';
            activeIndex = -1;
        }

        function openMenu(query) {
            const matches = locations.filter(function (loc) {
                return !query || loc.toLowerCase().includes(query.toLowerCase());
            });
            if (!matches.length) {
                closeMenu();
                return;
            }
            menu.innerHTML = matches
                .map(function (loc) {
                    return '<li class="list-group-item list-group-item-action location-combobox-option" role="option" data-value="' +
                        escapeHtml(loc) + '">' + highlightMatch(loc, query) + '</li>';
                })
                .join('');
            menu.classList.remove('d-none');
            activeIndex = -1;
        }

        function setActive(index) {
            const options = menu.querySelectorAll('.location-combobox-option');
            options.forEach(function (opt) { opt.classList.remove('active'); });
            if (index >= 0 && index < options.length) {
                options[index].classList.add('active');
                options[index].scrollIntoView({ block: 'nearest' });
            }
            activeIndex = index;
        }

        input.addEventListener('focus', function () { openMenu(input.value); });
        input.addEventListener('input', function () { openMenu(input.value); });

        input.addEventListener('keydown', function (event) {
            const options = menu.querySelectorAll('.location-combobox-option');
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                if (menu.classList.contains('d-none')) { openMenu(input.value); return; }
                setActive(Math.min(activeIndex + 1, options.length - 1));
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive(Math.max(activeIndex - 1, 0));
            } else if (event.key === 'Enter') {
                if (activeIndex >= 0 && options[activeIndex]) {
                    event.preventDefault();
                    input.value = options[activeIndex].dataset.value;
                    closeMenu();
                }
            } else if (event.key === 'Escape') {
                closeMenu();
            }
        });

        // mousedown (not click) fires before the input's blur handler, so the
        // menu is still populated when we read the clicked option's value.
        menu.addEventListener('mousedown', function (event) {
            const option = event.target.closest('.location-combobox-option');
            if (!option) return;
            event.preventDefault();
            input.value = option.dataset.value;
            closeMenu();
        });

        document.addEventListener('click', function (event) {
            if (!combobox.contains(event.target)) closeMenu();
        });
    });
})();
