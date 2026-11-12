"""Uji pembacaan data/ dan pencarian cepat di kelas Data."""

import pandas as pd

from src import muat_data
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
