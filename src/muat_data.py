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

import numpy as np
import pandas as pd

from src.wilayah import tentukan_wilayah

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
        r = self.relasi[self.relasi["id_kabel"] == id_kabel].sort_values("urutan", kind="mergesort")
        # Landing yang tercatat dua kali untuk kabel yang sama cukup muncul sekali, di urutan pertamanya.
        return list(dict.fromkeys(r["id_landing"]))

    def kabel_dari_landing(self, id_landing: str) -> list[str]:
        ids = self.relasi.loc[self.relasi["id_landing"] == id_landing, "id_kabel"]
        # Kabel yang mencatat landing ini dua kali tetap dihitung satu kabel.
        return list(dict.fromkeys(ids))

    @staticmethod
    def _peta_nama(tabel: pd.DataFrame) -> dict[str, str]:
        # Nama kosong tidak dimasukkan, supaya pencarian jatuh ke id dan bukan mengembalikan NaN.
        nama = tabel.set_index("id")["nama"]
        nama = nama[nama.notna() & (nama.astype(str).str.strip() != "")]
        return nama.astype(str).to_dict()

    @cached_property
    def _nama_kabel(self) -> dict[str, str]:
        return self._peta_nama(self.kabel)

    @cached_property
    def _nama_landing(self) -> dict[str, str]:
        return self._peta_nama(self.landing)

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

    # Tahun pecahan ("2020.5") atau "inf" membuat astype("Int64") error dan seluruh aplikasi gagal
    # dimuat; tahun seperti itu dianggap tidak diketahui.
    tahun = pd.to_numeric(kabel["tahun_rfs"], errors="coerce")
    kabel["tahun_rfs"] = tahun.where(np.isfinite(tahun) & (tahun % 1 == 0)).astype("Int64")
    # Id dari suntingan manual ("sjc-2 ") harus persis sama di ketiga tabel; spasi sisa membuat
    # relasi tidak menemukan kabel atau landing-nya dan kabel itu hilang dari graf diam-diam.
    for tabel, kolom_id in ((kabel, ["id"]), (landing, ["id"]), (relasi, ["id_kabel", "id_landing"])):
        for kolom in kolom_id:
            tabel[kolom] = tabel[kolom].map(lambda v: v.strip() if isinstance(v, str) else v)
    # Id yang tercatat dua kali (baris tersalin saat menyunting CSV) membuat landing tampil dobel di
    # tabel simulasi dan persen gateway dihitung dari jumlah kabel yang kelebihan; pakai baris pertama.
    kabel = kabel.drop_duplicates("id", keep="first").reset_index(drop=True)
    landing = landing.drop_duplicates("id", keep="first").reset_index(drop=True)
    # Urutan pendaratan harus angka; satu sel teks membuat kolomnya teks dan "10" tersortir sebelum "2".
    relasi["urutan"] = pd.to_numeric(relasi["urutan"], errors="coerce")
    panjang = pd.to_numeric(kabel["panjang_km"], errors="coerce")
    # Panjang 0 adalah tanda "belum diisi" di sumbernya, dan panjang negatif atau tak hingga bukan
    # ukuran kabel; dulu ikut dijumlahkan dan tampil "0 km" seolah kabel benar-benar sependek itu.
    kabel["panjang_km"] = panjang.where(np.isfinite(panjang) & (panjang > 0))
    # Status dan kategori dibandingkan persis ("aktif", "internasional"); suntingan manual seperti
    # "Aktif " atau "INTERNASIONAL" jangan sampai membuat kabel keluar dari graf diam-diam.
    for kolom in ("status", "kategori"):
        kabel[kolom] = kabel[kolom].fillna("").astype(str).str.strip().str.lower()
    kabel["negara"] = kabel["negara"].fillna("")
    kabel["pemilik"] = kabel["pemilik"].fillna("")
    kabel["pemasok"] = kabel["pemasok"].fillna("")
    landing["wilayah"] = landing["wilayah"].fillna("")
    # Koordinat teks rusak (mis. "tidak ada") jadi NaN; kalau dibiarkan teks, kolomnya bukan angka
    # dan perhitungan jarak antar landing station gagal untuk seluruh graf.
    for kolom in ("lat", "lon"):
        landing[kolom] = pd.to_numeric(landing[kolom], errors="coerce")
        # "inf" terbaca sebagai angka tak hingga dan membuat haversine (math.sin) error saat graf dibangun.
        landing[kolom] = landing[kolom].where(landing[kolom].abs() != float("inf"))
    # Lintang di luar ±90 atau bujur di luar ±180 (misalnya lat/lon tertukar) bukan koordinat nyata;
    # haversine tetap menghitungnya dan jarak kabel jadi ngawur.
    landing["lat"] = landing["lat"].where(landing["lat"].abs() <= 90)
    landing["lon"] = landing["lon"].where(landing["lon"].abs() <= 180)
    # Graf membandingkan negara == "Indonesia" persis; "Indonesia " dari suntingan manual
    # membuat landing dalam negeri terhitung sebagai luar negeri.
    landing["negara"] = landing["negara"].where(landing["negara"].isna(), landing["negara"].astype(str).str.strip())
    # Landing Indonesia yang wilayahnya kosong (baris baru dari suntingan manual) tetap bisa ditentukan
    # dari koordinatnya; dulu ia terkumpul di baris "Tidak diketahui" pada ringkasan per wilayah.
    kosong = (landing["wilayah"].astype(str).str.strip() == "") & (landing["negara"] == "Indonesia")
    if kosong.any():
        landing.loc[kosong, "wilayah"] = [
            tentukan_wilayah(lat, lon) for lat, lon in zip(landing.loc[kosong, "lat"], landing.loc[kosong, "lon"])
        ]
    return Data(kabel=kabel, landing=landing, relasi=relasi, geo=geo, meta=meta)


def muat_data_center(folder: Path = DATA) -> pd.DataFrame:
    """Lokasi data center besar di Indonesia (dari proyek dc-impact-dashboard), untuk lapisan peta opsional."""
    df = pd.read_csv(folder / "data_center.csv")
    kolom = ["nama", "operator", "kabupaten_kota", "provinsi", "lat", "lon", "kapasitas_it_mw", "status"]
    df = df[kolom].copy()
    # Sama seperti landing station: koordinat teks rusak atau tak hingga jadi NaN lalu dibuang,
    # supaya satu sel salah tidak membuat lapisan peta data center gagal digambar.
    for k in ("lat", "lon", "kapasitas_it_mw"):
        df[k] = pd.to_numeric(df[k], errors="coerce")
    df[["lat", "lon"]] = df[["lat", "lon"]].where(df[["lat", "lon"]].abs() != float("inf"))
    return df.dropna(subset=["lat", "lon"])
