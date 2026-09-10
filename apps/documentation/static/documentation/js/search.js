(function () {
  var modal = document.getElementById('searchModal');
  if (!modal) return;
  var searchUrl = modal.getAttribute('data-search-url') || '';
  var docsBase = searchUrl.replace(/\/search\/?$/, '');
  var input = document.getElementById('searchInput');
  var results = document.getElementById('searchResults');
  var overlay = document.getElementById('searchOverlay');
  var sIdx = -1;

  function open() {
    modal.classList.remove('hidden');
    if (input) {
      input.value = '';
      setTimeout(function () { input.focus(); }, 10);
    }
    render('');
  }
  function close() {
    modal.classList.add('hidden');
    sIdx = -1;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function folderOf(path) {
    var parts = String(path || '').split('/');
    if (parts.length <= 1) return 'Documentation';
    return parts.slice(0, -1).join(' / ');
  }

  function render(q, items) {
    results.innerHTML = '';
    sIdx = -1;
    if (!items || !items.length) {
      results.innerHTML = '<li class="px-4 py-8 text-center text-muted text-sm">No results for "' + esc(q) + '"</li>';
      return;
    }
    items.forEach(function (it, i) {
      var li = document.createElement('li');
      li.dataset.i = i;
      var linkPath = it.url_path || it.path;
      li.innerHTML =
        '<a href="' + docsBase + '/' + encodeURI(linkPath) + '/" data-search-nav="' + esc(linkPath) + '" class="flex items-start gap-3 px-4 py-3 hover:bg-bgsoft transition-colors">' +
        '<div class="min-w-0"><div class="text-sm font-medium text-ink">' + esc(it.title) + '</div>' +
        '<div class="text-xs text-muted">' + esc(folderOf(it.path)) + '</div>' +
        (it.description ? '<div class="text-sm text-muted mt-0.5 truncate">' + esc(it.description) + '</div>' : '') +
        '</div></a>';
      results.appendChild(li);
    });
  }

  function doSearch(q) {
    if (!q) return;
    fetch(searchUrl + '?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (data) { render(q, data.results); })
      .catch(function () { results.innerHTML = '<li class="px-4 py-8 text-center text-muted text-sm">Search unavailable</li>'; });
  }

  var debounce;
  if (input) {
    input.addEventListener('input', function () {
      var q = input.value.trim();
      clearTimeout(debounce);
      if (!q) { render('', []); return; }
      debounce = setTimeout(function () { doSearch(q); }, 150);
    });
  }

  results.addEventListener('click', function (e) {
    var a = e.target.closest('[data-search-nav]');
    if (a) close();
  });
  results.addEventListener('mousemove', function (e) {
    var li = e.target.closest('li');
    if (!li) return;
    sIdx = parseInt(li.dataset.i);
    highlight();
  });

  function highlight() {
    results.querySelectorAll('li').forEach(function (el, i) {
      el.querySelector('a').classList.toggle('bg-bgsoft', i === sIdx);
    });
  }

  modal.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var a = results.querySelector('li:nth-child(' + (sIdx + 1) + ') a');
      if (a) { window.location.href = a.getAttribute('href'); close(); }
    }
    if (e.key === 'ArrowDown') { e.preventDefault(); sIdx = Math.min(sIdx + 1, results.children.length - 1); highlight(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); sIdx = Math.max(sIdx - 1, 0); highlight(); }
  });

  var openDesktop = document.getElementById('searchOpen');
  var openMobile = document.getElementById('searchOpenMobile');
  if (openDesktop) openDesktop.addEventListener('click', open);
  if (openMobile) openMobile.addEventListener('click', open);
  if (overlay) overlay.addEventListener('click', close);

  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); }
    if (e.key === 'Escape') { close(); }
  });
})();
