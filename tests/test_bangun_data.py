"""Tes helper di scripts/bangun_data.py (tanpa mengunduh dari submarinecablemap)."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "bangun_data.py"
spec = importlib.util.spec_from_file_location("bangun_data", PATH)
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


@pytest.mark.parametrize("teks, harapan", [
    ("19,888 km", 19888.0), ("650 KM", 650.0), ("1.5 km", 1.5), ("", None), (None, None), ("n.a.", None),
])
def test_panjang_km(teks, harapan):
    assert bd.panjang_km(teks) == harapan


def test_nama_kota_ambil_bagian_pertama():
    assert bd.nama_kota("Jakarta, Indonesia") == "Jakarta"
    assert bd.nama_kota("Grover Beach, CA, United States") == "Grover Beach"
    assert bd.nama_kota("Tanjung Pakis") == "Tanjung Pakis"


def test_lewat_kotak_pakai_urutan_lon_lat():
    # Koordinat GeoJSON: [lon, lat]. Satu titik di Laut Jawa sudah cukup.
    lewat = [[[103.0, 1.5], [106.8, -6.0]]]
    tidak = [[[139.7, 35.6], [-122.4, 37.7]]]          # Tokyo - San Francisco
    assert bd.lewat_kotak(lewat)
    assert not bd.lewat_kotak(tidak)
    assert not bd.lewat_kotak([])
