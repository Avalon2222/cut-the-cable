"""Uji pembagian wilayah dari koordinat."""

import pytest

from src import wilayah

KOTA = [
    # (nama, lat, lon, wilayah yang diharapkan)
    ("Jakarta", -6.2, 106.8, "Jawa"),
    ("Anyer", -6.1, 105.9, "Jawa"),
    ("Surabaya", -7.3, 112.7, "Jawa"),
    ("Banyuwangi (Benculuk)", -8.6, 114.1, "Jawa"),
    ("Bawean", -5.8, 112.6, "Jawa"),
    ("Kalianda, Lampung", -5.8, 105.6, "Sumatra & Kepulauan Riau"),
    ("Bandar Lampung", -5.4, 105.3, "Sumatra & Kepulauan Riau"),
    ("Batam", 1.1, 104.0, "Sumatra & Kepulauan Riau"),
    ("Natuna", 3.9, 108.1, "Sumatra & Kepulauan Riau"),
    ("Medan", 3.8, 98.7, "Sumatra & Kepulauan Riau"),
    ("Tanjung Pandan, Belitung", -2.8, 107.7, "Sumatra & Kepulauan Riau"),
    ("Pontianak", 0.0, 109.3, "Kalimantan"),
    ("Balikpapan", -1.3, 116.8, "Kalimantan"),
    ("Tarakan", 3.3, 117.6, "Kalimantan"),
    ("Banjarmasin", -3.3, 114.6, "Kalimantan"),
    ("Makassar", -5.2, 119.4, "Sulawesi"),
    ("Mamuju", -2.7, 118.9, "Sulawesi"),
    ("Manado", 1.5, 124.8, "Sulawesi"),
    ("Melonguane, Talaud", 4.0, 126.7, "Sulawesi"),
    ("Wakatobi", -5.3, 123.5, "Sulawesi"),
    ("Selayar", -6.1, 120.5, "Sulawesi"),
    ("Denpasar", -8.7, 115.2, "Bali & Nusa Tenggara"),
    ("Candikusuma, Jembrana", -8.3, 114.5, "Bali & Nusa Tenggara"),
    ("Mataram", -8.6, 116.1, "Bali & Nusa Tenggara"),
    ("Kupang", -10.2, 123.6, "Bali & Nusa Tenggara"),
    ("Alor", -8.3, 124.4, "Bali & Nusa Tenggara"),
    ("Ternate", 0.8, 127.4, "Maluku"),
    ("Morotai", 2.4, 128.4, "Maluku"),
    ("Ambon", -3.7, 128.2, "Maluku"),
    ("Taliabu", -1.8, 124.8, "Maluku"),
    ("Tual", -5.6, 132.8, "Maluku"),
    ("Saumlaki", -8.1, 131.2, "Maluku"),
    ("Tiakur, Maluku Barat Daya", -8.2, 127.8, "Maluku"),
    ("Sorong", -0.9, 131.3, "Papua"),
    ("Fakfak", -3.1, 133.0, "Papua"),
    ("Timika", -4.6, 136.9, "Papua"),
    ("Merauke", -8.5, 140.4, "Papua"),
    ("Jayapura", -2.6, 140.7, "Papua"),
]


@pytest.mark.parametrize("nama,lat,lon,harapan", KOTA, ids=[k[0] for k in KOTA])
def test_tentukan_wilayah(nama, lat, lon, harapan):
    assert wilayah.tentukan_wilayah(lat, lon) == harapan


def test_daftar_wilayah_lengkap():
    assert len(wilayah.WILAYAH) == 7
    for _, lat, lon, _ in KOTA:
        assert wilayah.tentukan_wilayah(lat, lon) in wilayah.WILAYAH


def test_kotak_indonesia():
    assert wilayah.di_kotak_indonesia(-6.2, 106.8)
    assert wilayah.di_kotak_indonesia(1.3, 103.8)        # Singapura sengaja ikut (kabel kawasan)
    assert not wilayah.di_kotak_indonesia(35.7, 139.7)   # Tokyo
    assert not wilayah.di_kotak_indonesia(-33.9, 151.2)  # Sydney
