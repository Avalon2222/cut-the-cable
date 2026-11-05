"""
app.py - Cut the Cable
======================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import library + konfigurasi halaman
  2. Muat data kabel, landing station, geometri (src/muat_data.py; snapshot di data/)
  3. Sidebar: lapisan peta, parameter model, learning mode
  4. Ringkasan angka
  5. Tab: peta -> simulasi kabel putus -> gateway dunia -> landing station -> data -> cara kerja

Logika yang bisa diuji ada di src/ (graf jaringan, skenario, wilayah); file ini hanya menyusun UI.
Setiap bagian diberi komentar "APA" dan "MENGAPA". Penjelasan istilah ada di docs/BELAJAR.md.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import jaringan, muat_data, skenario
from src.jaringan import PENJELASAN_STATUS, STATUS, WARNA_STATUS
from src.muat_data import LABEL_KATEGORI
from src.skenario import AREA_PRESET, Kotak

# ----------------------------------------------------------------------------
# 0. KONFIGURASI HALAMAN
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Cut the Cable", page_icon="✂️", layout="wide")

TEMPLATE = "plotly_dark"
WARNA_KATEGORI = {"internasional": "#22d3ee", "domestik": "#f59e0b", "transit": "#5b6b82"}
WARNA_RENCANA = "#a78bfa"
WARNA_PUTUS = "#ff2d55"
WARNA_LANDING = "#e6edf3"
WARNA_DC = "#ff6b9d"
PUSAT = {"lat": -2.3, "lon": 117.5}
DISCLAIMER = (
    "ℹ️ Data kabel dan landing station berasal dari **Submarine Cable Map (TeleGeography)**, sumber publik yang "
    "dirangkum dari pengumuman operator. Simulasi \"kabel putus\" adalah model sederhana berbasis konektivitas, bukan "
    "kapasitas atau lalu lintas sebenarnya. Proyek ini edukatif dan portofolio pribadi, bukan dokumen resmi."
)


def rapikan(fig: go.Figure, tinggi: int = 420) -> go.Figure:
    """Gaya seragam untuk semua grafik Plotly: latar gelap, grid tipis, legenda di atas."""
    fig.update_layout(
        template=TEMPLATE,
        height=tinggi,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=70, b=10),
        title=dict(y=0.98, yanchor="top", x=0, xanchor="left", font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#243044", zeroline=False)
    return fig


def angka(n) -> str:
    """1234 -> '1.234' (format Indonesia)."""
    return f"{int(n):,}".replace(",", ".")


# ----------------------------------------------------------------------------
# 1. MUAT DATA (snapshot di data/, tidak perlu internet)
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Memuat data kabel...")
def muat():
    return muat_data.muat_semua(), muat_data.muat_data_center()


data, df_dc = muat()
kabel_idn = data.kabel[data.kabel["kategori"].isin(["domestik", "internasional"])]
kabel_aktif = kabel_idn[kabel_idn["status"] == "aktif"]
nama_kabel = data.kabel.set_index("id")["nama"].to_dict()

# APA: hitung jumlah kabel aktif per landing station sekali di awal, dipakai di banyak tempat.
# MENGAPA: tabel relasi berbentuk panjang (satu baris per pasangan kabel-landing), jadi perlu diagregasi.
rel_aktif = data.relasi[data.relasi["id_kabel"].isin(kabel_aktif["id"])]
per_landing = (
    rel_aktif.merge(kabel_aktif[["id", "nama", "kategori"]], left_on="id_kabel", right_on="id")
    .groupby("id_landing")
    .agg(n_kabel=("id_kabel", "nunique"),
         n_internasional=("kategori", lambda s: int((s == "internasional").sum())),
         daftar_kabel=("nama", lambda s: "; ".join(sorted(s))))
)
landing = data.landing.join(per_landing, on="id")
landing[["n_kabel", "n_internasional"]] = landing[["n_kabel", "n_internasional"]].fillna(0).astype(int)
landing["daftar_kabel"] = landing["daftar_kabel"].fillna("(hanya kabel rencana)")
landing_idn = landing[landing["negara"] == "Indonesia"].copy()
landing_idn_aktif = landing_idn[landing_idn["n_kabel"] > 0]

gateway = jaringan.gateway_luar_negeri(data)
persen_sg = int(gateway.set_index("negara")["persen"].get("Singapore", 0))
n_int_aktif = int((kabel_aktif["kategori"] == "internasional").sum())

# ----------------------------------------------------------------------------
# 2. SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("✂️ Cut the Cable")
    st.caption("Peta kabel internet bawah laut Indonesia, dan apa yang terjadi kalau salah satunya putus.")

    st.subheader("Map layers")
    tampil_int = st.checkbox("Kabel internasional", value=True)
    tampil_dom = st.checkbox("Kabel domestik", value=True)
    tampil_transit = st.checkbox("Kabel kawasan (lewat, tidak mendarat)", value=False)
    tampil_rencana = st.checkbox("Kabel rencana / dalam pembangunan", value=False)
    tampil_landing = st.checkbox("Landing station", value=True)
    tampil_dc = st.checkbox("Data center besar", value=False,
                            help="Lokasi 27 data center besar dari proyek dc-impact-dashboard; relevan karena data center bergantung pada kabel ini.")

    st.subheader("Model")
    radius_darat = st.slider(
        "Radius sambungan darat (km)", 0, 300, int(jaringan.RADIUS_DARAT_KM), step=10,
        help="Dua landing station senegara yang lebih dekat dari jarak ini dianggap tersambung lewat serat optik darat "
             "(misalnya Jakarta-Ancol-Tanjung Pakis atau Batam-Nongsa). 0 = tanpa sambungan darat.",
    )
    sertakan_rencana = st.toggle("Hitung juga kabel rencana", value=False,
                                 help="Masukkan kabel yang belum beroperasi ke dalam graf, untuk melihat masa depan.")

    mode_belajar = st.toggle("🎓 Learning mode", value=False, help="Tampilkan penjelasan, rumus, dan potongan kode di setiap bagian.")

    st.subheader("Data")
    st.caption(
        f"Snapshot Submarine Cable Map: **{data.meta.get('dibangun', '-')}**  \n"
        f"{data.meta.get('n_kabel_dunia', '-')} kabel di dunia, {len(kabel_idn)} mendarat di Indonesia."
    )
    st.caption("Perbarui dengan `python scripts/bangun_data.py`. Lihat tab *Data & Sources*.")

kategori_tampil = [k for k, aktif in (("internasional", tampil_int), ("domestik", tampil_dom), ("transit", tampil_transit)) if aktif]

# ----------------------------------------------------------------------------
# 3. JUDUL + ANGKA RINGKASAN
# ----------------------------------------------------------------------------
st.title("✂️ Cut the Cable")
st.markdown(
    "**Cut one cable. Watch who goes dark.** Peta kabel internet bawah laut yang menghubungkan Indonesia ke dunia dan "
    "antar pulau, lengkap dengan simulasi: kalau satu kabel, satu landing station, atau satu area laut bermasalah, "
    "daerah mana yang kehilangan jalur?"
)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Kabel aktif di Indonesia", angka(len(kabel_aktif)),
          help="Domestik + internasional yang sudah beroperasi; kabel rencana tidak dihitung")
k2.metric("…internasional", angka(n_int_aktif), help="Punya landing station di Indonesia dan di luar negeri")
k3.metric("Landing station", angka(len(landing_idn_aktif)), help="Yang disinggahi minimal satu kabel aktif")
k4.metric("Lewat Singapura", f"{persen_sg}%",
          help="Persentase kabel internasional aktif yang salah satu landing station-nya di Singapura")
k5.metric("Stasiun 1 kabel saja", angka((landing_idn_aktif["n_kabel"] == 1).sum()),
          help="Tanpa cadangan: satu kabel putus, stasiun itu gelap")
st.caption(DISCLAIMER)

# ----------------------------------------------------------------------------
# 4. FUNGSI PETA
# ----------------------------------------------------------------------------
GEO = {f["properties"]["id"]: f for f in data.geo["features"]}


def garis_kabel(ids: list[str]) -> tuple[list, list, list]:
    """Gabungkan geometri beberapa kabel jadi satu deret lon/lat (dipisah None) + teks hover per titik.
    MENGAPA: satu trace per kategori jauh lebih ringan daripada 118 trace terpisah."""
    lon, lat, teks = [], [], []
    for cid in ids:
        f = GEO.get(cid)
        if f is None:
            continue
        nama = f["properties"]["nama"]
        for garis in f["geometry"]["coordinates"]:
            for x, y in garis:
                lon.append(x)
                lat.append(y)
                teks.append(nama)
            lon.append(None)
            lat.append(None)
            teks.append(None)
    return lon, lat, teks


def tambah_garis(fig: go.Figure, ids: list[str], nama: str, warna: str, lebar: float = 1.6, opasitas: float = 0.9,
                 tampil_legenda: bool = True) -> None:
    lon, lat, teks = garis_kabel(ids)
    if not lon:
        return
    fig.add_trace(go.Scattermap(
        lon=lon, lat=lat, mode="lines", name=nama, line=dict(color=warna, width=lebar), opacity=opasitas,
        hovertext=teks, hoverinfo="text", showlegend=tampil_legenda,
    ))


def tambah_landing(fig: go.Figure, df: pd.DataFrame, warna, nama: str, ukuran=None, teks=None) -> None:
    if len(df) == 0:
        return
    if teks is None:
        teks = [
            f"<b>{r.nama}</b><br>{r.n_kabel} kabel aktif ({r.n_internasional} internasional)<br>"
            f"<span style='font-size:11px'>{r.daftar_kabel}</span>"
            for r in df.itertuples()
        ]
    fig.add_trace(go.Scattermap(
        lon=df["lon"], lat=df["lat"], mode="markers", name=nama,
        marker=dict(size=ukuran if ukuran is not None else 7, color=warna, opacity=0.95),
        hovertext=teks, hoverinfo="text",
    ))


def tambah_kotak(fig: go.Figure, kotak: Kotak) -> None:
    lon = [kotak.lon_min, kotak.lon_max, kotak.lon_max, kotak.lon_min, kotak.lon_min]
    lat = [kotak.lat_min, kotak.lat_min, kotak.lat_max, kotak.lat_max, kotak.lat_min]
    fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", name=f"Area: {kotak.nama}",
                                line=dict(color=WARNA_PUTUS, width=2), hoverinfo="skip"))


def peta_dasar(tinggi: int = 600, zoom: float = 3.6) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        map=dict(style="carto-darkmatter", center=PUSAT, zoom=zoom),
        height=tinggi, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=0.01, x=0.01, title=None, bgcolor="rgba(7,11,20,0.75)", font=dict(size=12)),
        hoverlabel=dict(bgcolor="#111a2b", font=dict(color="#e6edf3")),
    )
    return fig


def ids_kategori(kategori: str, status: str) -> list[str]:
    k = data.kabel[(data.kabel["kategori"] == kategori) & (data.kabel["status"] == status)]
    return k["id"].tolist()


def peta_jaringan(sorot: str | None = None) -> go.Figure:
    """Peta utama: kabel per kategori (warna) + landing station (ukuran = jumlah kabel) + opsi data center."""
    fig = peta_dasar()
    for kat in ["transit", "domestik", "internasional"]:
        if kat not in kategori_tampil:
            continue
        lebar = 1.2 if kat == "transit" else 1.8
        tambah_garis(fig, ids_kategori(kat, "aktif"), LABEL_KATEGORI[kat].split(" (")[0], WARNA_KATEGORI[kat], lebar,
                     0.55 if kat == "transit" else 0.9)
        if tampil_rencana:
            tambah_garis(fig, ids_kategori(kat, "rencana"), f"Rencana ({kat})", WARNA_RENCANA, 1.4, 0.7)
    if tampil_landing:
        df = landing[landing["n_kabel"] > 0] if not tampil_rencana else landing
        ukuran = (5 + 2.2 * df["n_kabel"].clip(upper=14)).tolist()
        tambah_landing(fig, df, WARNA_LANDING, "Landing station (ukuran = jumlah kabel)", ukuran)
    if tampil_dc:
        teks = [f"<b>{r.nama}</b><br>{r.operator} · {r.kabupaten_kota}<br>{r.kapasitas_it_mw} MW · {r.status}" for r in df_dc.itertuples()]
        tambah_landing(fig, df_dc, WARNA_DC, "Data center besar", 9, teks)
    if sorot:
        tambah_garis(fig, [sorot], f"Disorot: {nama_kabel.get(sorot, sorot)}", "#ffffff", 4.5, 1.0)
    return fig


# ----------------------------------------------------------------------------
# 5. TAB
# ----------------------------------------------------------------------------
tab_peta, tab_putus, tab_gateway, tab_landing, tab_data, tab_cara = st.tabs(
    ["🗺️ The map", "✂️ Cut the cable", "🌏 Gateways", "🏝️ Landing stations", "📋 Data & Sources", "🧭 How it works"]
)

# ---------------------------------------------------------------- 5a. PETA
with tab_peta:
    c1, c2 = st.columns([3, 1])
    c1.subheader("Jaringan kabel bawah laut Indonesia")
    pilihan_sorot = ["(tidak ada)"] + kabel_idn.sort_values("nama")["nama"].tolist()
    nama_sorot = c2.selectbox("Sorot satu kabel", pilihan_sorot, index=0, label_visibility="collapsed")
    id_sorot = None if nama_sorot == "(tidak ada)" else kabel_idn.loc[kabel_idn["nama"] == nama_sorot, "id"].iloc[0]
    st.plotly_chart(peta_jaringan(id_sorot), width="stretch", key="peta_utama")

    if id_sorot:
        k = data.kabel.set_index("id").loc[id_sorot]
        lp = data.landing_dari_kabel(id_sorot)
        nama_lp = landing.set_index("id").loc[lp, "nama"].tolist()
        a, b, c, d = st.columns(4)
        a.metric("Status", "Aktif" if k["status"] == "aktif" else "Rencana")
        b.metric("Siap pakai (RFS)", str(k["rfs"]) if pd.notna(k["rfs"]) else "-")
        c.metric("Panjang", f"{angka(k['panjang_km'])} km" if pd.notna(k["panjang_km"]) else "-")
        d.metric("Landing station", len(lp))
        st.markdown(
            f"**Kategori:** {LABEL_KATEGORI[k['kategori']]}  \n"
            f"**Pemilik:** {k['pemilik'] or '-'}  \n**Pemasok:** {k['pemasok'] or '-'}  \n"
            f"**Mendarat di:** {', '.join(nama_lp)}  \n[Halaman kabel di Submarine Cable Map]({k['url']})"
        )

    st.info(
        "💡 **Cara membaca peta.** Garis **biru** adalah kabel internasional (mendarat di Indonesia dan di negara lain), "
        "garis **oranye** kabel domestik antar pulau, garis **abu-abu** (opsional) kabel kawasan yang hanya lewat. "
        "Titik putih adalah landing station: tempat kabel naik ke darat; semakin besar titiknya, semakin banyak kabel yang "
        "mendarat. Perhatikan betapa padatnya Batam-Singapura dan Teluk Jakarta dibanding Indonesia timur."
    )

    with st.expander("📜 Daftar kabel yang mendarat di Indonesia", expanded=False):
        tabel = kabel_idn[["nama", "kategori", "status", "tahun_rfs", "panjang_km", "n_landing", "n_landing_indonesia", "negara", "pemilik"]].copy()
        tabel["negara"] = tabel["negara"].str.replace("|", ", ", regex=False)
        tabel = tabel.rename(columns={"nama": "Kabel", "kategori": "Kategori", "status": "Status", "tahun_rfs": "RFS",
                                      "panjang_km": "Panjang (km)", "n_landing": "Landing", "n_landing_indonesia": "…di Indonesia",
                                      "negara": "Negara", "pemilik": "Pemilik"})
        st.dataframe(tabel.sort_values(["Kategori", "Status", "Kabel"]), hide_index=True, height=420,
                     column_config={"Panjang (km)": st.column_config.NumberColumn(format="%d")})

    if mode_belajar:
        with st.expander("🎓 Dari GeoJSON ke garis di peta"):
            st.markdown(
                """
Geometri setiap kabel disimpan sebagai **MultiLineString** GeoJSON: daftar garis, setiap garis daftar titik `[lon, lat]`.
Plotly bisa menggambar banyak garis dalam satu *trace* kalau deret koordinatnya dipisah `None`:

```python
lon, lat, teks = [], [], []
for garis in fitur["geometry"]["coordinates"]:
    for x, y in garis:
        lon.append(x); lat.append(y); teks.append(nama_kabel)
    lon.append(None); lat.append(None); teks.append(None)   # "angkat pena"
fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", hovertext=teks))
```

Satu trace per kategori (bukan satu per kabel) membuat peta ringan dan legendanya tetap rapi. Kode: fungsi
`garis_kabel` dan `tambah_garis` di `app.py`. Data dibangun oleh `scripts/bangun_data.py` dari API publik
Submarine Cable Map, lalu disaring: kabel yang mendarat di Indonesia, plus kabel yang hanya melintas kotak
perairan Indonesia (`src/wilayah.py: KOTAK_INDONESIA`).
"""
            )

# ---------------------------------------------------------------- 5b. SIMULASI
with tab_putus:
    st.subheader("Kalau kabel ini putus, siapa yang gelap?")
    st.caption(
        "Pilih cara memutus, lalu lihat landing station mana yang kehilangan jalur. Model: kabel yang diputus dianggap mati "
        "seluruhnya; dua landing station senegara dalam radius darat dianggap tersambung lewat darat (atur di sidebar)."
    )
    cara = st.radio(
        "Cara memutus",
        ["Pilih kabel sendiri", "Satu landing station mati", "Semua kabel ke satu negara", "Gangguan di satu area laut"],
        horizontal=True,
    )
    kabel_pilihan = kabel_idn if sertakan_rencana else kabel_aktif
    putus: set[str] = set()
    kotak_aktif: Kotak | None = None

    if cara == "Pilih kabel sendiri":
        # APA: default = kabel internasional terbesar yang mendarat di Jakarta, supaya ada contoh saat halaman dibuka.
        default = [n for n in ["Indonesia Global Gateway (IGG) System", "SeaMeWe-5"] if n in kabel_pilihan["nama"].values]
        nama_terpilih = st.multiselect("Kabel yang diputus", kabel_pilihan.sort_values("nama")["nama"].tolist(), default=default)
        putus = set(kabel_pilihan.loc[kabel_pilihan["nama"].isin(nama_terpilih), "id"])
    elif cara == "Satu landing station mati":
        urut = landing_idn_aktif.sort_values(["n_kabel", "nama"], ascending=[False, True])
        label = {r.id: f"{r.kota} ({r.n_kabel} kabel)" for r in urut.itertuples()}
        id_lp = st.selectbox("Landing station", list(label), format_func=label.get)
        putus = skenario.kabel_di_landing(data, id_lp, hanya_aktif=not sertakan_rencana)
        st.caption("Semua kabel yang mendarat di stasiun ini dianggap mati: kebakaran, banjir, pemadaman listrik panjang, atau sabotase di satu titik.")
    elif cara == "Semua kabel ke satu negara":
        negara = st.selectbox("Negara tujuan", gateway["negara"].tolist())
        putus = skenario.kabel_ke_negara(data, negara, hanya_aktif=not sertakan_rencana)
        st.caption("Skenario geopolitik: seluruh kabel internasional yang mendarat di negara itu tidak bisa dipakai.")
    else:
        pilih = st.selectbox("Area laut", [k.nama for k in AREA_PRESET])
        kotak_aktif = next(k for k in AREA_PRESET if k.nama == pilih)
        st.caption(f"📍 {kotak_aktif.keterangan} Semua kabel yang garisnya melewati kotak ini dianggap putus "
                   "(gempa, longsor bawah laut, jangkar kapal, atau sabotase).")
        putus = skenario.kabel_lewat_kotak(data, kotak_aktif, hanya_aktif=not sertakan_rencana)

    if not putus:
        st.warning("Belum ada kabel yang dipilih. Pilih minimal satu kabel untuk menjalankan simulasi.")
    else:
        hasil = jaringan.simulasi(data, putus, sertakan_rencana=sertakan_rencana, radius_darat_km=radius_darat)
        ringkas = jaringan.ringkas_angka(hasil)
        hasil_aktif = hasil[hasil["n_kabel_awal"] > 0]

        st.markdown("**Kabel yang diputus:** " + " · ".join(f"`{nama_kabel.get(i, i)}`" for i in sorted(putus, key=lambda i: nama_kabel.get(i, i))))
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Kabel putus", len(putus))
        m2.metric("Gelap total", ringkas["gelap"], help=PENJELASAN_STATUS["Gelap total"])
        m3.metric("Terputus dari dunia", ringkas["terputus"], help=PENJELASAN_STATUS["Terputus dari dunia"])
        m4.metric("Hidup lewat darat", ringkas["darat"], help=PENJELASAN_STATUS["Hidup lewat darat"])
        m5.metric("Rentan", ringkas["rentan"], help=PENJELASAN_STATUS["Rentan (1 kabel tersisa)"])
        m6.metric("Pintu keluar", f"{ringkas['pintu_sisa']} / {ringkas['pintu_awal']}",
                  delta=ringkas["pintu_sisa"] - ringkas["pintu_awal"],
                  help="Jumlah kabel internasional berbeda yang masih bisa dijangkau dari landing station paling terhubung")

        # Peta dampak: kabel putus merah, kabel lain redup, landing station berwarna status
        fig = peta_dasar(tinggi=620)
        sisa_ids = [i for i in (kabel_pilihan["id"]) if i not in putus]
        tambah_garis(fig, sisa_ids, "Kabel lain", "#3b4a63", 1.2, 0.8)
        tambah_garis(fig, sorted(putus), "Kabel putus", WARNA_PUTUS, 3.0, 1.0)
        if kotak_aktif:
            tambah_kotak(fig, kotak_aktif)
        for status in reversed(STATUS):
            sub = hasil_aktif[hasil_aktif["status"] == status]
            if len(sub) == 0:
                continue
            teks = [
                f"<b>{r.nama}</b><br>{r.status}<br>Kabel: {r.n_kabel_awal} → {r.n_kabel_sisa}"
                f"<br>Pintu internasional terjangkau: {r.pintu_awal} → {r.pintu_sisa}"
                + (f"<br><span style='font-size:11px'>Hilang: {r.kabel_hilang}</span>" if r.kabel_hilang else "")
                for r in sub.itertuples()
            ]
            ukuran = 7 if status == "Aman" else 12
            tambah_landing(fig, sub, WARNA_STATUS[status], status, ukuran, teks)
        st.plotly_chart(fig, width="stretch", key="peta_dampak")

        kiri, kanan = st.columns([1, 1])
        tabel_wil = jaringan.ringkas_wilayah(hasil)
        panjang = tabel_wil[STATUS].reset_index().melt(id_vars="wilayah", var_name="status", value_name="jumlah")
        panjang = panjang[panjang["jumlah"] > 0]
        fig_w = px.bar(
            panjang, x="jumlah", y="wilayah", color="status", orientation="h", color_discrete_map=WARNA_STATUS,
            category_orders={"status": STATUS, "wilayah": tabel_wil.index.tolist()},
            title="Landing station per wilayah, menurut status", labels={"jumlah": "Landing station", "wilayah": ""},
        )
        fig_w = rapikan(fig_w, 420)
        fig_w.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.12, x=0), margin=dict(t=50, b=10))
        kiri.plotly_chart(fig_w, width="stretch", key="bar_wilayah")

        terdampak = hasil_aktif[hasil_aktif["status"] != "Aman"][
            ["kota", "wilayah", "status", "n_kabel_awal", "n_kabel_sisa", "pintu_awal", "pintu_sisa", "kabel_hilang"]
        ].rename(columns={"kota": "Landing station", "wilayah": "Wilayah", "status": "Status", "n_kabel_awal": "Kabel awal",
                          "n_kabel_sisa": "Kabel sisa", "pintu_awal": "Pintu awal", "pintu_sisa": "Pintu sisa", "kabel_hilang": "Kabel hilang"})
        kanan.markdown(f"**{len(terdampak)} landing station terdampak** dari {ringkas['n_landing']}")
        kanan.dataframe(terdampak, hide_index=True, height=360)

        with st.expander("ℹ️ Arti setiap status"):
            for s in STATUS:
                st.markdown(f"<span style='color:{WARNA_STATUS[s]}'>●</span> **{s}**: {PENJELASAN_STATUS[s]}", unsafe_allow_html=True)
            st.markdown(
                "**Pintu keluar internasional** = jumlah kabel internasional berbeda yang bisa dicapai dari suatu landing station "
                "lewat rantai kabel/darat apa pun. Angka di kartu adalah nilai tertinggi di antara semua landing station."
            )

        if mode_belajar:
            with st.expander("🎓 Jaringan kabel sebagai graf"):
                st.markdown(
                    """
Simulasinya adalah soal **graf**: simpul = landing station, sisi = kabel. Satu kabel dengan *n* landing station
menjadi sisi di antara semua pasangannya (kabel punya cabang, dan data publik tidak menyimpan urutan segmen).
Memutus kabel = menghapus semua sisi berlabel kabel itu, lalu bertanya: komponen terhubung mana yang masih
memuat simpul luar negeri?

```python
G = nx.Graph()
for id_kabel, simpul in landing_per_kabel.items():      # kabel aktif yang tidak diputus
    for a, b in combinations(simpul, 2):
        G.add_edge(a, b)
for komp in nx.connected_components(G):
    ada_asing = any(negara[n] != "Indonesia" for n in komp)
```

Sisi "darat" ditambahkan untuk pasangan landing station senegara yang berjarak kurang dari radius (haversine),
karena Jakarta, Ancol, dan Tanjung Pakis jelas tersambung lewat serat optik darat meski datanya tidak mencatat itu.
Coba geser radius ke 0 di sidebar dan ulangi skenario "Semua kabel ke Singapura": tanpa sisi darat, hampir seluruh
Indonesia timur terlihat terputus; dengan sisi darat 60 km, hasilnya jauh lebih masuk akal. Itulah bedanya model dan
kenyataan, dan mengapa setiap asumsi harus ditulis.

Kode: `src/jaringan.py` (`bangun_graf`, `simulasi`, `tentukan_status`), diuji di `tests/test_jaringan.py` dengan
jaringan mainan sembilan simpul.
"""
                )
            with st.expander("🎓 Memilih kabel lewat kotak di laut"):
                st.markdown(
                    """
Untuk skenario area, setiap ruas garis kabel diuji terhadap persegi dengan algoritma **Liang-Barsky**: parameter
*t* di sepanjang ruas dipotong oleh empat sisi kotak; kalau selang *t* yang tersisa tidak kosong, ruas itu melintasi
kotak. Mengecek titik sudut saja tidak cukup, karena ruas kabel di laut lepas bisa ratusan kilometer panjangnya.

```python
for p, q in ((-dx, x1 - lon_min), (dx, lon_max - x1), (-dy, y1 - lat_min), (dy, lat_max - y1)):
    t = q / p
    t0, t1 = (max(t0, t), t1) if p < 0 else (t0, min(t1, t))
return t0 <= t1
```
Kode: `src/skenario.py` (`segmen_memotong_kotak`, `kabel_lewat_kotak`), diuji di `tests/test_skenario.py`.
"""
                )

# ---------------------------------------------------------------- 5c. GATEWAY
with tab_gateway:
    st.subheader("Ke mana kabel internasional Indonesia pergi?")
    st.caption("Satu kabel bisa mendarat di beberapa negara sekaligus, sehingga total persen melebihi 100%.")
    gateway_df = jaringan.gateway_luar_negeri(data, sertakan_rencana=sertakan_rencana)
    c1, c2 = st.columns([1, 1])
    fig = px.bar(
        gateway_df.head(12), x="n_kabel", y="negara", orientation="h", text="persen",
        title=f"Jumlah kabel internasional per negara tujuan ({'aktif + rencana' if sertakan_rencana else 'aktif'})",
        labels={"n_kabel": "Kabel", "negara": ""}, hover_data={"kabel": True, "persen": False},
        color="n_kabel", color_continuous_scale=["#1e3a5f", "#22d3ee"],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    fig.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
    c1.plotly_chart(rapikan(fig, 460), width="stretch", key="bar_gateway")

    # Sankey: landing station Indonesia -> negara tujuan
    kabel_int = kabel_idn[(kabel_idn["kategori"] == "internasional") & (kabel_idn["status"].isin(["aktif", "rencana"] if sertakan_rencana else ["aktif"]))]
    rel = data.relasi[data.relasi["id_kabel"].isin(kabel_int["id"])].merge(
        data.landing[["id", "kota", "negara"]], left_on="id_landing", right_on="id")
    sisi_idn = rel[rel["negara"] == "Indonesia"][["id_kabel", "kota"]]
    sisi_asing = rel[rel["negara"] != "Indonesia"][["id_kabel", "negara"]].drop_duplicates()
    alur = sisi_idn.merge(sisi_asing, on="id_kabel").groupby(["kota", "negara"]).size().reset_index(name="n")
    simpul = alur["kota"].unique().tolist() + alur["negara"].unique().tolist()
    idx = {n: i for i, n in enumerate(simpul)}
    fig_s = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=simpul, pad=12, thickness=14, color=["#f59e0b"] * alur["kota"].nunique() + ["#22d3ee"] * alur["negara"].nunique(),
                  line=dict(width=0)),
        link=dict(source=alur["kota"].map(idx), target=alur["negara"].map(idx), value=alur["n"],
                  color="rgba(34,211,238,0.25)",
                  hovertemplate="%{source.label} → %{target.label}: %{value} kabel<extra></extra>"),
    ))
    fig_s.update_layout(title="Landing station Indonesia → negara tujuan (lebar = jumlah kabel)")
    c2.plotly_chart(rapikan(fig_s, 460), width="stretch", key="sankey")

    st.info(
        f"💡 **Singapura adalah pintu utama.** {persen_sg}% kabel internasional aktif Indonesia mendarat di Singapura, "
        "karena di sanalah pusat pertukaran data Asia Tenggara dan ujung kabel lintas benua. Jalur lain yang tidak lewat "
        "Singapura: ke Malaysia dari Sumatra dan Batam, serta ke Guam/Amerika lewat Manado (SEA-US) dan Jakarta (Bifrost, Echo, Apricot) "
        "yang juga mampir di Singapura. Coba skenario \"Semua kabel ke satu negara → Singapore\" di tab sebelumnya."
    )

    st.subheader("Kapan kabel-kabel ini dibangun?")
    per_tahun = jaringan.kabel_per_tahun(data)
    per_tahun["kelompok"] = per_tahun.apply(lambda r: f"{r['kategori']} ({r['status']})", axis=1)
    warna_kelompok = {"internasional (aktif)": WARNA_KATEGORI["internasional"], "domestik (aktif)": WARNA_KATEGORI["domestik"],
                      "internasional (rencana)": WARNA_RENCANA, "domestik (rencana)": "#c4b5fd"}
    fig_t = px.bar(per_tahun, x="tahun_rfs", y="jumlah", color="kelompok", color_discrete_map=warna_kelompok,
                   title="Jumlah kabel menurut tahun siap pakai (RFS)", labels={"tahun_rfs": "Tahun", "jumlah": "Kabel", "kelompok": ""})
    fig_t.update_layout(bargap=0.15)
    st.plotly_chart(rapikan(fig_t, 360), width="stretch", key="bar_tahun")
    st.caption("Gelombang 2018-2019 adalah Palapa Ring (barat, tengah, timur) yang menyambungkan Indonesia timur; "
               "2025-2029 diisi kabel trans-Pasifik baru (Bifrost, Echo, Apricot, Hawaiki Nui, APX West) yang mendarat di Jakarta, Batam, dan Manado.")

    if mode_belajar:
        with st.expander("🎓 Membaca sankey dan menghitung dependensi"):
            st.markdown(
                """
Persentase per negara dihitung dari tabel relasi yang berbentuk panjang:

```python
rel = relasi[relasi.id_kabel.isin(kabel_internasional)]
rel["negara"] = rel.id_landing.map(negara_landing)
asing = rel[rel.negara != "Indonesia"].drop_duplicates(["id_kabel", "negara"])
per_negara = asing.groupby("negara").id_kabel.nunique()
persen = 100 * per_negara / len(kabel_internasional)
```

`drop_duplicates` penting: SeaMeWe-5 mendarat di dua kota Malaysia tetapi tetap dihitung satu kabel untuk Malaysia.
Sankey dibuat dari pasangan (kota Indonesia, negara tujuan) per kabel; lebar pita = jumlah kabel.
Kode: `jaringan.gateway_luar_negeri` dan bagian 5c di `app.py`.
"""
            )

# ---------------------------------------------------------------- 5d. LANDING STATION
with tab_landing:
    st.subheader("Siapa yang punya cadangan, siapa yang tidak?")
    per_wil = (
        landing_idn_aktif.groupby("wilayah")
        .agg(landing=("id", "count"), kabel_rata=("n_kabel", "mean"),
             satu_kabel=("n_kabel", lambda s: int((s == 1).sum())),
             internasional=("n_internasional", lambda s: int((s > 0).sum())))
        .reset_index()
    )
    per_wil["persen_satu_kabel"] = (100 * per_wil["satu_kabel"] / per_wil["landing"]).round(0).astype(int)
    per_wil = per_wil.sort_values("persen_satu_kabel", ascending=False)
    c1, c2 = st.columns([1, 1])
    fig = px.bar(
        per_wil, x="landing", y="wilayah", orientation="h", text="persen_satu_kabel",
        title="Landing station per wilayah (angka = % yang hanya punya 1 kabel)",
        labels={"landing": "Landing station", "wilayah": ""}, color="persen_satu_kabel",
        color_continuous_scale=["#3fd0a4", "#ffd23f", "#ff2d55"], range_color=(0, 100),
        hover_data={"satu_kabel": True, "internasional": True, "kabel_rata": ":.1f"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    fig.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
    c1.plotly_chart(rapikan(fig, 400), width="stretch", key="bar_landing_wilayah")

    fig_h = px.histogram(landing_idn_aktif, x="n_kabel", nbins=14, title="Sebaran jumlah kabel per landing station",
                         labels={"n_kabel": "Jumlah kabel aktif"}, color_discrete_sequence=[WARNA_KATEGORI["internasional"]])
    fig_h.update_layout(yaxis_title="Landing station", bargap=0.1)
    c2.plotly_chart(rapikan(fig_h, 400), width="stretch", key="hist_landing")

    teratas = landing_idn_aktif.sort_values("n_kabel", ascending=False).head(3)
    st.info(
        "💡 **Yang terbaca dari data.** "
        + "; ".join(f"**{r.kota}** {r.n_kabel} kabel" for r in teratas.itertuples())
        + f". Sementara itu **{int((landing_idn_aktif['n_kabel'] == 1).sum())} dari {len(landing_idn_aktif)}** landing station "
        "hanya disinggahi satu kabel; kebanyakan di Indonesia timur dan pulau-pulau kecil, tempat satu kabel adalah satu-satunya "
        "jalan keluar (selain satelit dan radio). Di model ini stasiun semacam itu langsung \"gelap total\" bila kabelnya putus, "
        "kecuali ada landing station lain dalam radius darat."
    )

    tabel = landing_idn.sort_values(["n_kabel", "nama"], ascending=[False, True])[
        ["kota", "wilayah", "n_kabel", "n_internasional", "daftar_kabel", "lat", "lon"]
    ].rename(columns={"kota": "Landing station", "wilayah": "Wilayah", "n_kabel": "Kabel aktif", "n_internasional": "…internasional",
                      "daftar_kabel": "Kabel", "lat": "Lat", "lon": "Lon"})
    st.dataframe(tabel, hide_index=True, height=420,
                 column_config={"Lat": st.column_config.NumberColumn(format="%.2f"), "Lon": st.column_config.NumberColumn(format="%.2f")})

    if mode_belajar:
        with st.expander("🎓 Dari koordinat ke wilayah"):
            st.markdown(
                """
Submarine Cable Map hanya memberi nama kota dan koordinat, tanpa provinsi. Supaya hasil bisa dikelompokkan, setiap
titik dipetakan ke tujuh wilayah besar dengan aturan kotak lintang-bujur yang diperiksa berurutan (Papua dulu, lalu
Maluku, dan seterusnya) karena kotaknya saling tumpang tindih di tepinya:

```python
if lon >= 135.0 or (lon >= 130.3 and lat >= -4.7):   return "Papua"
if (lon >= 125.5 and -9.0 < lat < 2.5) or (lon >= 124.3 and -3.5 < lat < 0.0): return "Maluku"
if lat < -7.8 and lon >= 114.45:                      return "Bali & Nusa Tenggara"
...
```
Aturan sekasar ini cukup untuk 146 titik yang ada dan diuji dengan 38 kota di `tests/test_wilayah.py`. Kalau suatu
hari ada titik yang salah wilayah, tambahkan kota itu ke daftar uji dulu, baru perbaiki aturannya: itu cara kerja
*test-driven* yang paling sederhana.
"""
            )

# ---------------------------------------------------------------- 5e. DATA & SOURCES
with tab_data:
    st.subheader("Sumber data dan keterbatasan")
    st.markdown(
        f"""
| Data | Sumber | Keterangan |
|---|---|---|
| Daftar kabel, landing station, pemilik, panjang, tahun RFS, geometri | [Submarine Cable Map](https://www.submarinecablemap.com) oleh TeleGeography, API publik `api/v3` | Snapshot **{data.meta.get('dibangun', '-')}**: {data.meta.get('n_kabel_dunia')} kabel di dunia → {len(kabel_idn)} mendarat di Indonesia ({int((kabel_idn['status']=='aktif').sum())} aktif, {int((kabel_idn['status']=='rencana').sum())} rencana) + {int((data.kabel['kategori']=='transit').sum())} kabel kawasan. Lisensi CC BY-NC-SA 3.0, dipakai di sini untuk tujuan edukasi non-komersial dengan atribusi |
| Pembagian wilayah | `src/wilayah.py` | Aturan kotak lintang-bujur buatan sendiri, bukan batas administratif |
| Area laut untuk skenario | `src/skenario.py` | Delapan kotak kasar (Selat Sunda, Batam-Singapura, Selat Malaka, Teluk Jakarta, Selat Lombok, Selat Makassar, Laut Sulawesi, Laut Banda) |
| Lokasi data center | Proyek [dc-impact-dashboard](https://github.com/Avalon2222/dc-impact-dashboard) | 27 data center besar, hanya lapisan peta opsional |

**Yang tidak ada di data dan tidak dimodelkan**

- **Kapasitas** (Tbps) dan lalu lintas sebenarnya. Dua kabel tua dan satu kabel baru dihitung sama-sama "satu kabel", padahal kapasitasnya bisa beda puluhan kali.
- **Topologi segmen.** Kabel dengan cabang (misalnya SeaMeWe-5 atau Palapa Ring) diperlakukan sebagai satu kesatuan: putus di mana pun, seluruh kabel dianggap mati.
- **Jaringan darat** di dalam pulau dan lintas batas (Kalimantan-Sarawak, Papua-PNG), kecuali pendekatan radius darat di sidebar.
- **Satelit dan radio** sebagai cadangan, serta kebijakan *rerouting* operator.
- **Lokasi persis** landing station dan jalur kabel: operator sering memublikasikan titik yang disederhanakan untuk alasan keamanan.
- Nama kota kadang ganda di sumber (misalnya *Benculuk* dan *Beculuk*, *Sangata* dan *Sangatta*) karena berasal dari pengumuman operator yang berbeda. Radius darat otomatis menyatukan pasangan semacam ini.

Rincian lengkap setiap sumber ada di `data/SUMBER_DATA.md`.
"""
    )
    st.markdown("**Download data (CSV/JSON)**")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("kabel.csv", data.kabel.to_csv(index=False).encode("utf-8"), "kabel.csv", "text/csv", width="stretch")
    d2.download_button("landing_station.csv", data.landing.to_csv(index=False).encode("utf-8"), "landing_station.csv", "text/csv", width="stretch")
    d3.download_button("kabel_landing.csv", data.relasi.to_csv(index=False).encode("utf-8"), "kabel_landing.csv", "text/csv", width="stretch")
    with open(muat_data.DATA / "kabel_geo.json", "rb") as fh:
        d4.download_button("kabel_geo.json", fh.read(), "kabel_geo.json", "application/geo+json", width="stretch")

# ---------------------------------------------------------------- 5f. HOW IT WORKS
with tab_cara:
    st.subheader("Bagaimana aplikasi ini bekerja")
    st.code(
        """
Submarine Cable Map API  ──►  scripts/bangun_data.py  ──►  data/kabel.csv, landing_station.csv,
(713 kabel, 1.928 titik)      saring Indonesia + kawasan     kabel_landing.csv, kabel_geo.json
                                                                        │
                                       src/wilayah.py  (lat/lon → 7 wilayah)
                                                                        │
            src/skenario.py ─ pilih kabel (manual / stasiun / negara / kotak laut: Liang-Barsky)
                                                                        │
            src/jaringan.py ─ graf landing station + sisi kabel + sisi darat (haversine < radius)
                              hapus kabel putus → komponen terhubung → status per landing station
                                                                        │
                                                        app.py ─ peta, metrik, tabel, sankey
""",
        language="text",
    )
    st.markdown(
        """
| Modul | Yang dilakukan |
|---|---|
| `scripts/bangun_data.py` | Unduh daftar kabel, detail per kabel, dan geometri dari API publik; saring yang mendarat di Indonesia atau melintas kotak perairan Indonesia; simpan CSV/GeoJSON ringkas |
| `src/muat_data.py` | Baca CSV/JSON dengan tipe yang benar; pencarian kabel ↔ landing station |
| `src/wilayah.py` | Aturan kotak lintang-bujur untuk tujuh wilayah besar |
| `src/skenario.py` | Empat cara memilih kabel yang diputus, termasuk uji ruas garis vs persegi (Liang-Barsky) |
| `src/jaringan.py` | Graf networkx: simpul landing station, sisi kabel (clique per kabel) + sisi darat; simulasi, status, ringkasan wilayah, gateway, linimasa |
| `app.py` | UI Streamlit: sidebar, peta Plotly (`Scattermap`), metrik, sankey, tabel, learning mode |

**Definisi yang dipakai**

- **Kabel internasional**: minimal satu landing station di Indonesia dan minimal satu di luar negeri.
- **Kabel domestik**: semua landing station di Indonesia.
- **Kabel kawasan**: tidak mendarat di Indonesia tetapi lintasannya melewati kotak 94-142° BT, 12° LS-8° LU. Hanya untuk konteks peta; tidak masuk graf.
- **Aktif**: `is_planned = false` menurut Submarine Cable Map (sudah RFS). Kabel dengan RFS akhir 2025 atau 2026 yang sudah ditandai aktif ikut dihitung aktif.
- **Pintu keluar internasional**: jumlah kabel internasional berbeda yang bisa dicapai dari suatu landing station lewat rantai kabel dan sambungan darat.

Pengujian: `python -m pytest tests/ -v` (59 tes, tanpa internet) mencakup graf mainan sembilan simpul, aturan status,
geometri kotak, pembagian wilayah, dan konsistensi data asli.
"""
    )
    if mode_belajar:
        with st.expander("🎓 Mengapa Streamlit menghitung ulang semuanya?"):
            st.markdown(
                """
Setiap kali kamu mengubah widget, Streamlit menjalankan `app.py` dari atas ke bawah. Yang mahal (membaca CSV dan
GeoJSON) dibungkus `@st.cache_resource` sehingga hanya terjadi sekali per proses. Simulasi graf sendiri hanya
membutuhkan ±50 ms untuk 361 simpul dan ±2.000 sisi, jadi tidak perlu di-cache: lebih sederhana dan selalu segar.

```python
@st.cache_resource(show_spinner="Memuat data kabel...")
def muat():
    return muat_data.muat_semua(), muat_data.muat_data_center()
```
Aturan praktis: cache yang lambat dan tidak bergantung pada widget; biarkan yang cepat dihitung ulang.
"""
            )
