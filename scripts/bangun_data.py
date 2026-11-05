"""
scripts/bangun_data.py - membangun ulang data kabel dari Submarine Cable Map (TeleGeography)
===========================================================================================
Jalankan dari root repo:   python scripts/bangun_data.py

Yang dilakukan:
  1. Unduh daftar kabel, geometri kabel, dan geometri landing station dari API publik
     https://www.submarinecablemap.com/api/v3/ (format GeoJSON/JSON, tanpa kunci).
  2. Unduh detail setiap kabel (landing station, pemilik, panjang, tahun RFS, status).
  3. Saring yang relevan untuk Indonesia:
       - "mendarat": minimal satu landing station di Indonesia
       - "transit":  tidak mendarat tetapi lintasannya melewati kotak perairan Indonesia
  4. Simpan ke data/:
       kabel.csv            satu baris per kabel (mendarat + transit)
       landing_station.csv  satu baris per landing station yang tersentuh kabel di atas,
                            termasuk jumlah kabel (semua kabel dunia yang mendarat di sana)
       kabel_landing.csv    tabel relasi kabel <-> landing station (bentuk panjang)
       kabel_geo.json       GeoJSON garis kabel (hanya subset relevan, agar repo tetap kecil)
       META.json            tanggal pembuatan dan jumlah baris

Semua pemrosesan murni pandas + json; tidak ada library GIS yang dibutuhkan.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import wilayah  # noqa: E402  (setelah sys.path agar bisa dijalankan dari mana saja)

API = "https://www.submarinecablemap.com/api/v3"
DATA = ROOT / "data"
TIMEOUT = 30
SESI = requests.Session()
SESI.headers["User-Agent"] = "cut-the-cable (portofolio pribadi, data publik)"


def ambil_json(url: str):
    r = SESI.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def panjang_km(teks: str | None) -> float | None:
    """'19,888 km' -> 19888.0 ; None/'' -> None."""
    if not teks:
        return None
    angka = teks.lower().replace("km", "").replace(",", "").strip()
    try:
        return float(angka)
    except ValueError:
        return None


def nama_kota(nama_lengkap: str) -> str:
    """'Jakarta, Indonesia' -> 'Jakarta' ; 'Grover Beach, CA, United States' -> 'Grover Beach'."""
    return nama_lengkap.split(",")[0].strip()


def lewat_kotak(koordinat_multiline) -> bool:
    """True bila ada satu saja titik garis kabel yang jatuh di dalam kotak perairan Indonesia."""
    for garis in koordinat_multiline:
        for lon, lat in garis:
            if wilayah.di_kotak_indonesia(lat, lon):
                return True
    return False


def main() -> None:
    print("1/4 mengunduh daftar kabel dan geometri ...")
    daftar = ambil_json(f"{API}/cable/all.json")
    geo_kabel = ambil_json(f"{API}/cable/cable-geo.json")
    geo_landing = ambil_json(f"{API}/landing-point/landing-point-geo.json")
    geometri = {f["properties"]["id"]: f for f in geo_kabel["features"]}
    titik = {f["properties"]["id"]: f for f in geo_landing["features"]}
    print(f"    {len(daftar)} kabel, {len(titik)} landing station di seluruh dunia")

    print("2/4 mengunduh detail setiap kabel (±1 menit) ...")

    def detail(k):
        return ambil_json(f"{API}/cable/{k['id']}.json")

    with ThreadPoolExecutor(max_workers=12) as ex:
        kabel_detail = list(ex.map(detail, daftar))

    print("3/4 menyaring kabel yang relevan untuk Indonesia ...")
    baris_kabel, baris_relasi, fitur_geo = [], [], []
    id_landing_terpakai: set[str] = set()
    for k in kabel_detail:
        landing = k["landing_points"]
        negara = sorted({l["country"] for l in landing})
        n_idn = sum(1 for l in landing if l["country"] == "Indonesia")
        g = geometri.get(k["id"])
        mendarat = n_idn > 0
        transit = (not mendarat) and g is not None and lewat_kotak(g["geometry"]["coordinates"])
        if not (mendarat or transit):
            continue
        if mendarat and n_idn == len(landing):
            kategori = "domestik"
        elif mendarat:
            kategori = "internasional"
        else:
            kategori = "transit"
        baris_kabel.append(
            {
                "id": k["id"],
                "nama": k["name"],
                "kategori": kategori,
                "status": "rencana" if k["is_planned"] else "aktif",
                "tahun_rfs": k["rfs_year"],
                "rfs": k["rfs"],
                "panjang_km": panjang_km(k["length"]),
                "pemilik": k["owners"],
                "pemasok": k["suppliers"],
                "n_landing": len(landing),
                "n_landing_indonesia": n_idn,
                "negara": "|".join(negara),
                "warna": g["properties"].get("color") if g else None,
                "url": f"https://www.submarinecablemap.com/submarine-cable/{k['id']}",
            }
        )
        for urut, l in enumerate(landing):
            baris_relasi.append({"id_kabel": k["id"], "id_landing": l["id"], "urutan": urut})
            id_landing_terpakai.add(l["id"])
        if g is not None:
            fitur_geo.append(
                {
                    "type": "Feature",
                    "properties": {"id": k["id"], "nama": k["name"], "kategori": kategori,
                                   "status": "rencana" if k["is_planned"] else "aktif"},
                    "geometry": g["geometry"],
                }
            )

    nama_negara_landing = {}
    n_kabel: dict[str, int] = {}
    n_kabel_aktif: dict[str, int] = {}
    for k in kabel_detail:
        for l in k["landing_points"]:
            nama_negara_landing[l["id"]] = (l["name"], l["country"])
            n_kabel[l["id"]] = n_kabel.get(l["id"], 0) + 1
            if not k["is_planned"]:
                n_kabel_aktif[l["id"]] = n_kabel_aktif.get(l["id"], 0) + 1

    baris_landing = []
    for lid in sorted(id_landing_terpakai):
        f = titik.get(lid)
        nama, negara = nama_negara_landing[lid]
        lon, lat = (f["geometry"]["coordinates"] if f else (None, None))
        baris_landing.append(
            {
                "id": lid,
                "nama": nama,
                "kota": nama_kota(nama),
                "negara": negara,
                "lat": lat,
                "lon": lon,
                "wilayah": wilayah.tentukan_wilayah(lat, lon) if negara == "Indonesia" and lat is not None else "",
                "n_kabel_aktif": n_kabel_aktif.get(lid, 0),
                "n_kabel": n_kabel.get(lid, 0),
                "url": f"https://www.submarinecablemap.com/landing-point/{lid}",
            }
        )

    print("4/4 menyimpan ke data/ ...")
    DATA.mkdir(exist_ok=True)
    df_kabel = pd.DataFrame(baris_kabel).sort_values(["kategori", "nama"])
    df_landing = pd.DataFrame(baris_landing).sort_values(["negara", "nama"])
    df_relasi = pd.DataFrame(baris_relasi)
    df_kabel.to_csv(DATA / "kabel.csv", index=False)
    df_landing.to_csv(DATA / "landing_station.csv", index=False)
    df_relasi.to_csv(DATA / "kabel_landing.csv", index=False)
    with open(DATA / "kabel_geo.json", "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": fitur_geo}, fh, ensure_ascii=False, separators=(",", ":"))
    meta = {
        "dibangun": date.today().isoformat(),
        "sumber": API,
        "n_kabel_dunia": len(daftar),
        "n_kabel": int(len(df_kabel)),
        "n_kabel_per_kategori": df_kabel["kategori"].value_counts().to_dict(),
        "n_landing": int(len(df_landing)),
        "n_landing_indonesia": int((df_landing["negara"] == "Indonesia").sum()),
    }
    with open(DATA / "META.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
