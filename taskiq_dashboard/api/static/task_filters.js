(function () {
    if (window.taskFiltersInitialized) return;
    window.taskFiltersInitialized = true;
    const initialized = new WeakSet();
    const dateRestorers = new WeakMap();

    function collectFilters() {
        const params = new URLSearchParams();
        document.querySelectorAll('.task-filter').forEach(function (field) {
            if (field.name) params.set(field.name, field.value);
        });
        return params;
    }

    function requestTasks() {
        const table = document.getElementById('task-list');
        if (!table) return;
        htmx.ajax('GET', table.dataset.listUrl + '?' + collectFilters().toString(), {
            source: table,
            target: '#task-list-body',
            swap: 'innerHTML',
        }).catch(function () {
            // HTMX reports errors through its events; replacing a request rejects its promise.
        });
    }

    function hideOptions(combo) {
        combo.querySelector('.task-combobox-options').hidden = true;
        const input = combo.querySelector('[role="combobox"]');
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
    }

    function closeFilterPanels() {
        document.querySelectorAll('.column-filter').forEach(function (filter) {
            filter.querySelector('.column-filter-panel').classList.add('hidden');
            filter.querySelector('.column-filter-toggle').setAttribute('aria-expanded', 'false');
            filter.querySelectorAll('.task-combobox').forEach(hideOptions);
        });
    }

    function placeFilterPanel(filter) {
        const panel = filter.querySelector('.column-filter-panel');
        if (panel.classList.contains('hidden')) return;
        const rect = filter.querySelector('.column-filter-toggle').getBoundingClientRect();
        panel.style.maxWidth = Math.max(0, window.innerWidth - 16) + 'px';
        panel.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 8)) + 'px';
        panel.style.top = Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - panel.offsetHeight - 8)) + 'px';
    }

    function updateSortLinks() {
        document.querySelectorAll('a[data-sort-link]').forEach(function (link) {
            const url = new URL(link.href, window.location.origin);
            const params = collectFilters();
            params.set('sort_by', url.searchParams.get('sort_by'));
            params.set('sort_order', url.searchParams.get('sort_order'));
            link.href = url.pathname + '?' + params.toString();
        });
    }

    function dateSummary(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        });
    }

    function syncHeaderFilters() {
        document.querySelectorAll('.column-filter').forEach(function (filter) {
            const panel = filter.querySelector('.column-filter-panel');
            const field = Array.from(panel.querySelectorAll('.task-filter')).find(function (candidate) {
                return candidate.name === filter.dataset.filterParam;
            });
            const raw = field ? field.value : '';
            const kind = filter.dataset.filterKind;
            let summary = '';
            if (kind === 'status') {
                if (raw && raw !== 'null') summary = field.selectedOptions[0].textContent;
            } else if (kind === 'datetime') {
                const end = panel.querySelector('.date-range-end').value;
                if (raw && end) summary = dateSummary(raw) + ' – ' + dateSummary(end);
                else if (raw) summary = 'From ' + dateSummary(raw);
                else if (end) summary = 'Until ' + dateSummary(end);
            } else {
                const mode = panel.querySelector('.task-combobox input[type="hidden"]');
                if (mode && mode.value === 'exact' && raw) summary = raw;
                else if (raw.trim().length > 1) summary = 'Contains: ' + raw.trim();
            }
            const badge = filter.querySelector('[data-filter-summary]');
            badge.textContent = summary;
            badge.title = summary;
            badge.hidden = !summary;
            const icon = filter.querySelector('.column-filter-icon');
            icon.classList.toggle('text-ctp-blue', !!summary);
            icon.classList.toggle('text-ctp-subtext0', !summary);
            const clear = panel.querySelector('.column-filter-clear');
            if (clear) clear.disabled = !raw || (kind === 'status' && raw === 'null');
            const combo = panel.querySelector('.task-combobox');
            if (combo) {
                combo.querySelector('.task-combobox-state').textContent = summary
                    ? (modeIsExact(combo) ? 'Exact match' : 'Partial match')
                    : (raw.trim() ? 'Type at least 2 characters, or select a suggestion.' : '');
            }
        });
        updateSortLinks();
    }

    function modeIsExact(combo) {
        return combo.querySelector('input[type="hidden"]').value === 'exact';
    }

    function initCombo(combo) {
        if (initialized.has(combo)) return;
        initialized.add(combo);
        const input = combo.querySelector('[role="combobox"]');
        const mode = combo.querySelector('input[type="hidden"]');
        const options = combo.querySelector('.task-combobox-options');
        const filter = combo.closest('.column-filter');
        let active = -1;
        let timer;
        let controller;

        const clear = filter.querySelector('.column-filter-clear');
        clear.addEventListener('pointerdown', function (event) {
            // Blurring the input hides suggestions and moves the button before the click.
            event.preventDefault();
        });
        clear.addEventListener('click', function () {
            clearTimeout(timer);
            if (controller) controller.abort();
        });

        function highlight(index) {
            const buttons = Array.from(options.querySelectorAll('[role="option"]'));
            active = index;
            buttons.forEach(function (button, position) {
                button.setAttribute('aria-selected', position === active ? 'true' : 'false');
            });
            if (buttons[active]) {
                input.setAttribute('aria-activedescendant', buttons[active].id);
                const itemRect = buttons[active].getBoundingClientRect();
                const listRect = options.getBoundingClientRect();
                if (itemRect.top < listRect.top) options.scrollTop += itemRect.top - listRect.top;
                else if (itemRect.bottom > listRect.bottom) options.scrollTop += itemRect.bottom - listRect.bottom;
            } else input.removeAttribute('aria-activedescendant');
        }

        function select(value) {
            clearTimeout(timer);
            if (controller) controller.abort();
            input.value = value;
            mode.value = 'exact';
            hideOptions(combo);
            input.focus({ preventScroll: true });
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }

        async function loadValues() {
            if (controller) controller.abort();
            controller = new AbortController();
            const current = controller;
            const url = new URL(combo.dataset.valuesUrl, window.location.origin);
            url.searchParams.set('q', input.value);
            input.setAttribute('aria-busy', 'true');
            try {
                const response = await fetch(url, { signal: current.signal, credentials: 'same-origin' });
                if (!response.ok) throw new Error('Suggestions are unavailable');
                const values = await response.json();
                if (current.signal.aborted || document.activeElement !== input || filter.querySelector('.column-filter-panel').classList.contains('hidden')) return false;
                options.replaceChildren();
                active = -1;
                values.slice(0, 20).forEach(function (value, index) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.tabIndex = -1;
                    button.setAttribute('role', 'option');
                    button.setAttribute('aria-selected', 'false');
                    button.id = input.getAttribute('aria-controls') + '-' + index;
                    button.textContent = value;
                    button.addEventListener('pointerdown', function (event) { event.preventDefault(); });
                    button.addEventListener('click', function () { select(value); });
                    options.appendChild(button);
                });
                if (!values.length) {
                    const empty = document.createElement('p');
                    empty.className = 'task-combobox-empty';
                    empty.textContent = 'No suggestions. You can still filter by this text.';
                    options.appendChild(empty);
                }
                options.hidden = false;
                input.setAttribute('aria-expanded', 'true');
                input.removeAttribute('aria-activedescendant');
                placeFilterPanel(filter);
                return true;
            } catch (error) {
                if (error.name !== 'AbortError') {
                    hideOptions(combo);
                    combo.querySelector('.task-combobox-state').textContent = 'Suggestions unavailable. You can still type a filter.';
                }
            } finally {
                if (controller === current) input.removeAttribute('aria-busy');
            }
            return false;
        }

        input.addEventListener('focus', loadValues);
        input.addEventListener('input', function () {
            mode.value = 'contains';
            hideOptions(combo);
            options.replaceChildren();
            active = -1;
            syncHeaderFilters();
            clearTimeout(timer);
            if (controller) controller.abort();
            timer = setTimeout(loadValues, 200);
        });
        input.addEventListener('blur', function () {
            clearTimeout(timer);
            if (controller) controller.abort();
            hideOptions(combo);
        });
        input.addEventListener('keydown', function (event) {
            const buttons = Array.from(options.querySelectorAll('[role="option"]'));
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                if (options.hidden) {
                    clearTimeout(timer);
                    loadValues().then(function (loaded) {
                        if (loaded && !options.hidden) highlight(event.key === 'ArrowDown' ? 0 : options.querySelectorAll('[role="option"]').length - 1);
                    });
                } else if (buttons.length) {
                    const first = event.key === 'ArrowDown' ? 0 : buttons.length - 1;
                    const next = active < 0 ? first : (active + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
                    highlight(next);
                }
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (!options.hidden && buttons[active]) select(buttons[active].textContent);
                else {
                    clearTimeout(timer);
                    if (controller) controller.abort();
                    hideOptions(combo);
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            } else if (event.key === 'Escape' || event.key === 'Tab') hideOptions(combo);
        });
    }

    function initDates(container) {
        if (initialized.has(container)) return;
        initialized.add(container);
        const display = container.querySelector('.date-range-display');
        const start = container.querySelector('.date-range-start');
        const end = container.querySelector('.date-range-end');
        const clear = container.querySelector('.date-range-clear');
        let lastApplied = start.value + '|' + end.value;
        function applyDates() {
            const value = start.value + '|' + end.value;
            if (value === lastApplied) return;
            lastApplied = value;
            requestTasks();
        }
        function changed(dates) {
            start.value = dates[0] ? dates[0].toISOString() : '';
            end.value = dates[1] ? dates[1].toISOString() : '';
            clear.classList.toggle('hidden', !(start.value || end.value));
            syncHeaderFilters();
        }
        const picker = flatpickr(display, {
            mode: 'range', enableTime: true, dateFormat: 'M j, Y h:i K',
            defaultDate: [start.value, end.value].filter(Boolean).map(function (value) { return new Date(value); }),
            onChange: changed,
            onClose: applyDates,
        });
        dateRestorers.set(container, function () {
            picker.setDate([start.value, end.value].filter(Boolean).map(function (value) { return new Date(value); }), false);
            lastApplied = start.value + '|' + end.value;
            clear.classList.toggle('hidden', !(start.value || end.value));
        });
        clear.addEventListener('click', function () {
            picker.clear();
            changed([]);
            applyDates();
        });
    }

    function init() {
        document.querySelectorAll('.column-filter').forEach(function (filter) {
            if (initialized.has(filter)) return;
            initialized.add(filter);
            const panel = filter.querySelector('.column-filter-panel');
            const button = filter.querySelector('.column-filter-toggle');
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                const open = panel.classList.contains('hidden');
                closeFilterPanels();
                if (!open) return;
                panel.classList.remove('hidden');
                button.setAttribute('aria-expanded', 'true');
                placeFilterPanel(filter);
                const field = panel.querySelector('input:not([type="hidden"]), select');
                if (field) field.focus({ preventScroll: true });
            });
            const clear = panel.querySelector('.column-filter-clear');
            if (clear) clear.addEventListener('click', function () {
                const field = panel.querySelector('input:not([type="hidden"]), select');
                field.value = filter.dataset.filterKind === 'status' ? 'null' : '';
                const mode = panel.querySelector('.task-combobox input[type="hidden"]');
                if (mode) mode.value = 'contains';
                panel.querySelectorAll('.task-combobox').forEach(hideOptions);
                syncHeaderFilters();
                requestTasks();
            });
        });
        document.querySelectorAll('.task-combobox').forEach(initCombo);
        document.querySelectorAll('.date-range').forEach(initDates);
        const search = document.getElementById('search');
        const hint = document.getElementById('search-slash-hint');
        if (search && hint && !initialized.has(search)) {
            initialized.add(search);
            const update = function () { hint.hidden = document.activeElement === search || search.value !== ''; };
            ['input', 'focus', 'blur'].forEach(function (event) { search.addEventListener(event, update); });
            update();
        }
        const table = document.getElementById('task-list');
        const scroller = table && table.closest('.overflow-x-auto');
        if (scroller && !initialized.has(scroller)) {
            initialized.add(scroller);
            scroller.addEventListener('scroll', closeFilterPanels);
        }
        syncHeaderFilters();
    }

    document.addEventListener('click', function (event) {
        if (!event.target.closest('.column-filter, .flatpickr-calendar')) closeFilterPanels();
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') closeFilterPanels();
    });
    document.addEventListener('input', syncHeaderFilters);
    document.addEventListener('change', syncHeaderFilters);
    document.addEventListener('htmx:afterSwap', init);
    document.addEventListener('htmx:historyRestore', function () {
        const params = new URLSearchParams(window.location.search);
        document.querySelectorAll('.task-filter').forEach(function (field) {
            if (params.has(field.name)) field.value = params.get(field.name);
            else if (field.name === 'status') field.value = 'null';
            else if (field.name === 'name_match' || field.name === 'worker_match') field.value = 'contains';
            else if (field.name !== 'sort_by' && field.name !== 'sort_order') field.value = '';
        });
        closeFilterPanels();
        init();
        document.querySelectorAll('.date-range').forEach(function (container) {
            const restore = dateRestorers.get(container);
            if (restore) restore();
        });
        syncHeaderFilters();
    });
    window.addEventListener('resize', closeFilterPanels);
    window.addEventListener('scroll', closeFilterPanels);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
