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


def _lp(negara):
    return {"country": negara}


def _geo(*titik):
    return {"geometry": {"coordinates": [list(titik)]}}


def test_kategori_kabel_domestik_internasional_transit():
    assert bd.kategori_kabel([_lp("Indonesia"), _lp("Indonesia")], None) == "domestik"
    assert bd.kategori_kabel([_lp("Indonesia"), _lp("Singapore")], None) == "internasional"
    # Tidak mendarat, tapi garisnya lewat Laut Jawa (lon, lat).
    assert bd.kategori_kabel([_lp("Singapore"), _lp("Australia")], _geo([104.0, 1.0], [110.0, -5.0])) == "transit"


def test_kategori_kabel_tidak_relevan():
    assert bd.kategori_kabel([_lp("Japan"), _lp("United States")], _geo([140.0, 35.0], [-120.0, 34.0])) is None
    assert bd.kategori_kabel([_lp("Japan")], None) is None
    assert bd.kategori_kabel([], None) is None


def test_main_dengan_api_tiruan(tmp_path, monkeypatch):
    import json

    def kabel(id_, planned, *landing):
        return {"id": id_, "name": id_.upper(), "is_planned": planned, "rfs_year": 2020, "rfs": "2020 Q1",
                "length": "1,000 km", "owners": "A", "suppliers": "B",
                "landing_points": [{"id": l, "name": f"{l.title()}, {n}", "country": n} for l, n in landing]}

    detail = {
        "jaya": kabel("jaya", False, ("jakarta", "Indonesia"), ("batam", "Indonesia")),
        "lintas": kabel("lintas", True, ("batam", "Indonesia"), ("changi", "Singapore")),
        "jauh": kabel("jauh", False, ("tokyo", "Japan"), ("la", "United States")),
    }
    respons = {
        "cable/all.json": [{"id": k} for k in detail],
        "cable/cable-geo.json": {"features": [
            {"properties": {"id": "jaya", "color": "#f00"}, "geometry": {"coordinates": [[[106.8, -6.1], [104.0, 1.1]]]}},
        ]},
        "landing-point/landing-point-geo.json": {"features": [
            {"properties": {"id": "jakarta"}, "geometry": {"coordinates": [106.8, -6.1]}},
            {"properties": {"id": "batam"}, "geometry": {"coordinates": [104.0, 1.1]}},
        ]},
    }

    def palsu(url):
        jalur = url.removeprefix(bd.API + "/")
        if jalur in respons:
            return respons[jalur]
        return detail[jalur.removeprefix("cable/").removesuffix(".json")]

    monkeypatch.setattr(bd, "ambil_json", palsu)
    monkeypatch.setattr(bd, "DATA", tmp_path)
    bd.main()

    meta = json.loads((tmp_path / "META.json").read_text(encoding="utf-8"))
    assert meta["n_kabel_dunia"] == 3 and meta["n_kabel"] == 2
    assert meta["n_kabel_per_kategori"] == {"domestik": 1, "internasional": 1}
    assert meta["n_landing_indonesia"] == 2
    landing = (tmp_path / "landing_station.csv").read_text(encoding="utf-8")
    # Batam dilewati dua kabel, tapi cuma satu yang sudah aktif.
    baris_batam = next(b for b in landing.splitlines() if b.startswith("batam,"))
    assert ",1,2," in baris_batam
    geo = json.loads((tmp_path / "kabel_geo.json").read_text(encoding="utf-8"))
    assert [f["properties"]["id"] for f in geo["features"]] == ["jaya"]
