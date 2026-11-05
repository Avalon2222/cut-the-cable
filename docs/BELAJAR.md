# 📚 Belajar dari proyek ini

Panduan ini menjelaskan apa yang terjadi di balik aplikasi, dari API publik Submarine Cable Map sampai peta
"siapa yang gelap". Tidak perlu latar belakang telekomunikasi; cukup Python dasar dan rasa penasaran. Setiap bagian
menunjuk ke file dan fungsi yang bisa langsung dibaca.

---

## 1. Gambaran besar

```
Submarine Cable Map (API) ─► scripts/bangun_data.py ─► data/*.csv, kabel_geo.json
                                                            │
                               src/wilayah.py (lat/lon → wilayah) ◄─┘
                                                            │
       src/skenario.py (kabel mana yang putus?) ─► src/jaringan.py (graf → status) ─► app.py (peta)
```

Tiga pertanyaan yang dijawab aplikasi, dan di mana jawabannya dihitung:

| Pertanyaan | Fungsi |
|---|---|
| Kabel apa saja yang menyentuh Indonesia, lewat mana? | `scripts/bangun_data.py`, lalu `muat_data.muat_semua` |
| Kalau kabel X putus, landing station mana yang gelap? | `skenario.*` untuk memilih X, `jaringan.simulasi` untuk menghitung |
| Seberapa bergantung Indonesia pada Singapura? | `jaringan.gateway_luar_negeri` |

---

## 2. Kabel bawah laut dalam 5 menit

Sebuah kabel bawah laut adalah seikat serat optik setebal selang taman, dilindungi baja dan polietilena, direntangkan
di dasar laut sampai ribuan kilometer. Di setiap ujung (dan cabangnya) kabel naik ke darat di **landing station**:
bangunan kecil di pantai tempat kabel disambung ke jaringan darat. Beberapa istilah yang muncul di data:

| Istilah | Arti |
|---|---|
| **RFS** (*ready for service*) | Tahun kabel mulai dipakai komersial. `is_planned = true` berarti belum RFS |
| **Landing point / landing station** | Titik pendaratan. Satu kabel bisa punya 2 sampai 20 lebih |
| **Pemilik (owners)** | Konsorsium operator (Telkom/Telin, Singtel, Meta, Google, dsb.) |
| **Pemasok (suppliers)** | Pabrikan kabel: ASN, SubCom, NEC, HMN Tech |
| **Branching unit** | Percabangan di dasar laut; inilah mengapa satu kabel bisa mendarat di banyak kota |

Kabel putus bukan hal langka. Penyebab terbanyak di dunia adalah jangkar dan jaring kapal (sekitar dua pertiga kasus),
disusul gempa dan longsor bawah laut. Di Indonesia, perairan Batam-Singapura dan Teluk Jakarta adalah tempat yang paling
sering disebut dalam berita gangguan, dan keduanya menjadi preset di aplikasi.

---

## 3. Mengambil data dari API publik

Submarine Cable Map menyediakan beberapa file JSON tanpa kunci. `scripts/bangun_data.py` mengambil:

1. `cable/all.json`: daftar `{id, name}` semua kabel (713 pada November 2026).
2. `cable/cable-geo.json`: GeoJSON **MultiLineString** untuk setiap kabel.
3. `landing-point/landing-point-geo.json`: koordinat setiap landing station.
4. `cable/<id>.json` untuk setiap kabel: landing station beserta negaranya, pemilik, panjang, RFS.

Langkah 4 berarti 713 permintaan HTTP kecil. Supaya tidak lama, dipakai *thread pool*:

```python
with ThreadPoolExecutor(max_workers=12) as ex:
    kabel_detail = list(ex.map(detail, daftar))
```

Dua belas permintaan berjalan bersamaan, selesai dalam ±1 menit. Perhatikan `SESI.headers["User-Agent"]`: sopan
santun dasar saat memakai API orang lain adalah memberi tahu siapa yang mengakses.

Setelah itu data disaring. Kabel dikategorikan dengan menghitung landing station di Indonesia:

```python
n_idn = sum(1 for l in landing if l["country"] == "Indonesia")
if n_idn == len(landing):   kategori = "domestik"
elif n_idn > 0:             kategori = "internasional"
elif lewat_kotak(geometri): kategori = "transit"      # hanya lewat perairan sekitar
```

Hasilnya disimpan dalam tiga tabel yang saling terhubung: `kabel.csv` (satu baris per kabel), `landing_station.csv`
(satu baris per stasiun), dan `kabel_landing.csv` (pasangan kabel-stasiun). Ini bentuk **banyak-ke-banyak**: satu kabel
mendarat di banyak stasiun, satu stasiun disinggahi banyak kabel. Menyimpannya sebagai tabel relasi terpisah jauh lebih
mudah diolah pandas daripada kolom berisi daftar.

---

## 4. Dari koordinat ke wilayah (`src/wilayah.py`)

Data sumber hanya memberi nama kota dan koordinat. Untuk menjawab "daerah mana yang terdampak", setiap titik di
Indonesia dipetakan ke tujuh wilayah besar dengan aturan kotak lintang-bujur yang diperiksa **berurutan**:

```python
if lon >= 135.0 or (lon >= 130.3 and lat >= -4.7):               return "Papua"
if (lon >= 125.5 and -9 < lat < 2.5) or (lon >= 124.3 and -3.5 < lat < 0): return "Maluku"
if lat < -7.8 and lon >= 114.45:                                  return "Bali & Nusa Tenggara"
if lon >= 118.2 and lat > -7.0:                                   return "Sulawesi"
if lon >= 108.7 and lat > -4.5:                                   return "Kalimantan"
if lat < -4.5 and (lon >= 106.1 or (lon > 105.5 and lat < -5.9)): return "Jawa"
return "Sumatra & Kepulauan Riau"
```

Urutan penting: Tual (132,8° BT) memenuhi syarat Papua kalau hanya melihat bujur, tetapi lintangnya (-5,6°) menggagalkan
aturan pertama sehingga jatuh ke Maluku. Aturan seperti ini rapuh, maka dilindungi 38 kasus uji di
`tests/test_wilayah.py`. Kalau ada titik baru yang salah wilayah: tambahkan ke daftar uji dulu, pastikan tesnya gagal,
baru ubah aturannya. Itu inti *test-driven development* versi paling sederhana.

---

## 5. Jaringan kabel sebagai graf (`src/jaringan.py`)

Inilah inti proyek. Sebuah **graf** terdiri dari simpul (*node*) dan sisi (*edge*). Di sini:

- simpul = landing station, dengan atribut `negara`;
- sisi = "dua stasiun ini terhubung oleh kabel K".

Satu kabel dengan lima landing station menjadi 10 sisi (semua pasangan), masing-masing diberi label id kabel:

```python
for id_kabel, grup in relasi.groupby("id_kabel"):
    simpul = grup.sort_values("urutan")["id_landing"].tolist()
    for a, b in combinations(simpul, 2):
        if G.has_edge(a, b): G[a][b]["kabel"].add(id_kabel)
        else:                G.add_edge(a, b, kabel={id_kabel})
```

Mengapa semua pasangan, bukan rantai berurutan? Karena data publik tidak menyimpan topologi segmen: kita tahu SeaMeWe-5
mendarat di 18 tempat, tetapi tidak tahu segmen mana yang menghubungkan Dumai ke Singapura. Asumsi "semua saling
terhubung" adalah yang paling jujur dengan data yang ada, dan konsekuensinya satu kabel putus berarti seluruh kabel mati.

**Memutus kabel** = membangun ulang graf tanpa kabel itu. Lalu pertanyaan "masih tersambung ke dunia?" dijawab dengan
**komponen terhubung**: kelompok simpul yang saling bisa dicapai.

```python
for komp in nx.connected_components(G):
    ada_asing = any(G.nodes[n]["negara"] != "Indonesia" for n in komp)
```

Kalau komponen sebuah stasiun tidak memuat simpul luar negeri, stasiun itu **terputus dari dunia**, meskipun kabelnya
sendiri tidak putus. Itulah yang terjadi pada Surabaya di jaringan mainan `tests/test_jaringan.py` ketika kedua kabel
ke Singapura dimatikan: kabel Jakarta-Surabaya masih utuh, tetapi Jakarta sudah tidak punya jalan keluar.

### Sisi darat

Versi pertama model ini memberi hasil aneh: memutus semua kabel ke Singapura membuat 64 landing station "terputus dari
dunia", termasuk hampir seluruh Indonesia timur. Penyebabnya: data tidak tahu bahwa Manado dan Kauditan (30 km) jelas
tersambung lewat darat, begitu pula Jakarta, Ancol, dan Tanjung Pakis. Solusinya sisi "darat" untuk pasangan stasiun
senegara yang berjarak kurang dari radius:

```python
for (a, la1, lo1), (b, la2, lo2) in combinations(baris, 2):
    if jarak_km(la1, lo1, la2, lo2) < radius_km:
        G.add_edge(a, b, kabel=set(), darat=True)
```

`jarak_km` memakai rumus **haversine** (jarak lingkaran besar di bola). Dengan radius 60 km, skenario yang sama hanya
menyisakan 2 stasiun terputus. Pelajarannya: model yang terlalu sederhana bisa menyesatkan, dan setiap asumsi tambahan
harus bisa diatur dan dijelaskan (karena itu radiusnya jadi slider, bukan konstanta tersembunyi).

### Status

Setelah dua graf (sebelum dan sesudah) dihitung, setiap landing station Indonesia diberi label dengan aturan
berurutan di `tentukan_status`:

| Kondisi | Status |
|---|---|
| tidak punya kabel sejak awal | Aman (bukan bagian jaringan aktif) |
| kabel sisa 0 dan tidak ada jalur ke luar negeri | Gelap total |
| sebelumnya punya jalur ke luar negeri, sekarang tidak | Terputus dari dunia |
| kabel sisa 0 tetapi masih ada jalur (lewat darat) | Hidup lewat darat |
| kehilangan kabel, sisa tepat 1 | Rentan (1 kabel tersisa) |
| kehilangan kabel, sisa ≥ 2 | Kehilangan jalur |
| tidak kehilangan apa-apa | Aman |

**Pintu keluar internasional** dihitung per komponen: himpunan kabel internasional yang muncul di sisi mana pun dalam
komponen itu. Angkanya menjawab "berapa jalan keluar berbeda yang masih bisa dipakai", ukuran redundansi yang lebih
berguna daripada sekadar "masih tersambung atau tidak".

---

## 6. Memilih kabel yang diputus (`src/skenario.py`)

Tiga cara pertama hanya penyaringan tabel. Yang menarik adalah cara keempat: **semua kabel yang melewati sebuah kotak di
laut**. Mengecek apakah ada titik sudut garis yang jatuh di dalam kotak tidak cukup, karena ruas kabel di laut lepas bisa
ratusan kilometer dan kotaknya kecil. Yang dibutuhkan: apakah **ruas garis** memotong persegi?

Algoritma **Liang-Barsky** menjawabnya tanpa trigonometri. Ruas dari P1 ke P2 ditulis sebagai P1 + t·(P2 − P1) dengan
t ∈ [0, 1]. Setiap sisi kotak memberi batasan pada t; kalau setelah empat batasan selang t masih tidak kosong, ruasnya
memotong kotak.

```python
t0, t1 = 0.0, 1.0
for p, q in ((-dx, x1 - lon_min), (dx, lon_max - x1), (-dy, y1 - lat_min), (dy, lat_max - y1)):
    if p == 0:
        if q < 0: return False       # sejajar sisi dan di luar
        continue
    t = q / p
    if p < 0: t0 = max(t0, t)        # ruas masuk kotak di sini
    else:     t1 = min(t1, t)        # ruas keluar kotak di sini
    if t0 > t1: return False
return True
```

Uji di `tests/test_skenario.py` mencakup kasus yang sering salah: garis menembus kiri-kanan tanpa titik di dalam, garis
sejajar sisi di luar kotak, dan garis vertikal.

---

## 7. Menggambar peta (`app.py`)

Plotly `Scattermap` menggambar garis di atas peta dasar (CARTO dark matter) dari deret koordinat. Trik yang dipakai:
satu *trace* untuk semua kabel dalam satu kategori, dengan `None` sebagai pemisah garis, dan `hovertext` per titik
supaya nama kabel muncul saat kursor melayang. 118 kabel menjadi tiga trace, bukan 118, sehingga peta ringan dan
legendanya rapi.

Untuk peta dampak, landing station digambar per status (satu trace per warna, urutan terbalik agar yang paling parah
digambar terakhir dan tidak tertutup), kabel putus digambar merah tebal di atas kabel lain yang redup.

---

## 8. Batas model (penting untuk dibaca sebelum menyimpulkan apa pun)

- **Tidak ada kapasitas.** Satu kabel tua 2003 dan satu kabel 2025 berkapasitas ratusan Tbps dihitung sama. "Masih
  tersambung" bukan berarti "masih cukup".
- **Kabel = satu kesatuan.** Putus di satu segmen dianggap mematikan seluruh kabel. Kenyataannya operator bisa tetap
  memakai segmen lain.
- **Jaringan darat** hanya didekati dengan radius; serat optik Jakarta-Surabaya atau Kalimantan-Sarawak tidak dimodelkan.
- **Satelit, radio, dan rerouting** tidak ada.
- **Nama kota ganda** di sumber (Benculuk/Beculuk) dibiarkan apa adanya; sisi darat menyatukannya secara otomatis.

Semua itu ditulis juga di tab *Data & Sources* aplikasi. Sebuah model boleh sederhana, asal batasnya jelas.

---

## 9. Cara kode ini disusun

- `src/` berisi logika murni tanpa Streamlit, sehingga bisa diuji dengan pytest dan dipakai dari notebook.
- `app.py` hanya memanggil fungsi di `src/` dan menggambar. Kalau ada perhitungan baru, taruh di `src/` dulu, tulis
  tesnya, baru tampilkan.
- `scripts/` untuk pekerjaan sekali jalan (membangun data), dipisah dari aplikasi supaya aplikasi tidak butuh internet.
- Setiap fungsi punya docstring yang menjelaskan **apa** dan **mengapa**, bukan hanya cara memanggilnya.

Lanjutkan ke [`LATIHAN.md`](LATIHAN.md) untuk mencoba mengubah dan memperluas proyek ini.
