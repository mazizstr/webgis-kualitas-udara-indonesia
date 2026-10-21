"""
Estimasi PM2.5 dengan regresi linear berganda (dihitung di Earth Engine).

CATATAN PENTING (versi latihan):
  Variabel "jawaban" (target) yang dipakai untuk melatih model adalah PM2.5
  dari model CAMS (ECMWF/CAMS/NRT), BUKAN hasil ukur alat di lapangan.
  Untuk project sungguhan, ganti target dengan data stasiun pemantau.

Cara pakai: lihat instruksi di pesan chat (2 baris tambahan di app.py).
"""
import json
import os
from datetime import date, datetime, timedelta

import ee
from flask import Blueprint, jsonify, request

bp = Blueprint("pm25", __name__)

# ---------- Konfigurasi ----------
# nama: (koleksi, band, faktor pengali agar angkanya tidak terlalu kecil)
S5P = {
    "NO2": ("COPERNICUS/S5P/OFFL/L3_NO2", "tropospheric_NO2_column_number_density", 1e5),
    "HCHO": ("COPERNICUS/S5P/OFFL/L3_HCHO", "tropospheric_HCHO_column_number_density", 1e4),
    "AER_AI": ("COPERNICUS/S5P/OFFL/L3_AER_AI", "absorbing_aerosol_index", 1.0),
    "CO": ("COPERNICUS/S5P/OFFL/L3_CO", "CO_column_number_density", 100.0),
    "SO2": ("COPERNICUS/S5P/OFFL/L3_SO2", "SO2_column_number_density", 1e4),
}
ERA5 = "ECMWF/ERA5_LAND/DAILY_AGGR"   # suhu & angin
CAMS = "ECMWF/CAMS/NRT"               # target latihan (PM2.5 model)
PM_BAND = "particulate_matter_d_less_than_25_um_surface"

N_WINDOWS = 8        # jumlah "potongan waktu" untuk data latih
WINDOW_DAYS = 30     # panjang tiap potongan (hari)
N_SAMPLES = 300      # titik sampel per potongan
TRAIN_FRAC = 0.7     # 70% data latih, 30% data uji

NAMES = list(S5P.keys()) + ["TEMP", "U", "V"]
PALETTE = ["1a9850", "91cf60", "d9ef8b", "fee08b", "fc8d59", "d73027", "7f0000"]

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "pm25_model.json")
_loaded = {"mtime": None, "model": None}


def _indonesia():
    return ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(
        ee.Filter.eq("country_na", "Indonesia")
    )


def _target_proj(start, end):
    return (
        ee.ImageCollection(CAMS)
        .filterDate(start, end)
        .first()
        .select(PM_BAND)
        .projection()
    )


def _target(start, end):
    """PM2.5 CAMS rata-rata (ug/m3). Satuan asli kg/m3, dikali 1e9."""
    c = (
        ee.ImageCollection(CAMS)
        .filter(ee.Filter.eq("model_initialization_hour", 0))
        .filterDate(start, end)
        .select(PM_BAND)
    )
    return c.mean().multiply(1e9).rename("PM25")


def _coarsen(img, src_proj, target_proj):
    """Rata-ratakan piksel halus ke grid kasar CAMS (~44 km)."""
    return (
        img.setDefaultProjection(src_proj)
        .reduceResolution(ee.Reducer.mean(), maxPixels=4096)
        .reproject(target_proj)
    )


def _predictors(start, end, target_proj=None):
    """Susun gambar berisi semua variabel prediktor (NO2, HCHO, dst)."""
    bands = []
    for name, (col, band, factor) in S5P.items():
        c = ee.ImageCollection(col).select(band).filterDate(start, end)
        img = c.mean().multiply(factor).rename(name)
        if target_proj is not None:
            img = _coarsen(img, c.first().projection(), target_proj)
        bands.append(img)

    era = ee.ImageCollection(ERA5).filterDate(start, end)
    era_proj = era.first().select("temperature_2m").projection()
    era_bands = [
        era.select("temperature_2m").mean().subtract(273.15).divide(10).rename("TEMP"),
        era.select("u_component_of_wind_10m").mean().rename("U"),
        era.select("v_component_of_wind_10m").mean().rename("V"),
    ]
    for img in era_bands:
        if target_proj is not None:
            img = _coarsen(img, era_proj, target_proj)
        bands.append(img)

    return ee.Image.cat(bands)


def _training_table(end_date):
    geom = _indonesia().geometry()
    parts = []
    for i in range(N_WINDOWS):
        e = end_date - timedelta(days=WINDOW_DAYS * i)
        s = e - timedelta(days=WINDOW_DAYS)
        s_str, e_str = s.isoformat(), e.isoformat()
        proj = _target_proj(s_str, e_str)
        stack = (
            _predictors(s_str, e_str, proj)
            .addBands(_target(s_str, e_str))
            .addBands(ee.Image.constant(1).rename("constant"))
        )
        parts.append(
            stack.sample(
                region=geom,
                projection=proj,
                numPixels=N_SAMPLES,
                seed=i + 1,
                tileScale=4,
            )
        )
    return ee.FeatureCollection(ee.List(parts)).flatten().randomColumn("r", 42)


def _fit_model(end_date):
    fc = _training_table(end_date)
    train = fc.filter(ee.Filter.lt("r", TRAIN_FRAC))
    test = fc.filter(ee.Filter.gte("r", TRAIN_FRAC))

    cols = ["constant"] + NAMES + ["PM25"]
    fit = train.reduceColumns(
        ee.Reducer.linearRegression(len(NAMES) + 1, 1), cols
    ).getInfo()
    coefs = [row[0] for row in fit["coefficients"]]

    def add_err(f):
        p = ee.Number(coefs[0])
        for n, c in zip(NAMES, coefs[1:]):
            p = p.add(ee.Number(f.get(n)).multiply(c))
        err = p.subtract(ee.Number(f.get("PM25")))
        return f.set("err2", err.pow(2))

    test = test.map(add_err)
    stats = ee.Dictionary(
        {
            "n_train": train.size(),
            "n_test": test.size(),
            "sse": test.aggregate_sum("err2"),
            "sd": test.aggregate_total_sd("PM25"),
            "mean_obs": test.aggregate_mean("PM25"),
        }
    ).getInfo()

    n_test = stats["n_test"]
    if n_test < 10:
        raise ValueError(
            "Data uji terlalu sedikit. Coba majukan tanggal akhir ke periode "
            "yang datanya sudah tersedia."
        )
    rmse = (stats["sse"] / n_test) ** 0.5
    r2 = 1 - stats["sse"] / (stats["sd"] ** 2 * n_test)

    return {
        "names": ["Konstanta"] + NAMES,
        "coefs": coefs,
        "n_train": stats["n_train"],
        "n_test": n_test,
        "rmse": rmse,
        "r2": r2,
        "mean_obs": stats["mean_obs"],
        "train_end": end_date.isoformat(),
        "n_windows": N_WINDOWS,
        "window_days": WINDOW_DAYS,
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "target": "PM2.5 model CAMS (versi latihan)",
    }


def train_and_save(end_date):
    """Latih model sekali, lalu simpan koefisiennya ke file JSON."""
    model = _fit_model(end_date)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)
    return model


def load_model():
    """Baca model dari file. Otomatis membaca ulang jika file berubah."""
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _loaded["mtime"] != mtime:
        with open(MODEL_PATH, encoding="utf-8") as f:
            _loaded["model"] = json.load(f)
        _loaded["mtime"] = mtime
    return _loaded["model"]


def _predict_image(start, end, coefs):
    stack = _predictors(start, end)  # resolusi asli TROPOMI
    pred = ee.Image.constant(coefs[0])
    for n, c in zip(NAMES, coefs[1:]):
        pred = pred.add(stack.select(n).multiply(c))
    return pred.max(0).rename("PM25_est").clip(_indonesia())


@bp.route("/api/pm25")
def api_pm25():
    try:
        start = request.args["start"]
        end = request.args["end"]

        model = load_model()
        if model is None:
            raise ValueError(
                "Model belum dilatih. Jalankan dulu di terminal: python train_pm25.py"
            )

        image = _predict_image(start, end, model["coefs"])
        map_id = image.getMapId({"min": 0, "max": 60, "palette": PALETTE})

        return jsonify(
            {
                "tile_url": map_id["tile_fetcher"].url_format,
                "palette": PALETTE,
                "vmin": 0,
                "vmax": 60,
                "model": model,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
