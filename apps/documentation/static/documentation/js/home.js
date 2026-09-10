(function () {
  'use strict';

  var SEARCH_URL = '/search/';

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ── toast ─────────────────────────────────────────────── */
  function showToast(msg) {
    var t = $('toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { t.classList.add('hidden'); }, 2200);
  }

  /* ── category filter ───────────────────────────────────── */
  var siteList = $('siteList');
  var resultCount = $('resultCount');
  var emptyState = $('emptyState');
  var activeCat = 'All';

  function applyFilters() {
    if (!siteList) return;
    var cards = siteList.querySelectorAll('.site-card');
    var shown = 0;
    cards.forEach(function (card) {
      var cat = card.getAttribute('data-cat') || '';
      var show = activeCat === 'All' || cat === activeCat;
      card.classList.toggle('hidden', !show);
      if (show) shown++;
    });
    if (resultCount) resultCount.textContent = shown + ' of ' + cards.length;
    if (emptyState) emptyState.classList.toggle('hidden', shown !== 0);
  }

  var filters = $('filters');
  if (filters) {
    filters.addEventListener('click', function (e) {
      var btn = e.target.closest('.catBtn');
      if (!btn) return;
      activeCat = btn.getAttribute('data-cat');
      filters.querySelectorAll('.catBtn').forEach(function (x) {
        var on = x === btn;
        x.classList.toggle('active', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      applyFilters();
    });
  }

  var clearFilters = $('clearFilters');
  if (clearFilters) {
    clearFilters.addEventListener('click', function () {
      activeCat = 'All';
      if (filters) {
        filters.querySelectorAll('.catBtn').forEach(function (x) {
          var on = x.getAttribute('data-cat') === 'All';
          x.classList.toggle('active', on);
          x.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
      }
      applyFilters();
    });
  }

  /* ── command palette ───────────────────────────────────── */
  var palette = $('palette');
  var palInput = $('palInput');
  var palList = $('palList');
  var palCount = $('palCount');
  var palResults = [];
  var palActive = 0;
  var palSeq = 0;

  function highlight(text, q) {
    var t = esc(text);
    if (!q) return t;
    var i = t.toLowerCase().indexOf(q);
    if (i < 0) return t;
    return t.slice(0, i) + '<mark class="pal-mark">' + t.slice(i, i + q.length) + '</mark>' + t.slice(i + q.length);
  }

  function renderResults(results, q) {
    palResults = results || [];
    palActive = 0;
    if (palResults.length === 0) {
      palList.innerHTML = '<div class="px-4 py-10 text-center text-sm text-muted">No matches for &ldquo;' + esc(palInput.value) + '&rdquo;.<br>Try &ldquo;install&rdquo;, &ldquo;api&rdquo;, or &ldquo;sso&rdquo;.</div>';
      palCount.textContent = '0 results';
      return;
    }
    var groups = [];
    var buckets = {};
    palResults.forEach(function (r) {
      var key = r.type === 'site' ? 'Documentation sites' : 'Articles';
      if (!buckets[key]) { buckets[key] = []; groups.push(key); }
      buckets[key].push(r);
    });
    var html = '';
    groups.forEach(function (g) {
      html += '<div class="pal-group">' + esc(g) + '</div>';
      buckets[g].forEach(function (r) {
        var idx = palResults.indexOf(r);
        html += '<div role="option" aria-selected="false">'
          + '<button class="pal-item' + (idx === palActive ? ' active' : '') + '" data-i="' + idx + '" type="button">'
          + '<span class="min-w-0 flex-1">'
          + '<span class="block text-sm font-medium text-ink">' + highlight(r.title, q) + '</span>'
          + (r.excerpt ? '<span class="block text-xs text-muted truncate">' + highlight(r.excerpt, q) + '</span>' : '')
          + '</span>'
          + '<span class="ghost mono text-[11px] shrink-0 hidden sm:inline">' + esc(r.sub) + '</span>'
          + '</button></div>';
      });
    });
    palList.innerHTML = html;
    palCount.textContent = palResults.length + (palResults.length === 1 ? ' result' : ' results');
  }

  function setActive(i) {
    if (i < 0 || i >= palResults.length) return;
    palActive = i;
    var items = palList.querySelectorAll('.pal-item');
    items.forEach(function (el, idx) {
      el.classList.toggle('active', idx === palActive);
      el.parentElement.setAttribute('aria-selected', idx === palActive ? 'true' : 'false');
    });
    var el = items[palActive];
    if (el) {
      var top = el.offsetTop;
      var bottom = top + el.offsetHeight;
      if (top < palList.scrollTop) palList.scrollTop = top - 8;
      else if (bottom > palList.scrollTop + palList.clientHeight) palList.scrollTop = bottom - palList.clientHeight + 8;
    }
  }

  function renderPalette() {
    var q = palInput.value.trim().toLowerCase();
    var seq = ++palSeq;
    if (!q) {
      palResults = [];
      palActive = 0;
      palList.innerHTML = '<div class="px-4 py-10 text-center text-sm text-muted">Start typing to search sites and articles&hellip;</div>';
      palCount.textContent = '';
      return;
    }
    fetch(SEARCH_URL + '?q=' + encodeURIComponent(q), { headers: { 'Accept': 'application/json' } })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        if (seq !== palSeq) return;
        renderResults(data.results || [], q);
      })
      .catch(function () {
        if (seq !== palSeq) return;
        renderResults([], q);
      });
  }

  function openPalette(seed) {
    palette.classList.remove('hidden');
    palInput.value = seed || '';
    renderPalette();
    palInput.focus();
  }
  function closePalette() { palette.classList.add('hidden'); }
  function openResult() {
    var r = palResults[palActive];
    if (!r) return;
    closePalette();
    window.location.href = r.href;
  }

  ['palOpen', 'palOpenHero', 'palOpenSites'].forEach(function (id) {
    var el = $(id);
    if (el) el.addEventListener('click', function () { openPalette(''); });
  });
  var palOpenMobile = $('palOpenMobile');
  if (palOpenMobile) palOpenMobile.addEventListener('click', function () { closeDrawer(); openPalette(''); });

  if (palInput) {
    var debounce;
    palInput.addEventListener('input', function () {
      clearTimeout(debounce);
      debounce = setTimeout(renderPalette, 150);
    });
    palInput.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(palActive + 1, palResults.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(palActive - 1, 0)); }
      else if (e.key === 'Enter') { e.preventDefault(); openResult(); }
    });
  }
  if (palList) {
    palList.addEventListener('click', function (e) {
      var b = e.target.closest('.pal-item');
      if (!b) return;
      var idx = Number(b.getAttribute('data-i'));
      if (!Number.isNaN(idx)) { palActive = idx; openResult(); }
    });
    palList.addEventListener('mousemove', function (e) {
      var b = e.target.closest('.pal-item');
      if (b) setActive(Number(b.getAttribute('data-i')));
    });
  }
  if (palette) {
    palette.addEventListener('mousedown', function (e) { if (e.target === palette) closePalette(); });
  }
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (palette.classList.contains('hidden')) openPalette(''); else closePalette();
    } else if (e.key === 'Escape' && palette && !palette.classList.contains('hidden')) {
      closePalette();
    }
  });

  document.querySelectorAll('.jump').forEach(function (b) {
    b.addEventListener('click', function () { openPalette(b.getAttribute('data-q')); });
  });

  /* ── copy button ───────────────────────────────────────── */
  document.querySelectorAll('.codeblock-copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var codeEl = $('quickCode');
      var code = codeEl ? codeEl.innerText : (btn.getAttribute('data-copy') || '');
      var done = function () {
        btn.textContent = '\u2713 Copied';
        setTimeout(function () { btn.textContent = 'Copy'; }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done).catch(done);
      } else {
        done();
      }
    });
  });

  /* ── mobile drawer ─────────────────────────────────────── */
  var drawer = $('drawer');
  function openDrawer() {
    if (!drawer) return;
    drawer.classList.remove('hidden');
    var menuBtn = $('menuBtn');
    if (menuBtn) menuBtn.setAttribute('aria-expanded', 'true');
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.add('hidden');
    var menuBtn = $('menuBtn');
    if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
  }
  var menuBtn = $('menuBtn');
  if (menuBtn) menuBtn.addEventListener('click', openDrawer);
  var drawerClose = $('drawerClose');
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  var drawerOverlay = $('drawerOverlay');
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);
  if (drawer) {
    drawer.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', closeDrawer);
    });
  }

  /* ── neutralize placeholder anchors ────────────────────── */
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href="#"]');
    if (a) e.preventDefault();
  });

  applyFilters();
})();
