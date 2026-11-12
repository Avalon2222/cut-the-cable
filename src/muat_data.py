"""
src/muat_data.py - membaca data dari folder data/
=================================================
Semua data sudah berbentuk CSV/JSON hasil scripts/bangun_data.py, sehingga aplikasi
berjalan tanpa internet. Fungsi di sini hanya membaca, memberi tipe yang benar, dan
menyediakan beberapa pencarian cepat (kabel per landing station dan sebaliknya).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"

LABEL_KATEGORI = {
    "internasional": "Internasional (mendarat di Indonesia + luar negeri)",
    "domestik": "Domestik (semua landing station di Indonesia)",
    "transit": "Kawasan (lewat perairan sekitar, tidak mendarat)",
}
LABEL_STATUS = {"aktif": "Aktif", "rencana": "Rencana / dalam pembangunan"}


@dataclass
class Data:
    kabel: pd.DataFrame          # satu baris per kabel
    landing: pd.DataFrame        # satu baris per landing station
    relasi: pd.DataFrame         # pasangan (id_kabel, id_landing)
    geo: dict                    # GeoJSON FeatureCollection garis kabel
    meta: dict                   # tanggal pembuatan dan jumlah baris

    # --- pencarian cepat -----------------------------------------------------------------
    def landing_dari_kabel(self, id_kabel: str) -> list[str]:
        r = self.relasi[self.relasi["id_kabel"] == id_kabel].sort_values("urutan")
        return r["id_landing"].tolist()

    def kabel_dari_landing(self, id_landing: str) -> list[str]:
        return self.relasi.loc[self.relasi["id_landing"] == id_landing, "id_kabel"].tolist()

    @cached_property
    def _nama_kabel(self) -> dict[str, str]:
        return self.kabel.set_index("id")["nama"].to_dict()

    @cached_property
    def _nama_landing(self) -> dict[str, str]:
        return self.landing.set_index("id")["nama"].to_dict()

    def nama_kabel(self, id_kabel: str) -> str:
        """Nama kabel, atau id-nya sendiri bila tidak ditemukan. Tabel id -> nama dibuat sekali saja."""
        return self._nama_kabel.get(id_kabel, id_kabel)

    def nama_landing(self, id_landing: str) -> str:
        return self._nama_landing.get(id_landing, id_landing)


def muat_semua(folder: Path = DATA) -> Data:
    kabel = pd.read_csv(folder / "kabel.csv")
    landing = pd.read_csv(folder / "landing_station.csv")
    relasi = pd.read_csv(folder / "kabel_landing.csv")
    with open(folder / "kabel_geo.json", encoding="utf-8") as fh:
        geo = json.load(fh)
    with open(folder / "META.json", encoding="utf-8") as fh:
        meta = json.load(fh)

    kabel["tahun_rfs"] = pd.to_numeric(kabel["tahun_rfs"], errors="coerce").astype("Int64")
    kabel["panjang_km"] = pd.to_numeric(kabel["panjang_km"], errors="coerce")
    kabel["negara"] = kabel["negara"].fillna("")
    kabel["pemilik"] = kabel["pemilik"].fillna("")
    kabel["pemasok"] = kabel["pemasok"].fillna("")
    landing["wilayah"] = landing["wilayah"].fillna("")
    return Data(kabel=kabel, landing=landing, relasi=relasi, geo=geo, meta=meta)


def muat_data_center(folder: Path = DATA) -> pd.DataFrame:
    """Lokasi data center besar di Indonesia (dari proyek dc-impact-dashboard), untuk lapisan peta opsional."""
    df = pd.read_csv(folder / "data_center.csv")
    kolom = ["nama", "operator", "kabupaten_kota", "provinsi", "lat", "lon", "kapasitas_it_mw", "status"]
    return df[kolom].dropna(subset=["lat", "lon"])
