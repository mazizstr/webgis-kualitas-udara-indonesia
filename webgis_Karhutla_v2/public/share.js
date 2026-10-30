// Fitur "Bagikan tautan": menyalin alamat yang membawa kondisi peta saat ini
// (parameter, tanggal, posisi & zoom, dan status layer batas wilayah).
// Pemulihannya dilakukan di init() pada templates/index.html.
(function () {
  const $ = (id) => document.getElementById(id);
  const apply = $('apply');
  if (!apply || typeof map === 'undefined') return;

  const btn = document.createElement('button');
  btn.id = 'share-btn';
  btn.textContent = 'Bagikan tautan';
  btn.style.cssText = 'background:#5f6368;margin-top:8px';
  apply.insertAdjacentElement('afterend', btn);

  const flag = (id) => ($(id) && $(id).checked ? '1' : '0');

  function buildLink() {
    const c = map.getCenter();
    // `current` = parameter & tanggal yang SEDANG tampil di peta (dari index.html)
    const st = (typeof current !== 'undefined' && current)
      ? current
      : { param: $('param').value, start: $('start').value, end: $('end').value };

    const q = new URLSearchParams({
      param: st.param,
      start: st.start,
      end: st.end,
      lat: c.lat.toFixed(4),
      lng: c.lng.toFixed(4),
      z: String(map.getZoom()),
      bn: flag('ly-country'),
      bp: flag('ly-prov'),
      bb: flag('ly-aoi'),
    });
    return location.origin + location.pathname + '?' + q.toString();
  }

  btn.addEventListener('click', async () => {
    const link = buildLink();
    try {
      await navigator.clipboard.writeText(link);
    } catch (e) {
      window.prompt('Salin tautan ini (Ctrl + C):', link);  // cadangan
      return;
    }
    btn.textContent = 'Tautan disalin ✓';
    setTimeout(() => { btn.textContent = 'Bagikan tautan'; }, 2000);
  });
})();
