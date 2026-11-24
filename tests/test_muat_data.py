"""Uji pembacaan data/ dan pencarian cepat di kelas Data."""

import shutil

import pandas as pd

from src import jaringan, muat_data
from tests.test_jaringan import buat_data_mainan


def test_landing_dari_kabel_ikut_urutan():
    d = buat_data_mainan()
    d.relasi = pd.DataFrame({"id_kabel": ["k", "k", "k"], "id_landing": ["c", "a", "b"], "urutan": [2, 0, 1]})
    assert d.landing_dari_kabel("k") == ["a", "b", "c"]
    assert d.landing_dari_kabel("tidak-ada") == []


def test_kabel_dari_landing():
    d = buat_data_mainan()
    hasil = d.kabel_dari_landing("jkt")
    assert set(hasil) >= {"int-2", "dom-1"}
    assert d.kabel_dari_landing("tidak-ada") == []


def test_nama_kabel_dan_landing_jatuh_ke_id():
    d = buat_data_mainan()
    id_kabel = d.kabel["id"].iloc[0]
    id_landing = d.landing["id"].iloc[0]
    assert d.nama_kabel(id_kabel) == d.kabel["nama"].iloc[0]
    assert d.nama_landing(id_landing) == d.landing["nama"].iloc[0]
    assert d.nama_kabel("kabel-hantu") == "kabel-hantu"
    assert d.nama_landing("landing-hantu") == "landing-hantu"


def test_data_repo_konsisten():
    d = muat_data.muat_semua()
    assert d.kabel["id"].is_unique and d.landing["id"].is_unique
    assert set(d.relasi["id_kabel"]) <= set(d.kabel["id"])
    assert set(d.relasi["id_landing"]) <= set(d.landing["id"])
    assert str(d.kabel["tahun_rfs"].dtype) == "Int64"
    contoh = d.relasi["id_kabel"].iloc[0]
    assert d.nama_kabel(contoh) != contoh


def test_muat_data_center():
    dc = muat_data.muat_data_center()
    assert not dc.empty
    assert dc[["lat", "lon"]].notna().all().all()


def test_landing_dari_kabel_tanpa_duplikat():
    d = buat_data_mainan()
    d.relasi = pd.DataFrame({"id_kabel": ["k", "k", "k", "k"], "id_landing": ["a", "b", "a", "c"], "urutan": [0, 1, 1, 2]})
    assert d.landing_dari_kabel("k") == ["a", "b", "c"]


def test_kabel_dari_landing_tanpa_duplikat():
    d = buat_data_mainan()
    d.relasi = pd.DataFrame({"id_kabel": ["k1", "k1", "k2"], "id_landing": ["a", "a", "a"], "urutan": [0, 2, 0]})
    assert d.kabel_dari_landing("a") == ["k1", "k2"]


def test_muat_semua_status_dan_kategori_dirapikan(tmp_path):
    for nama in ("kabel.csv", "landing_station.csv", "kabel_landing.csv", "kabel_geo.json", "META.json"):
        shutil.copy(muat_data.DATA / nama, tmp_path / nama)
    kabel = pd.read_csv(tmp_path / "kabel.csv")
    asli = muat_data.muat_semua()
    kabel["status"] = kabel["status"].str.upper() + " "
    kabel["kategori"] = " " + kabel["kategori"].str.title()
    kabel.to_csv(tmp_path / "kabel.csv", index=False)
    d = muat_data.muat_semua(tmp_path)
    assert list(d.kabel["status"]) == list(asli.kabel["status"])
    assert list(d.kabel["kategori"]) == list(asli.kabel["kategori"])


def test_negara_landing_dirapikan(tmp_path):
    folder = tmp_path / "data"
    shutil.copytree(muat_data.DATA, folder)
    landing = pd.read_csv(folder / "landing_station.csv")
    landing["negara"] = landing["negara"].where(landing["negara"] != "Indonesia", " Indonesia ")
    landing.to_csv(folder / "landing_station.csv", index=False)
    d = muat_data.muat_semua(folder)
    assert (d.landing["negara"] == "Indonesia").sum() == (landing["negara"] == " Indonesia ").sum() > 0


def test_koordinat_landing_teks_rusak_jadi_nan(tmp_path):
    folder = tmp_path / "data"
    shutil.copytree(muat_data.DATA, folder)
    landing = pd.read_csv(folder / "landing_station.csv")
    landing["lat"] = landing["lat"].astype(object)
    landing.loc[0, "lat"] = "tidak ada"
    landing.to_csv(folder / "landing_station.csv", index=False)
    d = muat_data.muat_semua(folder)
    assert pd.api.types.is_float_dtype(d.landing["lat"])
    assert pd.isna(d.landing.loc[0, "lat"])
    jaringan.bangun_graf(d)


def test_nama_kosong_jatuh_ke_id():
    d = buat_data_mainan()
    d.kabel["nama"] = d.kabel["nama"].astype(object)
    d.kabel.loc[0, "nama"] = None
    d.landing.loc[0, "nama"] = "  "
    assert d.nama_kabel(d.kabel["id"].iloc[0]) == d.kabel["id"].iloc[0]
    assert d.nama_landing(d.landing["id"].iloc[0]) == d.landing["id"].iloc[0]
    assert d.nama_kabel(d.kabel["id"].iloc[1]) == d.kabel["nama"].iloc[1]


def test_data_center_koordinat_rusak_dibuang(tmp_path):
    dc = pd.read_csv(muat_data.DATA / "data_center.csv")
    dc["lat"] = dc["lat"].astype(object)
    dc.loc[0, "lat"] = "tidak ada"
    dc.loc[1, "lon"] = float("inf")
    dc.to_csv(tmp_path / "data_center.csv", index=False)
    hasil = muat_data.muat_data_center(tmp_path)
    assert len(hasil) == len(dc) - 2
    assert pd.api.types.is_float_dtype(hasil["lat"]) and pd.api.types.is_float_dtype(hasil["lon"])
