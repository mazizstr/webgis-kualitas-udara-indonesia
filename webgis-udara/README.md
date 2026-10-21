# WebGIS Kualitas Udara Indonesia (Sentinel-5P TROPOMI)

Flask + Google Earth Engine (backend) dan Leaflet + Chart.js (frontend).

## Struktur
```
webgis-udara/
├── app.py
├── templates/index.html
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup di VS Code
1. Buka folder `webgis-udara` di VS Code (File > Open Folder).
2. Buka terminal (Ctrl+`), buat virtual environment:
   - Windows: `python -m venv .venv` lalu `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` lalu `source .venv/bin/activate`
3. Pilih interpreter: Ctrl+Shift+P > "Python: Select Interpreter" > pilih `.venv`.
4. `pip install -r requirements.txt`
5. Autentikasi Earth Engine (sekali saja): `earthengine authenticate`
6. Salin `.env.example` menjadi `.env`, isi `EE_PROJECT` dengan ID project GCP kamu
   (project harus sudah terdaftar di https://code.earthengine.google.com/register).
7. Jalankan: `python app.py`, lalu buka http://127.0.0.1:5000
