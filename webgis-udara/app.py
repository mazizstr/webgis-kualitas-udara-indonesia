import os

import ee
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

EE_PROJECT = os.getenv("EE_PROJECT")
if not EE_PROJECT:
    raise SystemExit("Isi EE_PROJECT di file .env (lihat .env.example).")

ee.Initialize(project=EE_PROJECT)

app = Flask(__name__)
from pm25 import bp as pm25_bp
app.register_blueprint(pm25_bp)

# ---------- Konfigurasi parameter ----------
PALETTE = ["000000", "0000ff", "800080", "00ffff", "008000", "ffff00", "ff0000"]

PARAMS = {
    "NO2": {
        "label": "NO₂ (nitrogen dioksida)",
        "col": "COPERNICUS/S5P/OFFL/L3_NO2",
        "band": "tropospheric_NO2_column_number_density",
        "min": 0, "max": 0.0005, "unit": "mol/m²",
    },
    "CO": {
        "label": "CO (karbon monoksida)",
        "col": "COPERNICUS/S5P/OFFL/L3_CO",
        "band": "CO_column_number_density",
        "min": 0.02, "max": 0.05, "unit": "mol/m²",
    },
    "SO2": {
        "label": "SO₂ (sulfur dioksida)",
        "col": "COPERNICUS/S5P/OFFL/L3_SO2",
        "band": "SO2_column_number_density",
        "min": 0, "max": 0.0005, "unit": "mol/m²",
    },
    "O3": {
        "label": "O₃ (ozon)",
        "col": "COPERNICUS/S5P/OFFL/L3_O3",
        "band": "O3_column_number_density",
        "min": 0.11, "max": 0.13, "unit": "mol/m²",
    },
    "HCHO": {
        "label": "HCHO (formaldehida)",
        "col": "COPERNICUS/S5P/OFFL/L3_HCHO",
        "band": "tropospheric_HCHO_column_number_density",
        "min": 0, "max": 0.0003, "unit": "mol/m²",
    },
    "AER_AI": {
        "label": "Aerosol Index (UV)",
        "col": "COPERNICUS/S5P/OFFL/L3_AER_AI",
        "band": "absorbing_aerosol_index",
        "min": -1, "max": 2, "unit": "indeks",
    },
}

INDONESIA = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(
    ee.Filter.eq("country_na", "Indonesia")
)


def get_collection(param, start, end):
    cfg = PARAMS[param]
    return (
        ee.ImageCollection(cfg["col"])
        .select(cfg["band"])
        .filterDate(start, end)
        .filterBounds(INDONESIA)
    )


def parse_args():
    param = request.args.get("param", "NO2")
    start = request.args.get("start")
    end = request.args.get("end")
    if param not in PARAMS or not start or not end:
        raise ValueError("Parameter, start, dan end wajib diisi dengan benar.")
    return param, start, end


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/params")
def api_params():
    return jsonify({"params": PARAMS, "palette": PALETTE})


@app.route("/api/tiles")
def api_tiles():
    """Kembalikan URL tile XYZ untuk komposit rata-rata."""
    try:
        param, start, end = parse_args()
        cfg = PARAMS[param]
        image = get_collection(param, start, end).mean().clip(INDONESIA)
        map_id = image.getMapId(
            {"min": cfg["min"], "max": cfg["max"], "palette": PALETTE}
        )
        return jsonify({"tile_url": map_id["tile_fetcher"].url_format})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/point")
def api_point():
    """Nilai rata-rata + deret waktu pada satu titik."""
    try:
        param, start, end = parse_args()
        lon = float(request.args["lon"])
        lat = float(request.args["lat"])
        cfg = PARAMS[param]
        band = cfg["band"]
        point = ee.Geometry.Point([lon, lat])
        col = get_collection(param, start, end)

        mean_value = (
            col.mean().reduceRegion(ee.Reducer.mean(), point, 5000).get(band).getInfo()
        )

        def to_feature(img):
            v = img.reduceRegion(ee.Reducer.mean(), point, 5000).get(band)
            return ee.Feature(
                None, {"date": img.date().format("YYYY-MM-dd"), "value": v}
            )

        fc = (
            col.limit(366)
            .map(to_feature)
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
