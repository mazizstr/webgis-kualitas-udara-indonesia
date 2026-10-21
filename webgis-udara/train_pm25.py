"""
Latih model PM2.5 SEKALI, lalu simpan koefisien ke models/pm25_model.json.

Cara pakai (di terminal VS Code, dengan (.venv) aktif):
    python train_pm25.py
    python train_pm25.py --end 2026-10-10     # pilih tanggal akhir data latih

Setelah file model ada, peta tinggal memakainya. Tidak perlu melatih lagi
setiap membuka browser. Latih ulang kira-kira sebulan sekali.
"""
import argparse
import os
from datetime import date, timedelta

import ee
from dotenv import load_dotenv

load_dotenv()
ee.Initialize(project=os.getenv("EE_PROJECT"))

import pm25  # setelah ee.Initialize

parser = argparse.ArgumentParser()
parser.add_argument(
    "--end",
    default=(date.today() - timedelta(days=10)).isoformat(),
    help="Tanggal akhir data latih (YYYY-MM-DD). Default: 10 hari lalu.",
)
args = parser.parse_args()

print(f"Melatih model dengan data sampai {args.end} ... (1-3 menit)")
model = pm25.train_and_save(date.fromisoformat(args.end))

print("\nSelesai. Model disimpan di:", pm25.MODEL_PATH)
print(f"R2 (data uji)   : {model['r2']:.3f}")
print(f"RMSE (data uji) : {model['rmse']:.2f} ug/m3")
print("Koefisien:")
for n, c in zip(model["names"], model["coefs"]):
    print(f"  {n:10s} {c:+.4f}")
