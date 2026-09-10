(function () {
  var themeBtn = document.getElementById('themeBtn');
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    var sun = document.getElementById('themeSun');
    var moon = document.getElementById('themeMoon');
    if (sun) sun.classList.toggle('hidden', t === 'dark');
    if (moon) moon.classList.toggle('hidden', t !== 'dark');
    if (typeof window.renderMermaid === 'function') window.renderMermaid();
  }
  function cycleTheme() {
    var cur = document.documentElement.getAttribute('data-theme');
    var next = cur === 'light' ? 'dark' : 'light';
    localStorage.setItem('od-theme', next);
    applyTheme(next);
  }
  if (themeBtn) themeBtn.addEventListener('click', cycleTheme);
  applyTheme(document.documentElement.getAttribute('data-theme') || 'light');
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    if (localStorage.getItem('od-theme') === 'system') {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
})();
