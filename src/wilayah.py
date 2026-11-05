"""
src/wilayah.py - pembagian wilayah Indonesia dari koordinat
===========================================================
Landing station dari TeleGeography hanya punya nama kota dan koordinat, tidak ada provinsi.
Supaya simulasi bisa menjawab "daerah mana yang terdampak", setiap titik di Indonesia
dikelompokkan ke tujuh wilayah besar dengan aturan kotak lintang-bujur sederhana.

Aturan ini kasar (garis lurus, bukan batas provinsi), tetapi cukup untuk 146 titik yang ada
dan diuji di tests/test_wilayah.py. Urutan pemeriksaan penting: Papua dulu, lalu Maluku, dan
seterusnya, karena kotak-kotaknya saling tumpang tindih di tepinya.
"""

from __future__ import annotations

WILAYAH = [
    "Sumatra & Kepulauan Riau",
    "Jawa",
    "Kalimantan",
    "Sulawesi",
    "Bali & Nusa Tenggara",
    "Maluku",
    "Papua",
]

# Kotak perairan Indonesia secara longgar (lon_min, lon_max, lat_min, lat_max).
# Dipakai untuk memilih kabel "kawasan" yang lewat tanpa mendarat. Sengaja agak lebar
# sehingga Singapura, Selat Malaka, dan Timor-Leste ikut masuk.
KOTAK_INDONESIA = (94.0, 142.0, -12.0, 8.0)


def di_kotak_indonesia(lat: float, lon: float) -> bool:
    lon_min, lon_max, lat_min, lat_max = KOTAK_INDONESIA
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def tentukan_wilayah(lat: float, lon: float) -> str:
    """
    Petakan satu koordinat di Indonesia ke salah satu dari tujuh wilayah besar.

    >>> tentukan_wilayah(-6.1, 106.8)   # Jakarta
    'Jawa'
    >>> tentukan_wilayah(1.1, 104.0)    # Batam
    'Sumatra & Kepulauan Riau'
    """
    # 1. Papua: semua yang di timur 135° BT, plus kepala burung (Sorong, Fakfak, Kaimana, Timika)
    if lon >= 135.0 or (lon >= 130.3 and lat >= -4.7):
        return "Papua"
    # 2. Maluku: Halmahera, Seram, Ambon, Kei, Aru, Tanimbar, Maluku Barat Daya, Sula/Taliabu
    if (lon >= 125.5 and -9.0 < lat < 2.5) or (lon >= 124.3 and -3.5 < lat < 0.0):
        return "Maluku"
    # 3. Bali dan Nusa Tenggara: selatan Jawa-Bali, timur Selat Bali (±114,45° BT)
    if lat < -7.8 and lon >= 114.45:
        return "Bali & Nusa Tenggara"
    # 4. Sulawesi: timur Selat Makassar (±118,2° BT) sampai Sangihe-Talaud di utara
    if lon >= 118.2 and lat > -7.0:
        return "Sulawesi"
    # 5. Kalimantan: barat Selat Makassar, utara Laut Jawa, timur Selat Karimata (±108,7° BT)
    if lon >= 108.7 and lat > -4.5:
        return "Kalimantan"
    # 6. Jawa dan Madura: pisahkan dari ujung Lampung lewat garis Selat Sunda
    if lat < -4.5 and ((lon >= 106.1) or (lon > 105.5 and lat < -5.9)):
        return "Jawa"
    # 7. Sisanya: Sumatra beserta Kepulauan Riau, Natuna, Bangka-Belitung
    return "Sumatra & Kepulauan Riau"
