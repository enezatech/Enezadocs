(function () {
  var content = document.getElementById('content');
  var list = document.getElementById('tocList');
  if (!content || !list) return;

  var items = [];
  list.querySelectorAll('li').forEach(function (li) {
    var a = li.querySelector('a');
    if (!a) return;
    var id = li.dataset.target;
    items.push({ li: li, id: id });
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var h = document.getElementById(id);
      if (h) content.scrollTo({ top: h.getBoundingClientRect().top + content.scrollTop - 92, behavior: 'smooth' });
    });
  });

  function setActive(id) {
    items.forEach(function (it) {
      var a = it.li.querySelector('a');
      if (it.id === id) {
        a.classList.add('border-accent', 'text-ink', 'font-medium');
        a.classList.remove('border-transparent', 'text-muted');
      } else {
        a.classList.remove('border-accent', 'text-ink', 'font-medium');
        a.classList.add('border-transparent', 'text-muted');
      }
    });
  }

  var heads = Array.prototype.slice.call(document.querySelectorAll('#article h2, #article h3'));
  if (!heads.length || !('IntersectionObserver' in window)) return;

  var map = new Map();
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) map.set(en.target.id, en.boundingClientRect.top);
      else map.delete(en.target.id);
    });
    var active = null;
    var best = Infinity;
    map.forEach(function (v, k) { if (v < best) { best = v; active = k; } });
    if (active !== null) setActive(active);
  }, { root: content, rootMargin: '-90px 0px -60% 0px', threshold: 0 });

  heads.forEach(function (h) { obs.observe(h); });
})();
