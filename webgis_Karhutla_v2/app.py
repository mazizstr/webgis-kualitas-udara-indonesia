import os
from datetime import date

import ee
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

EE_PROJECT = os.getenv("EE_PROJECT")
if not EE_PROJECT:
    raise SystemExit("Isi EE_PROJECT di file .env (lihat .env.example).")

SA_JSON = os.getenv("EE_SERVICE_ACCOUNT_JSON")
if SA_JSON:
    # Di server online: login pakai service account
    import json
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_JSON),
        scopes=[
            "https://www.googleapis.com/auth/earthengine",
            "https://www.googleapis.com/auth/cloud-platform",
        ],
    )
    ee.Initialize(creds, project=EE_PROJECT)
else:
    # Di laptop: login seperti biasa
    ee.Initialize(project=EE_PROJECT)

app = Flask(__name__, static_folder="public", static_url_path="")

# ---------------------------------------------------------------
# AREA STUDI (persegi panjang) -- ubah angka di sini kalau perlu.
# Urutan: [barat, selatan, timur, utara] dalam derajat.
# Default mencakup Sumatra, Kalimantan, Jawa, Semenanjung Malaysia,
# Singapura, Brunei, Thailand selatan, dan Filipina selatan.
# ---------------------------------------------------------------
BBOX = [92.0, -14.0, 142.0, 24.0]
AOI = ee.Geometry.Rectangle(BBOX, geodesic=False)

CO_PALETTE = ["000000", "0000ff", "800080", "00ffff", "008000", "ffff00", "ff0000"]
PM_PALETTE = ["00e400", "ffff00", "ff7e00", "ff0000", "8f3f97", "7e0023"]

# ---------- Konfigurasi parameter (hanya CO dan PM2.5) ----------
PARAMS = {
    "CO": {
        "label": "CO",
        "col": "COPERNICUS/S5P/OFFL/L3_CO",
        "band": "CO_column_number_density",
        "factor": 1.0,
        "min": 0.0, "max": 0.10, "unit": "mol/m²",
        "palette": CO_PALETTE,
        "scale": 5000,
        "note": "Catatan: Kolom CO yang digunakan bersumber dari Sentinel-5P TROPOMI. "
                "Data ini merupaka kolom vertikal atmosfer dengan resolusi ±5,5.",
    },
    "PM25": {
        "label": "PM2.5",
        "col": "ECMWF/CAMS/NRT",
        "band": "particulate_matter_d_less_than_25_um_surface",
        "factor": 1e9,  # kg/m3 -> ug/m3
        "min": 0, "max": 150, "unit": "µg/m³",
        "palette": PM_PALETTE,
        "scale": 44528,
        "note": "Catatan: PM2.5 yang digunakan merupakan keluaran model CAMS dari ECMWF. "
                "Memakai run 00 UTC, langkah prakiraan 0-21 jam dengan Resolusi ±44 km.",
    },
}


def get_collection(param, start, end):
    cfg = PARAMS[param]
    col = (
        ee.ImageCollection(cfg["col"])
        .filterDate(start, end)
        .select(cfg["band"])
    )
    if param == "PM25":
        col = col.filter(ee.Filter.eq("model_initialization_hour", 0)).filter(
            ee.Filter.lt("model_forecast_hour", 24)
        )
    else:
        col = col.filterBounds(AOI)
    return col


def parse_args():
    param = request.args.get("param", "CO")
    start = request.args.get("start")
    end = request.args.get("end")
    if param not in PARAMS or not start or not end:
        raise ValueError("Parameter, start, dan end wajib diisi dengan benar.")
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if d1 <= d0:
        raise ValueError("Tanggal akhir harus setelah tanggal mulai.")
    return param, start, end


def boundary_image(kind):
    """Garis batas wilayah (tanpa isi) sebagai gambar siap tampil."""
    if kind == "country":
        fc = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filterBounds(AOI)
        return fc.style(color="1a1a1a", fillColor="00000000", width=1.6)
    if kind == "province":
        fc = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level1").filterBounds(AOI)
        return fc.style(color="4d4d4d", fillColor="00000000", width=0.8)
    raise ValueError("Jenis batas tidak dikenal.")


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/params")
def api_params():
    return jsonify({"params": PARAMS, "bbox": BBOX})


@app.route("/api/tiles")
def api_tiles():
    """URL tile XYZ untuk komposit rata-rata, dipotong persegi panjang AOI."""
    try:
        param, start, end = parse_args()
        cfg = PARAMS[param]
        col = get_collection(param, start, end)
        n = col.size().getInfo()
        if n == 0:
            raise ValueError(
                "Tidak ada data pada rentang tanggal ini. Coba lebarkan rentang "
                "atau majukan tanggal ke periode yang datanya sudah tersedia."
            )
        image = col.mean().multiply(cfg["factor"]).clip(AOI)
        map_id = image.getMapId(
            {"min": cfg["min"], "max": cfg["max"], "palette": cfg["palette"]}
        )
        return jsonify({"tile_url": map_id["tile_fetcher"].url_format, "n_images": n})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/boundaries")
def api_boundaries():
    """URL tile untuk garis batas negara / provinsi."""
    try:
        kind = request.args.get("kind", "country")
        map_id = boundary_image(kind).getMapId()
        return jsonify({"tile_url": map_id["tile_fetcher"].url_format})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/point")
def api_point():
    """Nilai rata-rata + deret waktu harian pada satu titik."""
    try:
        param, start, end = parse_args()
        lon = float(request.args["lon"])
        lat = float(request.args["lat"])
        cfg = PARAMS[param]
        band, factor, scale = cfg["band"], cfg["factor"], cfg["scale"]
        point = ee.Geometry.Point([lon, lat])
        col = get_collection(param, start, end)

        mean_value = (
            col.mean()
            .multiply(factor)
            .reduceRegion(ee.Reducer.mean(), point, scale)
            .get(band)
            .getInfo()
        )

        n_days = min((date.fromisoformat(end) - date.fromisoformat(start)).days, 120)
        start_d = ee.Date(start)

        def daily(i):
            d0 = start_d.advance(ee.Number(i), "day")
            d1 = d0.advance(1, "day")
            c = col.filterDate(d0, d1)
            v = ee.Algorithms.If(
                c.size().gt(0),
                c.mean().multiply(factor).reduceRegion(ee.Reducer.mean(), point, scale).get(band),
                None,
            )
            return ee.Feature(None, {"date": d0.format("YYYY-MM-dd"), "value": v})

        fc = (
            ee.FeatureCollection(ee.List.sequence(0, n_days - 1).map(daily))
            .filter(ee.Filter.notNull(["value"]))
            .getInfo()
        )
        series = [
            {"date": f["properties"]["date"], "value": f["properties"]["value"]}
            for f in fc["features"]
        ]
        return jsonify({"mean": mean_value, "series": series})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
