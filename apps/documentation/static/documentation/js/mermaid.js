(function () {
  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark'
      ? 'dark'
      : 'neutral';
  }

  async function renderAll() {
    var els = document.querySelectorAll('pre.mermaid');
    if (!els.length || typeof mermaid === 'undefined') return;
    try {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: currentTheme(),
        fontFamily: 'inherit',
      });
    } catch (e) {
      return;
    }
    var counter = 0;
    for (var j = 0; j < els.length; j++) {
      var el = els[j];
      var src = el.getAttribute('data-src');
      if (src === null) {
        src = el.textContent;
        el.setAttribute('data-src', src);
      }
      try {
        counter += 1;
        var out = await mermaid.render('mmd-' + counter, src);
        el.innerHTML = out.svg;
        if (out.bindFunctions) out.bindFunctions(el);
      } catch (err) {
        el.innerHTML = '';
        var msg = document.createElement('div');
        msg.className = 'mermaid-error';
        msg.textContent = src;
        el.appendChild(msg);
      }
    }
  }

  window.renderMermaid = renderAll;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderAll);
  } else {
    renderAll();
  }
})();
