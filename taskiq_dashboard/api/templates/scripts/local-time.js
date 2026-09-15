(function () {
    function applyLocalTimes(root) {
        root.querySelectorAll('[data-utc-time]').forEach(function (el) {
            var date = new Date(el.dataset.utcTime);
            if (isNaN(date.getTime())) return;
            el.textContent = date.toLocaleString();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyLocalTimes(document);
    });
    document.addEventListener('htmx:afterSettle', function (evt) {
        applyLocalTimes(evt.target);
    });
})();
