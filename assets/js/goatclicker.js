document.addEventListener('click', function(event) {
  const a = event.target.closest('a');
  if (!a) return;
  const p = a.getAttribute('data-content-path');
  if (p) {
    window.goatcounter.count({
      event: true,
      path: "download:"+p,
      title: a.getAttribute('data-content-title') + ' -- ' + a.getAttribute('data-content-authors'),
    });
    return;
  }
  const value = (a.getAttribute('data-content-value') || a.getAttribute('ga-event-value'))*1;
  if (a.host == document.location.host || value == 0) return;
  window.goatcounter.count({
    event: true,
    path: a.href,
    title: a.text + " @ " + document.location.pathname,
  });
}, {useCapture: true});