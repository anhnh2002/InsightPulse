// Client-side bookmarks + read marks, stored in localStorage (per browser, no accounts).
// State is keyed by language-stripped path so /posts/x/ and /vi/posts/x/ share it.
(function () {
    var cfg = window.__ipBookmarks || {};
    var labels = cfg.labels || {};
    var LANG = cfg.lang || "en";
    var PREFIX = LANG === "vi" ? "/vi" : "";
    var BM_KEY = "ip:bookmarks";
    var VIEW_KEY = "ip:viewed";

    function load(key) {
        try { return JSON.parse(localStorage.getItem(key)) || {}; } catch (e) { return {}; }
    }
    function save(key, val) {
        try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* private mode */ }
    }
    function strip(path) {
        return path.replace(/^\/vi(\/|$)/, "$1");
    }
    function isPostPath(path) {
        return path.indexOf("/posts/") === 0 && path.length > "/posts/".length;
    }

    function toggleBookmark(path, meta) {
        var bms = load(BM_KEY);
        if (bms[path]) {
            delete bms[path];
        } else {
            bms[path] = { t: meta.title || path, d: meta.date || "", a: Date.now() };
        }
        save(BM_KEY, bms);
        return !!bms[path];
    }
    function setViewed(path, on) {
        var viewed = load(VIEW_KEY);
        if (on) { viewed[path] = Date.now(); } else { delete viewed[path]; }
        save(VIEW_KEY, viewed);
    }

    function decorateListEntries() {
        var bms = load(BM_KEY);
        var viewed = load(VIEW_KEY);
        var entries = document.querySelectorAll("article.post-entry, article.first-entry");
        entries.forEach(function (entry) {
            var link = entry.querySelector("a.entry-link");
            if (!link) return;
            var path = strip(new URL(link.href).pathname);
            if (!isPostPath(path)) return;

            if (viewed[path]) entry.classList.add("ip-viewed");

            var btn = document.createElement("button");
            btn.className = "ip-bm-btn" + (bms[path] ? " active" : "");
            btn.textContent = bms[path] ? "★" : "☆";
            btn.title = bms[path] ? (labels.rm || "Bookmarked") : (labels.add || "Bookmark");
            btn.setAttribute("aria-label", btn.title);
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                var h2 = entry.querySelector("h2");
                var foot = entry.querySelector(".entry-footer");
                var on = toggleBookmark(path, {
                    title: h2 ? h2.textContent.trim() : path,
                    date: foot ? foot.textContent.split("·")[0].trim() : ""
                });
                btn.classList.toggle("active", on);
                btn.textContent = on ? "★" : "☆";
                btn.title = on ? (labels.rm || "Bookmarked") : (labels.add || "Bookmark");
            });
            entry.appendChild(btn);
        });
    }

    function decorateSinglePost() {
        var article = document.querySelector("article.post-single");
        var path = strip(location.pathname);
        if (!article || !isPostPath(path)) return;

        var header = article.querySelector(".post-header");
        if (!header) return;

        var titleEl = article.querySelector("h1.post-title");
        var meta = {
            title: titleEl ? titleEl.textContent.trim() : document.title,
            date: (cfg.page && cfg.page.date) || ""
        };

        var row = document.createElement("div");
        row.className = "ip-post-actions";

        var bmBtn = document.createElement("button");
        var readBtn = document.createElement("button");

        function renderBm() {
            var on = !!load(BM_KEY)[path];
            bmBtn.classList.toggle("active", on);
            bmBtn.textContent = on ? (labels.rm || "★ Bookmarked") : (labels.add || "☆ Bookmark");
        }
        function renderRead() {
            var on = !!load(VIEW_KEY)[path];
            readBtn.classList.toggle("active", on);
            readBtn.textContent = on ? (labels.unread || "✓ Read") : (labels.read || "Mark as read");
        }

        bmBtn.addEventListener("click", function () {
            toggleBookmark(path, meta);
            renderBm();
        });
        readBtn.addEventListener("click", function () {
            setViewed(path, !load(VIEW_KEY)[path]);
            renderRead();
        });

        renderBm();
        renderRead();
        row.appendChild(bmBtn);
        row.appendChild(readBtn);
        header.appendChild(row);

        // Auto-mark as read after 20s on the page (explicit button can undo).
        setTimeout(function () {
            if (!load(VIEW_KEY)[path]) {
                setViewed(path, true);
                renderRead();
            }
        }, 20000);
    }

    function renderBookmarksPage() {
        var root = document.getElementById("ip-bookmarks");
        if (!root) return;
        var bms = load(BM_KEY);
        var paths = Object.keys(bms).sort(function (a, b) { return (bms[b].a || 0) - (bms[a].a || 0); });

        root.textContent = "";
        if (!paths.length) {
            var p = document.createElement("p");
            p.className = "ip-bm-empty";
            p.textContent = labels.empty || "No bookmarks yet.";
            root.appendChild(p);
            return;
        }
        paths.forEach(function (path) {
            var item = document.createElement("div");
            item.className = "ip-bm-item";

            var a = document.createElement("a");
            a.href = PREFIX + path;
            a.textContent = bms[path].t || path;

            var date = document.createElement("span");
            date.className = "ip-bm-date";
            date.textContent = bms[path].d || "";

            var rm = document.createElement("button");
            rm.className = "ip-bm-remove";
            rm.textContent = "✕";
            rm.title = labels.rm || "Remove";
            rm.setAttribute("aria-label", rm.title);
            rm.addEventListener("click", function () {
                toggleBookmark(path, {});
                renderBookmarksPage();
            });

            item.appendChild(a);
            item.appendChild(date);
            item.appendChild(rm);
            root.appendChild(item);
        });
    }

    function init() {
        decorateListEntries();
        decorateSinglePost();
        renderBookmarksPage();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
