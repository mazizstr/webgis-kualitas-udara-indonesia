// Fitur "Bagikan tautan": menyalin alamat yang membawa kondisi peta saat ini
// (parameter, tanggal, posisi & zoom, dan status layer PM2.5).
// Pemulihan parameter/tanggal/posisi dilakukan di init() index.html (lihat panduan).
(function () {
  const $ = (id) => document.getElementById(id);
  const apply = $('apply');
  if (!apply || typeof map === 'undefined') return;

  // ---------- Tombol ----------
  const btn = document.createElement('button');
  btn.id = 'share-btn';
  btn.textContent = 'Bagikan tautan';
  btn.style.cssText = 'background:#5f6368;margin-top:8px';
  apply.insertAdjacentElement('afterend', btn);

  // ---------- Susun tautan ----------
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
    });

    const pm = $('ly-pm');
    if (pm && pm.checked && !pm.disabled) q.set('pm', '1');

    return location.origin + location.pathname + '?' + q.toString();
  }

  btn.addEventListener('click', async () => {
    const link = buildLink();
    try {
      await navigator.clipboard.writeText(link);
    } catch (e) {
      // Cadangan jika browser menolak akses clipboard
      window.prompt('Salin tautan ini (Ctrl + C):', link);
      return;
    }
    btn.textContent = 'Tautan disalin ✓';
    setTimeout(() => { btn.textContent = 'Bagikan tautan'; }, 2000);
  });

  // ---------- Pulihkan layer PM2.5 jika tautan membawa pm=1 ----------
  const q = new URLSearchParams(location.search);
  if (q.get('pm') === '1') {
    let tries = 0;
    const timer = setInterval(() => {
      tries++;
      const ready = $('param') && $('param').options.length > 0 && $('start').value;
      if (ready && $('pm-run')) {
        clearInterval(timer);
        setTimeout(() => $('pm-run').click(), 800);
      } else if (tries > 60) {
        clearInterval(timer);   // menyerah setelah ~15 detik
      }
    }, 250);
  }
})();
