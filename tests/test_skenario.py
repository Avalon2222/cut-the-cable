"""Uji pemilihan kabel per skenario dan uji geometri garis vs kotak."""

import pytest

from src import skenario
from src.skenario import Kotak
from tests.test_jaringan import buat_data_mainan


@pytest.fixture
def data():
    d = buat_data_mainan()
    # geometri sederhana: int-1 Batam->Singapura, dom-2 Jakarta->Surabaya (lurus), tr-1 jauh di utara
    d.geo = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": "int-1"}, "geometry": {"type": "MultiLineString",
             "coordinates": [[[104.0, 1.1], [103.9, 1.2], [103.8, 1.3]]]}},
            {"type": "Feature", "properties": {"id": "dom-2"}, "geometry": {"type": "MultiLineString",
             "coordinates": [[[106.8, -6.2], [112.75, -7.25]]]}},
            {"type": "Feature", "properties": {"id": "int-3"}, "geometry": {"type": "MultiLineString",
             "coordinates": [[[124.85, 1.5], [144.8, 13.5]]]}},
            {"type": "Feature", "properties": {"id": "tr-1"}, "geometry": {"type": "MultiLineString",
             "coordinates": [[[100.0, 6.0], [101.0, 6.5]]]}},
        ],
    }
    return d


def test_kabel_di_landing(data):
    assert skenario.kabel_di_landing(data, "jkt") == {"int-2", "dom-1", "dom-2", "dom-3"}
    assert skenario.kabel_di_landing(data, "mnd") == set()                       # hanya kabel rencana
    assert skenario.kabel_di_landing(data, "mnd", hanya_aktif=False) == {"int-3"}


def test_kabel_ke_negara(data):
    assert skenario.kabel_ke_negara(data, "Singapore") == {"int-1", "int-2"}
    assert skenario.kabel_ke_negara(data, "Guam") == set()
    assert skenario.kabel_ke_negara(data, "Guam", hanya_aktif=False) == {"int-3"}
    assert skenario.kabel_ke_negara(data, "Indonesia") == {"int-1", "int-2"}    # semua internasional mendarat di Indonesia


def test_segmen_memotong_kotak():
    k = Kotak("uji", 0, 10, 0, 10)
    assert skenario.segmen_memotong_kotak((-5, 5), (15, 5), k)      # menembus kiri-kanan
    assert skenario.segmen_memotong_kotak((2, 2), (3, 3), k)        # seluruhnya di dalam
    assert skenario.segmen_memotong_kotak((-5, -5), (5, 5), k)      # masuk lewat sudut
    assert not skenario.segmen_memotong_kotak((-5, 11), (15, 11), k)  # sejajar di atas kotak
    assert not skenario.segmen_memotong_kotak((11, 0), (20, 5), k)    # seluruhnya di kanan
    assert not skenario.segmen_memotong_kotak((-1, -1), (-1, 20), k)  # vertikal, di kiri kotak


def test_garis_panjang_tanpa_titik_di_dalam_kotak_tetap_terdeteksi(data):
    # Kotak kecil di tengah Laut Jawa: tidak ada simpul dom-2 di dalamnya, tetapi segmennya melintas
    k = Kotak("laut jawa", 109.5, 110.0, -7.0, -6.5)
    assert skenario.kabel_lewat_kotak(data, k) == {"dom-2"}


def test_kabel_lewat_kotak_menyaring_transit_dan_rencana(data):
    k_utara = Kotak("utara", 99.0, 102.0, 5.0, 7.0)
    assert skenario.kabel_lewat_kotak(data, k_utara) == set()
    assert skenario.kabel_lewat_kotak(data, k_utara, sertakan_transit=True) == {"tr-1"}
    k_manado = Kotak("manado", 124.0, 126.0, 1.0, 2.0)
    assert skenario.kabel_lewat_kotak(data, k_manado) == set()
    assert skenario.kabel_lewat_kotak(data, k_manado, hanya_aktif=False) == {"int-3"}


def test_area_preset_masuk_akal():
    assert len(skenario.AREA_PRESET) >= 5
    nama = [k.nama for k in skenario.AREA_PRESET]
    assert len(nama) == len(set(nama))
    for k in skenario.AREA_PRESET:
        assert k.lon_min < k.lon_max and k.lat_min < k.lat_max
        lon, lat = k.pusat()
        assert 94 <= lon <= 142 and -12 <= lat <= 8


def test_area_preset_pada_data_sungguhan():
    from src import muat_data

    d = muat_data.muat_semua()
    batam = next(k for k in skenario.AREA_PRESET if "Batam" in k.nama)
    ids = skenario.kabel_lewat_kotak(d, batam)
    assert "batam-singapore-cable-system-bscs" in ids
    assert len(ids) >= 10


def test_kotak_memuat_dan_pusat():
    k = skenario.Kotak("uji", 100, 110, -5, 5)
    assert k.memuat(100, -5) and k.memuat(110, 5)        # tepi ikut dihitung
    assert not k.memuat(110.01, 0)
    assert k.pusat() == (105, 0)


def test_garis_lewat_kotak_multiline_dan_titik_tunggal():
    k = skenario.Kotak("uji", 0, 10, 0, 10)
    jauh = [[-20, -20], [-15, -20]]
    lewat = [[-5, 5], [15, 5]]
    assert skenario.garis_lewat_kotak([jauh, lewat], k)   # cukup satu bagian yang lewat
    assert not skenario.garis_lewat_kotak([jauh], k)
    assert skenario.garis_lewat_kotak([[[5, 5]]], k)      # garis satu titik di dalam kotak
    assert not skenario.garis_lewat_kotak([[[50, 5]]], k)
    assert not skenario.garis_lewat_kotak([], k)


def test_area_preset_valid():
    nama = [k.nama for k in skenario.AREA_PRESET]
    assert len(nama) == len(set(nama))
    for k in skenario.AREA_PRESET:
        assert k.lon_min < k.lon_max and k.lat_min < k.lat_max, k.nama
        # semua area preset ada di sekitar Indonesia
        assert 94 <= k.lon_min and k.lon_max <= 142 and -12 <= k.lat_min and k.lat_max <= 7, k.nama
        assert k.keterangan
