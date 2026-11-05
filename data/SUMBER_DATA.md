# Sumber data

Semua data dalam proyek ini publik. Tidak ada yang berasal dari akun berbayar atau sumber tertutup.

## 1. Kabel bawah laut dan landing station — Submarine Cable Map (TeleGeography)

- **Apa:** basis data kabel serat optik bawah laut seluruh dunia yang dirawat TeleGeography, perusahaan riset telekomunikasi. Mencakup nama kabel, landing station, pemilik, pemasok, panjang, tahun siap pakai (RFS, *ready for service*), status rencana/aktif, dan geometri jalur kabel.
- **URL:** <https://www.submarinecablemap.com>. API publik yang dipakai (tanpa kunci):
  - `https://www.submarinecablemap.com/api/v3/cable/all.json` — daftar id dan nama semua kabel
  - `https://www.submarinecablemap.com/api/v3/cable/cable-geo.json` — geometri semua kabel (GeoJSON MultiLineString)
  - `https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json` — koordinat semua landing station
  - `https://www.submarinecablemap.com/api/v3/cable/<id>.json` — detail per kabel (landing station, pemilik, panjang, RFS)
- **Snapshot:** tanggal pembuatan ada di `META.json`. Perbarui dengan `python scripts/bangun_data.py` (±1 menit, ±720 permintaan HTTP kecil).
- **Lisensi:** TeleGeography memublikasikan Submarine Cable Map dengan lisensi [Creative Commons Attribution-NonCommercial-ShareAlike 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Proyek ini non-komersial, mencantumkan atribusi, dan membagikan turunannya dengan lisensi yang sama untuk bagian data.
- **Keterbatasan:**
  - Jalur kabel adalah **penyederhanaan** yang dipublikasikan operator, bukan rute presisi; begitu pula titik landing station (sering digeser ke kota terdekat).
  - **Tidak ada kapasitas** (Tbps). TeleGeography menjual data kapasitas secara terpisah; di sini semua kabel diperlakukan sama.
  - Kabel dengan cabang (misalnya SeaMeWe-5, Palapa Ring) direkam sebagai satu entitas dengan banyak landing station; segmen mana yang menghubungkan kota mana tidak tersedia.
  - Nama kota kadang berbeda ejaan untuk tempat yang sama (*Benculuk*/*Beculuk*, *Sangata*/*Sangatta*, *Labuan Bajo*/*Labuhan Bajo*) karena bersumber dari pengumuman operator berbeda. Tidak digabung secara manual agar data tetap sama dengan sumbernya; sambungan darat di model menyatukan mereka secara otomatis.
  - Kabel domestik kecil milik operator lokal bisa saja belum tercatat.

## 2. File yang dibangun — `kabel.csv`, `landing_station.csv`, `kabel_landing.csv`, `kabel_geo.json`

| File | Isi | Kolom penting |
|---|---|---|
| `kabel.csv` | Satu baris per kabel yang relevan untuk Indonesia | `kategori` (internasional / domestik / transit), `status` (aktif / rencana), `tahun_rfs`, `panjang_km`, `pemilik`, `pemasok`, `n_landing`, `n_landing_indonesia`, `negara` (dipisah `\|`) |
| `landing_station.csv` | Satu baris per landing station yang disinggahi kabel di atas (Indonesia dan luar negeri) | `kota`, `negara`, `lat`, `lon`, `wilayah` (hanya Indonesia, dari `src/wilayah.py`) |
| `kabel_landing.csv` | Relasi banyak-ke-banyak kabel ↔ landing station | `id_kabel`, `id_landing`, `urutan` (urutan seperti di sumber) |
| `kabel_geo.json` | GeoJSON garis untuk kabel di `kabel.csv` saja (bukan 713 kabel dunia), agar repo tetap kecil | `properties.id`, `nama`, `kategori`, `status` |
| `META.json` | Tanggal pembuatan dan jumlah baris | |

Definisi kategori:

- **internasional** — minimal satu landing station di Indonesia dan minimal satu di luar negeri.
- **domestik** — semua landing station di Indonesia.
- **transit** (di aplikasi disebut *kabel kawasan*) — tidak mendarat di Indonesia, tetapi ada titik garisnya di dalam kotak 94–142° BT, 12° LS–8° LU. Termasuk kabel Malaysia, Singapura, Timor-Leste, dan kabel lintas benua yang lewat Selat Malaka. Hanya untuk konteks peta; tidak ikut dalam simulasi.

## 3. Pembagian wilayah — `src/wilayah.py`

- Tujuh wilayah besar (Sumatra & Kepulauan Riau, Jawa, Kalimantan, Sulawesi, Bali & Nusa Tenggara, Maluku, Papua) ditentukan dengan aturan kotak lintang-bujur buatan sendiri, diuji pada 38 kota di `tests/test_wilayah.py`.
- Bukan batas administratif. Beberapa pulau di perbatasan wilayah (misalnya Alor, Taliabu, Tanimbar) ditangani dengan aturan khusus; bila ada landing station baru yang salah wilayah, tambahkan ke daftar uji lalu perbaiki aturannya.

## 4. Area laut untuk skenario — `src/skenario.py`

- Delapan kotak kasar (Selat Sunda, Perairan Batam-Singapura, Selat Malaka utara, Teluk Jakarta, Selat Lombok, Selat Makassar, Laut Sulawesi, Laut Banda) dipilih karena sering disebut dalam pemberitaan gangguan kabel (jangkar kapal, gempa, pengerukan). Koordinatnya perkiraan, bukan zona resmi.

## 5. Lokasi data center — `data_center.csv`

- Salinan dari proyek [dc-impact-dashboard](https://github.com/Avalon2222/dc-impact-dashboard): 27 data center besar di Indonesia dengan koordinat, operator, kapasitas IT (MW), status, dan sumber per baris. Hanya dipakai sebagai lapisan peta opsional untuk melihat kedekatan data center dengan landing station (Jakarta-Bekasi-Karawang, Batam).
