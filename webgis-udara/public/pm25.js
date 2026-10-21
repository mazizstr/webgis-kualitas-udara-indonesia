// Fitur estimasi PM2.5 (regresi) + kontrol layer (on/off & transparansi).
// Memakai model yang SUDAH dilatih (models/pm25_model.json), tanpa melatih ulang.
// Dimuat SETELAH script utama di index.html, jadi `map` & `tileLayer` sudah ada.
(function () {
  const status = document.getElementById('status');
  if (!status || typeof map === 'undefined') return;

  const $ = (id) => document.getElementById(id);
  let pmLayer = null;

  // ---------- Panel PM2.5 ----------
  const pmBox = document.createElement('div');
  pmBox.style.cssText = 'margin-top:12px;padding:10px;border:1px solid #ccd;border-radius:8px;background:#fff';
  pmBox.innerHTML = `
    <div style="font-weight:700;margin-bottom:4px">Estimasi PM2.5</div>
    <div style="font-size:12px;color:#666;margin-bottom:8px">
        Periode mengikuti tanggal di atas.
    </div>
    <button id="pm-run" style="margin-top:0">Hitung PM2.5</button>
    <button id="pm-clear" style="margin-top:6px;background:#777">Hapus PM2.5</button>
    <div id="pm-status" style="font-size:12px;margin-top:8px"></div>
    <div id="pm-legend" style="display:none;margin-top:8px">
      <div id="pm-bar" style="height:14px;border-radius:3px"></div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span id="pm-min"></span><span>µg/m³</span><span id="pm-max"></span>
      </div>
    </div>
    <div id="pm-model" style="font-size:12px;margin-top:8px"></div>
    <div style="font-size:11px;color:#b3261e;margin-top:8px">
    </div>`;

  // ---------- Panel kontrol layer ----------
  const rowStyle = 'display:grid;grid-template-columns:1fr 110px;gap:8px;align-items:center;margin-top:6px';
  const cbStyle = 'width:auto;padding:0;margin:0 6px 0 0;vertical-align:middle';
  const rgStyle = 'width:100%;padding:0;border:none;margin:0';
  const layerBox = document.createElement('div');
  layerBox.style.cssText = 'margin-top:12px;padding:10px;border:1px solid #ccd;border-radius:8px;background:#fff';
  layerBox.innerHTML = `
    <div style="font-weight:700">Map Layer</div>
    <div style="${rowStyle}">
      <label style="margin:0;font-weight:400"><input type="checkbox" id="ly-param" checked style="${cbStyle}">Layer parameter</label>
      <input type="range" id="ly-param-op" min="0.1" max="1" step="0.1" value="0.8" style="${rgStyle}">
    </div>
    <div style="${rowStyle}">
      <label style="margin:0;font-weight:400"><input type="checkbox" id="ly-pm" disabled style="${cbStyle}">Layer PM2.5</label>
      <input type="range" id="ly-pm-op" min="0.1" max="1" step="0.1" value="0.8" style="${rgStyle}">
    </div>`;
  // Urutan di sidebar: tombol Tampilkan > legenda parameter > Map Layer > PM2.5
  const anchor = document.getElementById('legend-labels') || status;
  anchor.insertAdjacentElement('afterend', pmBox);
  anchor.insertAdjacentElement('afterend', layerBox);

  const hasParam = () => typeof tileLayer !== 'undefined' && tileLayer;

  // Centang layer parameter
  $('ly-param').addEventListener('change', (e) => {
    if (!hasParam()) return;
    if (e.target.checked) map.addLayer(tileLayer); else map.removeLayer(tileLayer);
  });
  // Centang layer PM2.5
  $('ly-pm').addEventListener('change', (e) => {
    if (!pmLayer) return;
    if (e.target.checked) { map.addLayer(pmLayer); pmLayer.bringToFront(); }
    else map.removeLayer(pmLayer);
  });
  // Slider transparansi
  $('ly-param-op').addEventListener('input', (e) => {
    if (hasParam()) tileLayer.setOpacity(parseFloat(e.target.value));
  });
  $('ly-pm-op').addEventListener('input', (e) => {
    if (pmLayer) pmLayer.setOpacity(parseFloat(e.target.value));
  });
  // Saat layer parameter dimuat ulang (tombol "Tampilkan" utama):
  // samakan transparansinya, centang kotaknya, dan jaga PM2.5 tetap di atas.
  map.on('layeradd', (e) => {
    const l = e.layer;
    const isEE = l && l._url && String(l._url).includes('earthengine');
    if (!isEE || l === pmLayer) return;
    l.setOpacity(parseFloat($('ly-param-op').value));
    $('ly-param').checked = true;
    if (pmLayer && map.hasLayer(pmLayer)) pmLayer.bringToFront();
  });

  // ---------- Tombol PM2.5 ----------
  $('pm-clear').addEventListener('click', () => {
    if (pmLayer) { map.removeLayer(pmLayer); pmLayer = null; }
    $('pm-legend').style.display = 'none';
    $('ly-pm').checked = false;
    $('ly-pm').disabled = true;
  });

  $('pm-run').addEventListener('click', async () => {
    const start = $('start').value, end = $('end').value;
    if (!start || !end) { $('pm-status').textContent = 'Isi tanggal mulai & akhir dulu.'; return; }

    $('pm-run').disabled = true;
    $('pm-status').textContent = 'Memuat peta PM2.5...';
    try {
      const res = await fetch(`/api/pm25?start=${start}&end=${end}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      if (pmLayer) map.removeLayer(pmLayer);
      const layer = L.tileLayer(data.tile_url, { opacity: parseFloat($('ly-pm-op').value) });
      pmLayer = layer;          // simpan dulu sebelum ditambahkan ke peta
      layer.addTo(map);
      $('ly-pm').disabled = false;
      $('ly-pm').checked = true;

      $('pm-bar').style.background =
        'linear-gradient(to right,' + data.palette.map((c) => '#' + c).join(',') + ')';
      $('pm-min').textContent = data.vmin;
      $('pm-max').textContent = data.vmax;
      $('pm-legend').style.display = 'block';

      const m = data.model;
      const rows = m.names.map((n, i) =>
        `<tr><td>${n}</td><td style="text-align:right">${Number(m.coefs[i]).toFixed(4)}</td></tr>`).join('');
      $('pm-model').innerHTML =
        `<b>Info model</b><br>` +
        `Dilatih: ${m.trained_at} (data sampai ${m.train_end})<br>` +
        `R² = ${Number(m.r2).toFixed(3)} • RMSE = ${Number(m.rmse).toFixed(2)} µg/m³ ` +
        `(data uji ${m.n_test} titik)<br>` +
        `<table style="width:100%;margin-top:6px;font-size:12px"><tr><th align="left">Variabel</th>` +
        `<th align="right">Koefisien</th></tr>${rows}</table>`;
      $('pm-status').textContent = '';
    } catch (e) {
      $('pm-status').textContent = 'Gagal: ' + e.message;
    } finally {
      $('pm-run').disabled = false;
    }
  });
})();
