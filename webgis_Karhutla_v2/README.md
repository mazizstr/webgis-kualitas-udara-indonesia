# WebGIS Pemantauan Asap Karhutla

Menampilkan **CO** (Sentinel-5P TROPOMI, OFFL) dan **PM2.5** (model CAMS, ECMWF/CAMS/NRT)
pada area persegi panjang yang mencakup Indonesia dan negara tetangga yang terdampak asap
(Malaysia, Singapura, Brunei, Thailand selatan, Filipina selatan), dengan overlay batas wilayah.

## Struktur
```
webgis-asap/
├── app.py
├── templates/index.html
├── public/            (logo.png, share.js)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Menjalankan di laptop
1. `python -m venv .venv` lalu `.venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `earthengine authenticate` (sekali saja)
4. Salin `.env.example` menjadi `.env`, isi `EE_PROJECT`
5. `python app.py`, buka http://127.0.0.1:5000

## Mengubah area studi
Edit `BBOX` di `app.py`: `[barat, selatan, timur, utara]` (derajat).

## Catatan data
- PM2.5 adalah keluaran model (resolusi ±44 km), bukan pengukuran stasiun.
- CO adalah kolom vertikal atmosfer (mol/m²), bukan konsentrasi permukaan.
- Batas provinsi memakai FAO GAUL (lisensi nonkomersial); untuk produk final ganti dengan batas resmi.
