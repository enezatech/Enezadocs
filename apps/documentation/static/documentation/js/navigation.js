(function () {
  var drawer = document.getElementById('drawer');
  function openDrawer() {
    if (drawer) drawer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
  function closeDrawer() {
    if (drawer) drawer.classList.add('hidden');
    document.body.style.overflow = '';
  }
  var mobileMenu = document.getElementById('mobileMenu');
  var drawerClose = document.getElementById('drawerClose');
  var drawerOverlay = document.getElementById('drawerOverlay');
  if (mobileMenu) mobileMenu.addEventListener('click', openDrawer);
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

  document.querySelectorAll('.nav-group > button, .nav-page-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var group = btn.closest('.nav-group') || btn.parentElement;
      group.classList.toggle('open');
    });
  });

  document.querySelectorAll('.nav-group a[data-close-drawer]').forEach(function (a) {
    a.addEventListener('click', closeDrawer);
  });
})();
