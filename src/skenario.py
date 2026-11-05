"""
src/skenario.py - cara memilih kabel mana yang "diputus"
========================================================
Ada empat cara di aplikasi, semuanya menghasilkan himpunan id kabel:

  1. pilih_manual        : pengguna mencentang kabel satu per satu (tidak perlu fungsi khusus)
  2. kabel_di_landing    : semua kabel yang mendarat di satu landing station (stasiun mati)
  3. kabel_ke_negara     : semua kabel internasional yang mendarat di negara tertentu
  4. kabel_lewat_kotak   : semua kabel yang garisnya melewati sebuah kotak di laut
                           (gempa, longsor bawah laut, jangkar kapal, atau sabotase di satu area)

Untuk cara ke-4 dipakai uji potongan garis vs persegi (algoritma Liang-Barsky), bukan hanya
mengecek titik sudut garis, supaya kotak kecil yang dilintasi segmen panjang tetap terdeteksi.
"""

from __future__ import annotations

from dataclasses import dataclass

from .muat_data import Data


@dataclass(frozen=True)
class Kotak:
    """Persegi di peta: bujur barat-timur, lintang selatan-utara (derajat)."""
    nama: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float
    keterangan: str = ""

    def memuat(self, lon: float, lat: float) -> bool:
        return self.lon_min <= lon <= self.lon_max and self.lat_min <= lat <= self.lat_max

    def pusat(self) -> tuple[float, float]:
        return ((self.lon_min + self.lon_max) / 2, (self.lat_min + self.lat_max) / 2)


# Area yang sering disebut dalam kajian kerentanan kabel di Indonesia. Koordinat dibuat sendiri
# sebagai kotak kasar di peta, bukan zona resmi apa pun.
AREA_PRESET: list[Kotak] = [
    Kotak("Selat Sunda", 105.3, 106.3, -6.7, -5.6,
          "Jalur Anyer-Kalianda dan pendaratan Jakarta dari barat; zona Gunung Anak Krakatau."),
    Kotak("Perairan Batam-Singapura", 103.4, 104.7, 0.6, 1.5,
          "Simpul tersibuk: hampir semua kabel internasional Indonesia singgah di sini. Lalu lintas kapal padat."),
    Kotak("Selat Malaka utara (Dumai-Medan)", 98.0, 101.8, 1.3, 4.6,
          "Kabel Sumatra-Malaysia dan jalur ke Penang; jalur kapal paling padat di dunia."),
    Kotak("Teluk Jakarta", 106.5, 107.5, -6.2, -5.4,
          "Landing station Jakarta, Ancol, Tanjung Pakis, Pantai Mutiara. Area jangkar kapal dan reklamasi."),
    Kotak("Selat Lombok", 115.4, 116.4, -9.3, -8.0,
          "Alur Laut Kepulauan Indonesia (ALKI) II; kabel Bali-Lombok dan jalur ke Australia."),
    Kotak("Selat Makassar", 117.3, 119.8, -4.5, 1.0,
          "Penghubung Kalimantan-Sulawesi dan jalur utara-selatan ALKI II; palung dalam dan gempa aktif."),
    Kotak("Laut Sulawesi (Manado)", 123.8, 126.8, 0.3, 2.8,
          "Pendaratan Manado untuk kabel ke Filipina, Guam, dan Amerika; zona subduksi aktif."),
    Kotak("Laut Banda (Ambon)", 126.5, 130.5, -6.5, -2.5,
          "Jalur Palapa Ring Timur di laut dalam yang rawan gempa besar."),
]


def kabel_di_landing(data: Data, id_landing: str, hanya_aktif: bool = True) -> set[str]:
    """Semua kabel yang mendarat di satu landing station."""
    ids = set(data.kabel_dari_landing(id_landing))
    if hanya_aktif:
        aktif = set(data.kabel.loc[data.kabel["status"] == "aktif", "id"])
        ids &= aktif
    return ids


def kabel_ke_negara(data: Data, negara: str, hanya_aktif: bool = True) -> set[str]:
    """Semua kabel internasional (yang mendarat di Indonesia) dengan landing station di `negara`."""
    k = data.kabel[(data.kabel["kategori"] == "internasional")]
    if hanya_aktif:
        k = k[k["status"] == "aktif"]
    return set(k.loc[k["negara"].str.split("|").apply(lambda n: negara in n), "id"])


def segmen_memotong_kotak(p1: tuple[float, float], p2: tuple[float, float], kotak: Kotak) -> bool:
    """
    Uji apakah ruas garis p1-p2 (lon, lat) memotong atau berada di dalam kotak.
    Implementasi Liang-Barsky: potong parameter t di [0,1] dengan empat sisi kotak.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - kotak.lon_min), (dx, kotak.lon_max - x1),
                 (-dy, y1 - kotak.lat_min), (dy, kotak.lat_max - y1)):
        if p == 0:
            if q < 0:
                return False          # sejajar sisi dan di luar
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


def garis_lewat_kotak(koordinat_multiline, kotak: Kotak) -> bool:
    """True bila ada satu ruas saja dari MultiLineString yang memotong kotak."""
    for garis in koordinat_multiline:
        for (x1, y1), (x2, y2) in zip(garis[:-1], garis[1:]):
            if segmen_memotong_kotak((x1, y1), (x2, y2), kotak):
                return True
        if len(garis) == 1 and kotak.memuat(*garis[0]):
            return True
    return False


def kabel_lewat_kotak(data: Data, kotak: Kotak, hanya_aktif: bool = True, sertakan_transit: bool = False) -> set[str]:
    """Id kabel yang garisnya melewati kotak. Kabel kawasan (transit) hanya ikut bila diminta."""
    status = data.kabel.set_index("id")["status"].to_dict()
    kategori = data.kabel.set_index("id")["kategori"].to_dict()
    hasil = set()
    for f in data.geo["features"]:
        cid = f["properties"]["id"]
        if hanya_aktif and status.get(cid) != "aktif":
            continue
        if not sertakan_transit and kategori.get(cid) == "transit":
            continue
        if garis_lewat_kotak(f["geometry"]["coordinates"], kotak):
            hasil.add(cid)
    return hasil
