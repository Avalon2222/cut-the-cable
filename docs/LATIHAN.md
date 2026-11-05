# 🏋️ Latihan

Diurutkan dari yang mudah ke yang lebih menantang. Setiap latihan dilengkapi petunjuk dan kunci jawaban yang dapat
dibuka. Usahakan mencoba minimal 10 menit sebelum membuka kunci. Setelah setiap latihan, jalankan
`python -m pytest tests/` dan `streamlit run app.py`.

---

### Latihan 1 — Ganti warna kabel domestik ⭐

Kabel domestik saat ini oranye (`#f59e0b`). Ubah menjadi hijau `#4ade80` dan pastikan peta utama, peta dampak, dan
linimasa tahun ikut berubah dengan mengedit **satu** tempat.

<details><summary>Petunjuk</summary>
Semua warna kategori ada di kamus <code>WARNA_KATEGORI</code> di bagian atas <code>app.py</code>; linimasa memakai kamus itu
lewat <code>warna_kelompok</code>.
</details>

<details><summary>Kunci</summary>

```python
WARNA_KATEGORI = {"internasional": "#22d3ee", "domestik": "#4ade80", "transit": "#5b6b82"}
```
</details>

---

### Latihan 2 — Tambah area laut baru ⭐

Tambahkan preset "Laut Natuna" (kira-kira 105–110° BT, 2–5° LU) ke daftar area, lalu lihat kabel apa saja yang terkena.
Tulis juga satu tes bahwa preset baru itu memilih minimal satu kabel.

<details><summary>Petunjuk</summary>
Daftar <code>AREA_PRESET</code> ada di <code>src/skenario.py</code>; aplikasi membacanya otomatis. Untuk tes, tiru
<code>test_area_preset_pada_data_sungguhan</code> di <code>tests/test_skenario.py</code>.
</details>

<details><summary>Kunci</summary>

```python
Kotak("Laut Natuna", 105.0, 110.0, 2.0, 5.0, "Jalur Batam-Natuna-Kalimantan Barat dan kabel ke Laut China Selatan."),
```
```python
def test_preset_natuna():
    d = muat_data.muat_semua()
    natuna = next(k for k in skenario.AREA_PRESET if k.nama == "Laut Natuna")
    assert len(skenario.kabel_lewat_kotak(d, natuna)) >= 1
```
</details>

---

### Latihan 3 — Kabel terpanjang dan terbanyak landing station ⭐

Di tab *The map*, tambahkan dua kartu metrik: kabel terpanjang (nama + km) dan kabel dengan landing station terbanyak
di antara yang mendarat di Indonesia.

<details><summary>Petunjuk</summary>
<code>kabel_idn</code> sudah berisi kolom <code>panjang_km</code> dan <code>n_landing</code>. Gunakan <code>idxmax()</code>
lalu ambil barisnya dengan <code>loc</code>. Beberapa panjang bernilai NaN; <code>idxmax</code> mengabaikannya.
</details>

<details><summary>Kunci</summary>

```python
terpanjang = kabel_idn.loc[kabel_idn["panjang_km"].idxmax()]
terbanyak = kabel_idn.loc[kabel_idn["n_landing"].idxmax()]
a, b = st.columns(2)
a.metric("Kabel terpanjang", terpanjang["nama"], f"{angka(terpanjang['panjang_km'])} km")
b.metric("Landing station terbanyak", terbanyak["nama"], f"{terbanyak['n_landing']} titik")
```
</details>

---

### Latihan 4 — Putus dua area sekaligus ⭐⭐

Ubah skenario area laut agar pengguna bisa memilih **beberapa** area sekaligus (misalnya Selat Sunda dan Teluk Jakarta),
dan gambarkan semua kotaknya di peta.

<details><summary>Petunjuk</summary>
Ganti <code>st.selectbox</code> dengan <code>st.multiselect</code>; gabungkan himpunan dengan <code>|=</code>; simpan
daftar kotak, bukan satu kotak, lalu panggil <code>tambah_kotak</code> dalam perulangan.
</details>

<details><summary>Kunci</summary>

```python
pilih = st.multiselect("Area laut", [k.nama for k in AREA_PRESET], default=[AREA_PRESET[0].nama])
kotak_terpilih = [k for k in AREA_PRESET if k.nama in pilih]
for k in kotak_terpilih:
    putus |= skenario.kabel_lewat_kotak(data, k, hanya_aktif=not sertakan_rencana)
...
for k in kotak_terpilih:
    tambah_kotak(fig, k)
```
</details>

---

### Latihan 5 — Ekspor hasil simulasi ⭐⭐

Tambahkan tombol download CSV berisi tabel hasil simulasi (semua landing station dengan statusnya) di tab *Cut the cable*,
dengan nama file yang memuat jumlah kabel yang diputus, misalnya `simulasi_22_kabel.csv`.

<details><summary>Petunjuk</summary>
Lihat cara <code>st.download_button</code> dipakai di tab <i>Data & Sources</i>. DataFrame <code>hasil</code> sudah ada; ubah
ke bytes dengan <code>.to_csv(index=False).encode("utf-8")</code>.
</details>

<details><summary>Kunci</summary>

```python
st.download_button(
    "Download hasil simulasi (CSV)",
    hasil.to_csv(index=False).encode("utf-8"),
    f"simulasi_{len(putus)}_kabel.csv", "text/csv",
)
```
</details>

---

### Latihan 6 — Kabel paling kritis ⭐⭐⭐

Buat fungsi `kabel_paling_kritis(data, n=10)` di `src/jaringan.py` yang memutus **setiap kabel aktif satu per satu**,
mencatat berapa landing station yang berstatus *Gelap total* atau *Terputus dari dunia*, dan mengembalikan 10 kabel
dengan dampak terbesar. Tampilkan sebagai grafik batang di tab *Landing stations*. Tulis tesnya dengan jaringan mainan.

<details><summary>Petunjuk</summary>
Perulangan sederhana atas <code>kabel_aktif(data)["id"]</code>, panggil <code>simulasi(data, {id})</code>, hitung dengan
<code>ringkas_angka</code>. 61 simulasi × ±50 ms ≈ 3 detik; bungkus pemanggilannya di <code>app.py</code> dengan
<code>@st.cache_data</code> agar hanya dihitung sekali per nilai radius.
</details>

<details><summary>Kunci</summary>

```python
def kabel_paling_kritis(data: Data, n: int = 10, radius_darat_km: float = RADIUS_DARAT_KM) -> pd.DataFrame:
    baris = []
    for cid, nama in kabel_aktif(data)[["id", "nama"]].itertuples(index=False):
        r = ringkas_angka(simulasi(data, {cid}, radius_darat_km=radius_darat_km))
        baris.append({"id": cid, "nama": nama, "gelap": r["gelap"], "terputus": r["terputus"],
                      "dampak": r["gelap"] + r["terputus"] + r["darat"]})
    return pd.DataFrame(baris).sort_values("dampak", ascending=False).head(n)
```
Tes pada jaringan mainan: memutus `dom-2` harus memberi dampak 1 (Surabaya gelap), memutus `int-1` dampak 0.
</details>

---

### Latihan 7 — Pemutusan per segmen ⭐⭐⭐

Model saat ini menganggap kabel bercabang mati seluruhnya. Buat varian: untuk kabel dengan lebih dari dua landing
station, bangun sisi hanya antara stasiun yang **berurutan** menurut kolom `urutan` (rantai), bukan semua pasangan,
lalu bandingkan hasil skenario "Semua kabel ke Singapura" antara kedua model. Mana yang lebih masuk akal untuk
Palapa Ring? Mana untuk SeaMeWe-5?

<details><summary>Petunjuk</summary>
Tambahkan parameter <code>mode="clique" | "rantai"</code> pada <code>bangun_graf</code>. Untuk rantai,
<code>zip(simpul[:-1], simpul[1:])</code> menggantikan <code>combinations(simpul, 2)</code>. Perhatikan bahwa kolom
<code>urutan</code> hanya mengikuti urutan di sumber, yang belum tentu urutan geografis; itu bahan diskusi, bukan jawaban
tunggal.
</details>

<details><summary>Kunci</summary>

```python
pasangan = combinations(simpul, 2) if mode == "clique" else zip(simpul[:-1], simpul[1:])
for a, b in pasangan:
    ...
```
Dalam model rantai, memutus kabel tetap menghapus semua sisinya, tetapi stasiun di tengah rantai kini hanya terhubung
ke tetangganya, sehingga jumlah "pintu keluar" per komponen umumnya turun. Untuk kabel ring seperti Palapa Ring,
rantai lurus justru terlalu pesimistis; cincin seharusnya menutup kembali ke titik awal. Itulah mengapa data topologi
segmen yang sebenarnya sangat berharga dan tidak dipublikasikan gratis.
</details>
