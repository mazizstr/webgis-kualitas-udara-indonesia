// Layer trajektori HYSPLIT dari file GeoJSON (hasil ekspor ArcGIS Pro / QGIS).
// Data dimuat dari /data/trajektori.geojson hanya saat kotaknya dicentang pertama kali.
// Dimuat SETELAH script utama di index.html, jadi variabel `map` sudah ada.
(function () {
  if (typeof map === 'undefined') return;
  const $ = (id) => document.getElementById(id);

  const DATA_URL = '/data/trajektori.geojson';
  const MAX_ARROWS = 600;           // batas jumlah panah supaya peta tetap ringan

  // Pane khusus: di atas data & batas wilayah
  map.createPane('trajektori');
  map.getPane('trajektori').style.zIndex = 455;
  const renderer = L.canvas({ pane: 'trajektori', padding: 0.5 });  // cepat untuk banyak garis

  let geo = null, lines = null, arrows = null;
  let loaded = false, loading = false, lineCount = 0;

  // ---------- Panel ----------
  const box = document.createElement('div');
  box.className = 'panel';
  box.innerHTML =
    '<div class="ptitle">Trajektori HYSPLIT</div>' +
    '<div style="font-size:11px;color:#333;margin-bottom:6px">' +
    'Lintasan <b>satu parsel udara</b> (forward trajectory), bukan peta sebaran asap.</div>' +
    '<div class="row">' +
    '<label class="chk"><input type="checkbox" id="tj-show" />Tampilkan lintasan</label>' +
    '<input type="range" id="tj-op" min="0.1" max="1" step="0.1" value="0.6" /></div>' +
    '<label class="chk"><input type="checkbox" id="tj-arrow" checked />Panah arah gerak</label>' +
    '<label class="chk"><input type="checkbox" id="tj-flip" />Balik arah panah</label>' +
    '<button id="tj-zoom" style="margin-top:8px;background:#5f6368;padding:6px;font-size:13px">Zoom ke trajektori</button>' +
    '<div id="tj-msg" style="font-size:12px;margin-top:8px"></div>';

  const anchor = document.querySelector('.panel') || $('legend-labels');
  if (anchor) anchor.insertAdjacentElement('afterend', box);
  else $('sidebar').appendChild(box);

  function msg(text, isError) {
    $('tj-msg').style.color = isError ? '#c5221f' : '#1b5e20';
    $('tj-msg').textContent = text;
  }

  // ---------- Util ----------
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function bearing(a, b) {            // a, b = [lon, lat]
    const r = (x) => (x * Math.PI) / 180;
    const y = Math.sin(r(b[0] - a[0])) * Math.cos(r(b[1]));
    const x = Math.cos(r(a[1])) * Math.sin(r(b[1])) -
              Math.sin(r(a[1])) * Math.cos(r(b[1])) * Math.cos(r(b[0] - a[0]));
    return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  }

  function arrowIcon(deg) {
    return L.divIcon({
      className: '',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
      html: '<div style="transform:rotate(' + deg.toFixed(0) + 'deg);color:#111;font-size:14px;' +
            'line-height:14px;text-shadow:0 0 2px #fff,0 0 2px #fff">▲</div>',
    });
  }

  // Ujung (dua titik terakhir) sebuah garis: kembalikan [titikSebelum, titikAkhir] atau null
  function lastSegment(geom) {
    let coords = geom.type === 'LineString' ? geom.coordinates
               : geom.type === 'MultiLineString' ? geom.coordinates[geom.coordinates.length - 1]
               : null;
    if (!coords) return null;
    for (let i = coords.length - 1; i > 0; i--) {
      const a = coords[i - 1], b = coords[i];
      if (a[0] !== b[0] || a[1] !== b[1]) return [a, b];
    }
    return null;
  }

  // ---------- Bangun layer ----------
  function buildArrows() {
    if (arrows) { map.removeLayer(arrows); arrows = null; }
    const feats = geo.features.filter((f) => f.geometry && /LineString/.test(f.geometry.type));
    const step = Math.max(1, Math.ceil(feats.length / MAX_ARROWS));
    const flip = $('tj-flip').checked;
    arrows = L.layerGroup();
    feats.forEach((f, i) => {
      if (i % step !== 0) return;
      const seg = lastSegment(f.geometry);
      if (!seg) return;
      const deg = flip ? bearing(seg[1], seg[0]) : bearing(seg[0], seg[1]);
      const tip = flip ? seg[0] : seg[1];
      L.marker([tip[1], tip[0]], {
        pane: 'trajektori', icon: arrowIcon(deg), interactive: false, keyboard: false,
      }).addTo(arrows);
    });
  }

  function popupHtml(props) {
    const rows = Object.entries(props || {}).slice(0, 12)
      .map(([k, v]) => '<tr><td><b>' + esc(k) + '</b></td><td>' + esc(v) + '</td></tr>').join('');
    return rows ? '<table style="font-size:12px">' + rows + '</table>' : 'Tidak ada atribut.';
  }

  function build() {
    lineCount = geo.features.filter((f) => f.geometry && /LineString/.test(f.geometry.type)).length;
    if (!lineCount) {
      throw new Error('Tidak ada garis (LineString) di file. Pastikan yang diekspor layer garis, bukan titik.');
    }
    lines = L.geoJSON(geo, {
      renderer,
      bubblingMouseEvents: false,
      filter: (f) => f.geometry && /LineString/.test(f.geometry.type),
      style: () => ({ color: '#222', weight: 1, opacity: parseFloat($('tj-op').value) }),
      onEachFeature: (f, layer) => {
        layer.on('click', (e) => {
          L.popup().setLatLng(e.latlng).setContent(popupHtml(f.properties)).openOn(map);
        });
      },
    });
    buildArrows();
  }

  async function load() {
    if (loaded || loading) return loaded;
    loading = true;
    msg('Memuat data trajektori...');
    try {
      const res = await fetch(DATA_URL);
      if (!res.ok) throw new Error('File ' + DATA_URL + ' tidak ditemukan (kode ' + res.status + ').');
      geo = await res.json();
      build();
      loaded = true;
      msg(lineCount + ' lintasan dimuat. Klik garis untuk melihat atributnya.');
    } catch (e) {
      msg('Gagal: ' + e.message, true);
      $('tj-show').checked = false;
    } finally {
      loading = false;
    }
    return loaded;
  }

  function sync() {
    if (!loaded) return;
    const show = $('tj-show').checked;
    if (show) lines.addTo(map); else map.removeLayer(lines);
    if (show && $('tj-arrow').checked) arrows.addTo(map);
    else if (arrows) map.removeLayer(arrows);
  }

  // ---------- Kontrol ----------
  $('tj-show').addEventListener('change', async () => {
    if ($('tj-show').checked && !(await load())) return;
    sync();
  });
  $('tj-arrow').addEventListener('change', sync);
  $('tj-flip').addEventListener('change', () => {
    if (!loaded) return;
    buildArrows();
    sync();
  });
  $('tj-op').addEventListener('input', (e) => {
    if (lines) lines.setStyle({ opacity: parseFloat(e.target.value) });
  });
  $('tj-zoom').addEventListener('click', async () => {
    if (!$('tj-show').checked) { $('tj-show').checked = true; if (!(await load())) return; sync(); }
    if (lines) map.fitBounds(lines.getBounds().pad(0.1));
  });
})();
