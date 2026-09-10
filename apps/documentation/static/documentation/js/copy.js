(function () {
  document.querySelectorAll('.codeblock-copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var code = btn.getAttribute('data-copy') || '';
      navigator.clipboard.writeText(code).then(function () {
        var span = btn.querySelector('span');
        btn.querySelector('svg').outerHTML = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg>';
        if (span) span.textContent = 'Copied';
        setTimeout(function () {
          btn.querySelector('svg').outerHTML = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>';
          if (span) span.textContent = 'Copy';
        }, 1400);
      });
    });
  });
})();
