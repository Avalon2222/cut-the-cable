"""
src/jaringan.py - jaringan kabel sebagai graf, dan simulasi kabel putus
=======================================================================
Model yang dipakai sengaja sederhana supaya bisa dihitung ulang dalam sepersekian detik
dan mudah dijelaskan:

  * Simpul  = landing station (di Indonesia maupun luar negeri).
  * Sisi    = sebuah kabel menghubungkan SEMUA landing station-nya satu sama lain.
              Satu kabel dengan 5 landing station menjadi 10 sisi, masing-masing diberi label
              id kabel. Beberapa kabel yang menghubungkan dua kota yang sama berbagi satu sisi
              dengan beberapa label.
  * Putus   = kabel dianggap mati seluruhnya (semua sisinya hilang). Kenyataannya kabel bisa
              putus di satu segmen saja, tetapi data publik tidak menyimpan topologi segmen.
  * Darat   = dua landing station di negara yang sama dan berjarak kurang dari `radius_darat_km`
              (bawaan 60 km: Jakarta-Ancol-Tanjung Pakis, Batam-Nongsa, Manado-Kauditan, dsb.)
              dianggap tersambung lewat serat optik darat. Sisi ini tidak pernah ikut putus.

Dengan graf ini kita bisa menjawab untuk setiap landing station Indonesia:
  1. Berapa kabel yang masih mendarat di sana?
  2. Masih ada jalur (lewat kabel apa pun, termasuk domestik) ke landing station luar negeri?
  3. Berapa "pintu keluar" internasional yang masih bisa dijangkau dari sana?

Yang TIDAK dimodelkan: kapasitas (Tbps) tiap kabel, lalu lintas sebenarnya, jaringan serat
darat di dalam pulau, perbatasan darat (Kalimantan-Malaysia, Papua-PNG), dan satelit.
Lihat docs/BELAJAR.md bagian "Batas model".
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import combinations

import networkx as nx
import pandas as pd

from .muat_data import Data

STATUS = ["Gelap total", "Terputus dari dunia", "Hidup lewat darat", "Rentan (1 kabel tersisa)", "Kehilangan jalur", "Aman"]
WARNA_STATUS = {
    "Gelap total": "#ff2d55",
    "Terputus dari dunia": "#ff7a1a",
    "Hidup lewat darat": "#c084fc",
    "Rentan (1 kabel tersisa)": "#ffd23f",
    "Kehilangan jalur": "#9ad1ff",
    "Aman": "#3fd0a4",
}
PENJELASAN_STATUS = {
    "Gelap total": "Semua kabel lautnya putus dan tidak ada landing station tetangga (jalur darat) yang bisa menolong.",
    "Terputus dari dunia": "Masih punya sambungan, tetapi seluruh kelompoknya tidak lagi punya jalur ke landing station luar negeri.",
    "Hidup lewat darat": "Semua kabel lautnya putus; hanya tersambung lewat landing station tetangga dalam radius darat.",
    "Rentan (1 kabel tersisa)": "Masih tersambung ke dunia, tetapi hanya satu kabel laut yang tersisa; satu gangguan lagi memutusnya.",
    "Kehilangan jalur": "Kehilangan satu atau lebih kabel, tetapi masih punya dua kabel atau lebih dan jalur ke dunia.",
    "Aman": "Tidak ada kabel yang hilang di landing station ini.",
}
URUTAN_KEPARAHAN = {s: i for i, s in enumerate(STATUS)}


def kabel_aktif(data: Data, sertakan_rencana: bool = False) -> pd.DataFrame:
    """Kabel yang dihitung dalam graf: yang mendarat di Indonesia (domestik + internasional), aktif
    kecuali diminta ikut menyertakan rencana. Kabel kawasan (transit) tidak masuk graf karena
    tidak menyentuh Indonesia."""
    k = data.kabel[data.kabel["kategori"].isin(["domestik", "internasional"])]
    if not sertakan_rencana:
        k = k[k["status"] == "aktif"]
    return k


RADIUS_DARAT_KM = 60.0


def jarak_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Jarak lingkaran besar (haversine) dalam km; cukup akurat untuk puluhan-ratusan km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pasangan_darat(landing: pd.DataFrame, radius_km: float) -> list[tuple[str, str]]:
    """Pasangan landing station senegara yang berjarak < radius_km (dianggap tersambung lewat darat)."""
    if radius_km <= 0:
        return []
    hasil = []
    titik = landing.dropna(subset=["lat", "lon"])
    for _, grup in titik.groupby("negara"):
        baris = list(grup[["id", "lat", "lon"]].itertuples(index=False))
        for (a, la1, lo1), (b, la2, lo2) in combinations(baris, 2):
            if jarak_km(la1, lo1, la2, lo2) < radius_km:
                hasil.append((a, b))
    return hasil


def bangun_graf(data: Data, putus: Iterable[str] = (), sertakan_rencana: bool = False,
                radius_darat_km: float = RADIUS_DARAT_KM) -> nx.Graph:
    """Bangun graf landing station dari semua kabel yang dihitung, minus kabel yang diputus,
    ditambah sisi "darat" antar landing station yang berdekatan."""
    putus = set(putus)
    kabel = kabel_aktif(data, sertakan_rencana)
    negara = data.landing.set_index("id")["negara"].to_dict()
    G = nx.Graph()
    for lid, neg in negara.items():
        G.add_node(lid, negara=neg)
    for a, b in pasangan_darat(data.landing, radius_darat_km):
        G.add_edge(a, b, kabel=set(), darat=True)
    relasi = data.relasi[data.relasi["id_kabel"].isin(kabel["id"])]
    for id_kabel, grup in relasi.groupby("id_kabel"):
        if id_kabel in putus:
            continue
        simpul = grup.sort_values("urutan")["id_landing"].tolist()
        for a, b in combinations(simpul, 2):
            if G.has_edge(a, b):
                G[a][b]["kabel"].add(id_kabel)
            else:
                G.add_edge(a, b, kabel={id_kabel})
    return G


def _komponen_internasional(G: nx.Graph) -> dict[str, bool]:
    """Untuk setiap simpul: apakah komponen terhubungnya memuat simpul luar negeri?"""
    hasil = {}
    for komp in nx.connected_components(G):
        ada_asing = any(G.nodes[n]["negara"] != "Indonesia" for n in komp)
        for n in komp:
            hasil[n] = ada_asing
    return hasil


def _pintu_keluar(G: nx.Graph, kabel_internasional: set[str]) -> dict[str, int]:
    """Jumlah kabel internasional berbeda yang bisa dicapai dari komponen setiap simpul."""
    hasil = {}
    for komp in nx.connected_components(G):
        kabel_komp: set[str] = set()
        for a, b, atr in G.subgraph(komp).edges(data=True):
            kabel_komp |= atr["kabel"] & kabel_internasional
        for n in komp:
            hasil[n] = len(kabel_komp)
    return hasil


def tentukan_status(n_awal: int, n_sisa: int, int_awal: bool, int_sisa: bool) -> str:
    """Aturan label untuk satu landing station setelah pemutusan."""
    if n_awal == 0:
        return "Aman"                      # tidak punya kabel sejak awal (hanya di kabel rencana)
    if n_sisa == 0 and not int_sisa:
        return "Gelap total"
    if int_awal and not int_sisa:
        return "Terputus dari dunia"
    if n_sisa == 0:
        return "Hidup lewat darat"
    if n_sisa < n_awal and n_sisa == 1:
        return "Rentan (1 kabel tersisa)"
    if n_sisa < n_awal:
        return "Kehilangan jalur"
    return "Aman"


def simulasi(data: Data, putus: Iterable[str], sertakan_rencana: bool = False,
             radius_darat_km: float = RADIUS_DARAT_KM) -> pd.DataFrame:
    """
    Bandingkan keadaan sebelum dan sesudah kabel-kabel `putus` dimatikan.

    Mengembalikan satu baris per landing station INDONESIA dengan kolom:
      id, nama, kota, wilayah, lat, lon,
      n_kabel_awal, n_kabel_sisa, kabel_hilang (nama kabel, dipisah '; '),
      internasional_awal, internasional_sisa (bool: masih ada jalur ke luar negeri),
      pintu_awal, pintu_sisa (jumlah kabel internasional yang terjangkau),
      status (salah satu dari STATUS).
    """
    putus = set(putus)
    kabel = kabel_aktif(data, sertakan_rencana)
    kabel_int = set(kabel.loc[kabel["kategori"] == "internasional", "id"])
    nama_kabel = kabel.set_index("id")["nama"].to_dict()

    G0 = bangun_graf(data, (), sertakan_rencana, radius_darat_km)
    G1 = bangun_graf(data, putus, sertakan_rencana, radius_darat_km)
    int0, int1 = _komponen_internasional(G0), _komponen_internasional(G1)
    pintu0, pintu1 = _pintu_keluar(G0, kabel_int), _pintu_keluar(G1, kabel_int)

    relasi = data.relasi[data.relasi["id_kabel"].isin(kabel["id"])]
    per_landing = relasi.groupby("id_landing")["id_kabel"].apply(set).to_dict()

    baris = []
    idn = data.landing[data.landing["negara"] == "Indonesia"]
    for r in idn.itertuples():
        semua = per_landing.get(r.id, set())
        hilang = semua & putus
        sisa = semua - putus
        baris.append(
            {
                "id": r.id, "nama": r.nama, "kota": r.kota, "wilayah": r.wilayah, "lat": r.lat, "lon": r.lon,
                "n_kabel_awal": len(semua), "n_kabel_sisa": len(sisa),
                "kabel_hilang": "; ".join(sorted(nama_kabel.get(k, k) for k in hilang)),
                "internasional_awal": bool(int0.get(r.id, False)),
                "internasional_sisa": bool(int1.get(r.id, False)),
                "pintu_awal": pintu0.get(r.id, 0),
                "pintu_sisa": pintu1.get(r.id, 0),
            }
        )
    df = pd.DataFrame(baris)
    df["status"] = [
        tentukan_status(a, s, ia, is_) for a, s, ia, is_ in
        zip(df["n_kabel_awal"], df["n_kabel_sisa"], df["internasional_awal"], df["internasional_sisa"])
    ]
    df["status"] = pd.Categorical(df["status"], categories=STATUS, ordered=True)
    return df.sort_values(["status", "n_kabel_sisa", "nama"]).reset_index(drop=True)


def ringkas_wilayah(hasil: pd.DataFrame) -> pd.DataFrame:
    """Agregasi hasil simulasi per wilayah: jumlah landing station per status dan persen terdampak."""
    aktif = hasil[hasil["n_kabel_awal"] > 0]
    tabel = pd.crosstab(aktif["wilayah"], aktif["status"], dropna=False).reindex(columns=STATUS, fill_value=0)
    tabel["Total"] = tabel.sum(axis=1)
    tabel["Terdampak"] = tabel["Total"] - tabel["Aman"]
    tabel["% terdampak"] = (100 * tabel["Terdampak"] / tabel["Total"]).round(0).astype(int)
    tabel["Terputus / gelap"] = tabel["Gelap total"] + tabel["Terputus dari dunia"] + tabel["Hidup lewat darat"]
    return tabel.sort_values(["Terputus / gelap", "Terdampak"], ascending=False)


def ringkas_angka(hasil: pd.DataFrame) -> dict:
    """Angka-angka besar untuk kartu metrik."""
    aktif = hasil[hasil["n_kabel_awal"] > 0]
    return {
        "n_landing": int(len(aktif)),
        "gelap": int((aktif["status"] == "Gelap total").sum()),
        "terputus": int((aktif["status"] == "Terputus dari dunia").sum()),
        "darat": int((aktif["status"] == "Hidup lewat darat").sum()),
        "rentan": int((aktif["status"] == "Rentan (1 kabel tersisa)").sum()),
        "kehilangan": int((aktif["status"] == "Kehilangan jalur").sum()),
        "aman": int((aktif["status"] == "Aman").sum()),
        "pintu_awal": int(aktif["pintu_awal"].max()) if len(aktif) else 0,
        "pintu_sisa": int(aktif["pintu_sisa"].max()) if len(aktif) else 0,
    }


def gateway_luar_negeri(data: Data, sertakan_rencana: bool = False) -> pd.DataFrame:
    """
    Negara tujuan kabel internasional Indonesia: berapa kabel mendarat di masing-masing negara.
    Satu kabel bisa dihitung di beberapa negara (misalnya Bifrost: Singapura, Filipina, Guam, AS).
    """
    kabel = kabel_aktif(data, sertakan_rencana)
    kabel = kabel[kabel["kategori"] == "internasional"]
    negara_landing = data.landing.set_index("id")["negara"].to_dict()
    rel = data.relasi[data.relasi["id_kabel"].isin(kabel["id"])].copy()
    rel["negara"] = rel["id_landing"].map(negara_landing)
    rel = rel[rel["negara"] != "Indonesia"].drop_duplicates(["id_kabel", "negara"])
    nama = kabel.set_index("id")["nama"]
    tabel = (
        rel.groupby("negara")["id_kabel"]
        .agg(n_kabel="nunique", kabel=lambda s: "; ".join(sorted(nama[s])))
        .reset_index()
        .sort_values("n_kabel", ascending=False)
    )
    tabel["persen"] = (100 * tabel["n_kabel"] / len(kabel)).round(0).astype(int)
    return tabel


def kabel_per_tahun(data: Data) -> pd.DataFrame:
    """Jumlah kabel (yang mendarat di Indonesia) menurut tahun siap pakai, aktif dan rencana."""
    k = data.kabel[data.kabel["kategori"].isin(["domestik", "internasional"])].dropna(subset=["tahun_rfs"])
    t = k.groupby(["tahun_rfs", "kategori", "status"]).size().reset_index(name="jumlah")
    t["tahun_rfs"] = t["tahun_rfs"].astype(int)
    return t.sort_values("tahun_rfs")
