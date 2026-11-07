"""Uji graf jaringan dan simulasi kabel putus dengan data mainan yang kecil dan mudah dibayangkan."""

import json

import pandas as pd
import pytest

from src import jaringan
from src.muat_data import Data


def buat_data_mainan() -> Data:
    """
    Jaringan mainan:
      SG (Singapura) --[int-1]-- BTM (Batam) --[dom-1]-- JKT (Jakarta) --[dom-2]-- SBY (Surabaya)
      SG (Singapura) --[int-2]-- JKT (Jakarta)
      JKT --[dom-3]-- ANC (Ancol, 5 km dari Jakarta)   <- sengaja berdekatan untuk uji sisi darat
      MND (Manado) --[int-3, rencana]-- GUM (Guam)
      PDG (Padang) --[dom-4]-- MTW (Mentawai)           <- pulau kecil yang tidak tersambung ke mana pun
    """
    landing = pd.DataFrame(
        [
            ("sg", "Singapore, Singapore", "Singapore", "Singapore", 1.30, 103.80, ""),
            ("gum", "Alupang, Guam", "Alupang", "Guam", 13.5, 144.8, ""),
            ("btm", "Batam, Indonesia", "Batam", "Indonesia", 1.10, 104.0, "Sumatra & Kepulauan Riau"),
            ("jkt", "Jakarta, Indonesia", "Jakarta", "Indonesia", -6.20, 106.80, "Jawa"),
            ("anc", "Ancol, Indonesia", "Ancol", "Indonesia", -6.12, 106.83, "Jawa"),
            ("sby", "Surabaya, Indonesia", "Surabaya", "Indonesia", -7.25, 112.75, "Jawa"),
            ("mnd", "Manado, Indonesia", "Manado", "Indonesia", 1.50, 124.85, "Sulawesi"),
            ("pdg", "Padang, Indonesia", "Padang", "Indonesia", -0.95, 100.35, "Sumatra & Kepulauan Riau"),
            ("mtw", "Tua Pejat, Indonesia", "Tua Pejat", "Indonesia", -2.05, 99.60, "Sumatra & Kepulauan Riau"),
        ],
        columns=["id", "nama", "kota", "negara", "lat", "lon", "wilayah"],
    )
    kabel = pd.DataFrame(
        [
            ("int-1", "Batam-Singapore", "internasional", "aktif", 2010, "Indonesia|Singapore"),
            ("int-2", "Jakarta-Singapore", "internasional", "aktif", 2015, "Indonesia|Singapore"),
            ("int-3", "Manado-Guam", "internasional", "rencana", 2028, "Guam|Indonesia"),
            ("dom-1", "Batam-Jakarta", "domestik", "aktif", 2012, "Indonesia"),
            ("dom-2", "Jakarta-Surabaya", "domestik", "aktif", 2013, "Indonesia"),
            ("dom-3", "Jakarta-Ancol", "domestik", "aktif", 2014, "Indonesia"),
            ("dom-4", "Padang-Mentawai", "domestik", "aktif", 2016, "Indonesia"),
            ("tr-1", "Transit", "transit", "aktif", 2000, "Malaysia|Thailand"),
        ],
        columns=["id", "nama", "kategori", "status", "tahun_rfs", "negara"],
    )
    relasi = pd.DataFrame(
        [
            ("int-1", "btm", 0), ("int-1", "sg", 1),
            ("int-2", "jkt", 0), ("int-2", "sg", 1),
            ("int-3", "mnd", 0), ("int-3", "gum", 1),
            ("dom-1", "btm", 0), ("dom-1", "jkt", 1),
            ("dom-2", "jkt", 0), ("dom-2", "sby", 1),
            ("dom-3", "jkt", 0), ("dom-3", "anc", 1),
            ("dom-4", "pdg", 0), ("dom-4", "mtw", 1),
        ],
        columns=["id_kabel", "id_landing", "urutan"],
    )
    return Data(kabel=kabel, landing=landing, relasi=relasi, geo={"type": "FeatureCollection", "features": []}, meta={})


@pytest.fixture
def data():
    return buat_data_mainan()


def test_graf_mengabaikan_transit_dan_rencana(data):
    G = jaringan.bangun_graf(data, radius_darat_km=0)
    assert G.has_edge("btm", "sg") and G.has_edge("jkt", "sby")
    assert not G.has_edge("mnd", "gum"), "kabel rencana tidak boleh masuk kecuali diminta"
    G2 = jaringan.bangun_graf(data, sertakan_rencana=True, radius_darat_km=0)
    assert G2.has_edge("mnd", "gum")


def test_sisi_darat_hanya_untuk_tetangga_dekat_senegara(data):
    pasangan = set(map(frozenset, jaringan.pasangan_darat(data.landing, 60)))
    assert frozenset({"jkt", "anc"}) in pasangan          # 9 km
    assert frozenset({"jkt", "sby"}) not in pasangan      # 660 km
    assert frozenset({"btm", "sg"}) not in pasangan       # 30 km tetapi beda negara
    assert jaringan.pasangan_darat(data.landing, 0) == []


def test_tanpa_pemutusan_semua_aman(data):
    hasil = jaringan.simulasi(data, set(), radius_darat_km=0)
    assert set(hasil["nama"].str.contains("Indonesia"))
    assert (hasil["status"] == "Aman").all()
    # Padang & Mentawai punya kabel tetapi tidak pernah tersambung ke luar negeri
    assert not hasil.set_index("id").loc["pdg", "internasional_awal"]
    assert hasil.set_index("id").loc["jkt", "pintu_awal"] == 2


def test_putus_kabel_batam_singapura(data):
    hasil = jaringan.simulasi(data, {"int-1"}, radius_darat_km=0).set_index("id")
    # Batam masih punya dom-1 ke Jakarta, dan Jakarta punya int-2 -> masih tersambung ke dunia, tapi tinggal 1 kabel
    assert hasil.loc["btm", "status"] == "Rentan (1 kabel tersisa)"
    assert hasil.loc["btm", "internasional_sisa"]
    assert hasil.loc["btm", "pintu_sisa"] == 1
    assert hasil.loc["jkt", "status"] == "Aman"


def test_putus_semua_kabel_ke_singapura(data):
    hasil = jaringan.simulasi(data, {"int-1", "int-2"}, radius_darat_km=0).set_index("id")
    assert hasil.loc["btm", "status"] == "Terputus dari dunia"
    assert hasil.loc["jkt", "status"] == "Terputus dari dunia"
    assert hasil.loc["sby", "status"] == "Terputus dari dunia"   # tidak kehilangan kabel, tetapi komponennya terisolasi
    assert hasil.loc["sby", "n_kabel_sisa"] == 1
    assert hasil.loc["pdg", "status"] == "Aman"                  # memang tidak pernah tersambung


def test_gelap_total(data):
    hasil = jaringan.simulasi(data, {"dom-2"}, radius_darat_km=0).set_index("id")
    assert hasil.loc["sby", "status"] == "Gelap total"
    assert hasil.loc["sby", "kabel_hilang"] == "Jakarta-Surabaya"
    assert hasil.loc["jkt", "status"] == "Kehilangan jalur"      # dari 3 kabel tinggal 2, masih internasional


def test_sisi_darat_menyelamatkan_ancol(data):
    # Tanpa sisi darat, Ancol gelap total bila dom-3 putus; dengan sisi darat 60 km ia tetap "online" lewat Jakarta.
    tanpa = jaringan.simulasi(data, {"dom-3"}, radius_darat_km=0).set_index("id")
    dengan = jaringan.simulasi(data, {"dom-3"}, radius_darat_km=60).set_index("id")
    assert tanpa.loc["anc", "status"] == "Gelap total"
    assert dengan.loc["anc", "status"] == "Hidup lewat darat"    # kabelnya habis, tetapi Jakarta 9 km jauhnya
    assert dengan.loc["anc", "internasional_sisa"]
    assert dengan.loc["anc", "pintu_sisa"] == 2


def test_ringkasan_wilayah_dan_angka(data):
    hasil = jaringan.simulasi(data, {"int-1", "int-2"}, radius_darat_km=0)
    tabel = jaringan.ringkas_wilayah(hasil)
    assert tabel.loc["Jawa", "Terputus dari dunia"] == 3
    assert tabel.loc["Jawa", "% terdampak"] == 100
    angka = jaringan.ringkas_angka(hasil)
    assert angka["terputus"] == 4 and angka["pintu_awal"] == 2 and angka["pintu_sisa"] == 0


def test_gateway_luar_negeri(data):
    g = jaringan.gateway_luar_negeri(data).set_index("negara")
    assert g.loc["Singapore", "n_kabel"] == 2 and g.loc["Singapore", "persen"] == 100
    assert "Guam" not in g.index                                  # rencana tidak dihitung
    g2 = jaringan.gateway_luar_negeri(data, sertakan_rencana=True).set_index("negara")
    assert g2.loc["Guam", "n_kabel"] == 1


def test_tentukan_status_aturan_dasar():
    assert jaringan.tentukan_status(0, 0, False, False) == "Aman"
    assert jaringan.tentukan_status(2, 0, True, False) == "Gelap total"
    assert jaringan.tentukan_status(2, 0, True, True) == "Hidup lewat darat"
    assert jaringan.tentukan_status(1, 0, False, False) == "Gelap total"
    assert jaringan.tentukan_status(2, 1, True, False) == "Terputus dari dunia"
    assert jaringan.tentukan_status(2, 1, True, True) == "Rentan (1 kabel tersisa)"
    assert jaringan.tentukan_status(3, 2, True, True) == "Kehilangan jalur"
    assert jaringan.tentukan_status(3, 3, True, True) == "Aman"


def test_jarak_haversine_jakarta_singapura():
    assert jaringan.jarak_km(-6.2, 106.8, 1.3, 103.8) == pytest.approx(895, abs=15)
    assert jaringan.jarak_km(0, 0, 0, 0) == 0


def test_data_sungguhan_konsisten():
    """Data asli di data/: setiap relasi menunjuk kabel dan landing station yang ada, geometri lengkap."""
    from src import muat_data

    d = muat_data.muat_semua()
    assert set(d.relasi["id_kabel"]) <= set(d.kabel["id"])
    assert set(d.relasi["id_landing"]) <= set(d.landing["id"])
    assert set(d.kabel["kategori"]) == {"domestik", "internasional", "transit"}
    id_geo = {f["properties"]["id"] for f in d.geo["features"]}
    assert set(d.kabel["id"]) <= id_geo
    idn = d.landing[d.landing["negara"] == "Indonesia"]
    assert idn["wilayah"].ne("").all()
    hasil = jaringan.simulasi(d, set())
    assert (hasil["status"] == "Aman").all()
    assert json.dumps(d.meta)  # META.json terbaca


def test_kabel_per_tahun_data_asli():
    from src.muat_data import muat_semua
    d = muat_semua()
    t = jaringan.kabel_per_tahun(d)
    k = d.kabel[d.kabel["kategori"].isin(["domestik", "internasional"])]
    assert t["jumlah"].sum() == k["tahun_rfs"].notna().sum()   # kabel transit tidak ikut
    assert t["tahun_rfs"].is_monotonic_increasing
    assert t["tahun_rfs"].dtype.kind == "i"
    assert set(t["kategori"]) <= {"domestik", "internasional"}
