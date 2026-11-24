"""Uji SP2KP tanpa jaringan (MDE-H1-02)."""
import datetime as dt
import json

import pandas as pd
import pytest

from renaro.contract import HOLDOUT_START, PROV_CODES, PROVINCES
from renaro.data import sp2kp as S

# Kode Kemendagri (dipakai SP2KP) untuk Papua; provinsi lain sama dengan BPS.
KEMENDAGRI_PAPUA = [("91", "Papua"), ("92", "Papua Barat"), ("93", "Papua Selatan"),
                    ("94", "Papua Tengah"), ("95", "Papua Pegunungan"), ("96", "Papua Barat Daya")]
# Nama persis dari master SP2KP (2026-11-24), termasuk ejaan "Daerah Istimewa Yogyakarta".
MASTER_38 = [(c, "Daerah Istimewa Yogyakarta" if c == "34" else n)
             for c, n in PROVINCES if c not in {"91", "94"}] + KEMENDAGRI_PAPUA


def _area(prices, variant_id=2):
    return {"status": "success", "data": [
        {"variant_id": variant_id, "variant": "Cabai Merah Keriting", "satuan": "kg",
         "daftarHarga": [{"date": d, "harga": h} for d, h in prices]},
        {"variant_id": 9, "variant": "Cabai Merah Besar", "satuan": "kg",
         "daftarHarga": [{"date": "2024-03-01", "harga": 1}]},
    ]}


def test_master_has_38_and_all_map():
    assert len(MASTER_38) == 38
    codes = {S.old_code_of(n) for _, n in MASTER_38}
    assert codes == set(PROV_CODES)


def test_papua_codes_not_confused():
    # SP2KP 94 = Papua Tengah -> BPS lama 94 (Papua), SP2KP 92 = Papua Barat -> BPS lama 91
    assert S.old_code_of("Papua Tengah") == "94"
    assert S.old_code_of("Papua Barat") == "91"
    assert S.old_code_of("Papua Barat Daya") == "91"
    assert S.old_code_of("Daerah Istimewa Yogyakarta") == "34"
    with pytest.raises(KeyError):
        S.old_code_of("Provinsi Antah")


def test_extract_provinces_tolerant():
    p = S.extract_provinces({"data": [{"kode_provinsi": "11", "nama_provinsi": "Aceh "}, {"x": 1}]})
    assert p == [{"kode": "11", "nama": "Aceh"}]


def test_parse_area_filters_variant_and_zero():
    f = S.parse_area(_area([("2024-03-01", 50000), ("2024-03-04", 0), ("2024-03-05", None)]), "31", "DKI Jakarta")
    assert len(f) == 3 and f["price_raw"].notna().sum() == 1


def test_windows_calendar_years_and_holdout():
    w = S.windows(dt.date(2024, 2, 1), dt.date(2026, 11, 23), 0)
    assert w[0] == (dt.date(2024, 2, 1), dt.date(2024, 12, 31), False)
    assert (dt.date(2026, 1, 1), dt.date(2026, 5, 31), False) in w
    assert w[-1] == (HOLDOUT_START, dt.date(2026, 11, 23), True)
    assert all(e < HOLDOUT_START for s, e, sealed in w if not sealed)


def _write_dir(tmp_path):
    (tmp_path / S.MASTER_NAME).write_text(json.dumps(
        {"data": [{"kode_provinsi": c, "nama_provinsi": n} for c, n in MASTER_38]}), encoding="utf-8")
    for i, (code, name) in enumerate(MASTER_38):
        price = 40000 + 1000 * i
        (tmp_path / S.file_name(code, dt.date(2024, 3, 1), dt.date(2024, 3, 31))).write_text(
            json.dumps(_area([("2024-03-01", price), ("2024-03-04", price)])), encoding="utf-8")


def test_parse_and_map_to_34(tmp_path):
    _write_dir(tmp_path)
    long = S.map_to_old_34(S.parse_dir(tmp_path))
    assert set(long["prov_code"]) == set(PROV_CODES) and len(long) == 34 * 2
    papua = long[(long["prov_code"] == "94") & (long["date"] == "2024-03-01")].iloc[0]
    prices = {n: 40000 + 1000 * i for i, (_, n) in enumerate(MASTER_38)}
    expect = (prices["Papua"] + prices["Papua Selatan"] + prices["Papua Tengah"] + prices["Papua Pegunungan"]) / 4
    assert papua["price"] == expect and papua["is_aggregated"] and papua["n_source_prov"] == 4
    pb = long[(long["prov_code"] == "91") & (long["date"] == "2024-03-01")].iloc[0]
    assert pb["n_source_prov"] == 2 and pb["is_aggregated"]
    assert not long.loc[long["prov_code"] == "31", "is_aggregated"].any()
    assert (long["available_at"] > long["date"]).all()
    assert long.loc[long["date"] == "2024-03-01", "available_at"].iloc[0] == pd.Timestamp("2024-03-04")
    assert S.validate(long) == ["data mulai 2024-03-01, harusnya Feb 2024"]


def test_parse_dir_rejects_holdout(tmp_path):
    _write_dir(tmp_path)
    (tmp_path / S.file_name("31", HOLDOUT_START, dt.date(2026, 6, 30))).write_text(json.dumps(_area([])))
    with pytest.raises(SystemExit):
        S.parse_dir(tmp_path)


def test_handoff_sp2kp(tmp_path):
    out = tmp_path / "sp2kp"
    (out / "_sealed").mkdir(parents=True)
    (out / "_sealed" / S.file_name("31", HOLDOUT_START, dt.date(2026, 11, 24))).write_text("{}")
    doc = tmp_path / "seal.md"
    doc.write_text("# seal\n", encoding="utf-8")
    S.run_handoff(out, tmp_path / "kirim", doc)
    assert not list((out / "_sealed").glob("*.json"))
    assert (tmp_path / "kirim" / "l1_p31_20260601_20261124.json").exists()
    assert "MDE-H1-02" in doc.read_text(encoding="utf-8")


def test_report(tmp_path):
    _write_dir(tmp_path)
    long = S.map_to_old_34(S.parse_dir(tmp_path))
    interim = tmp_path / "long.parquet"
    long.to_parquet(interim)
    S.upsert_manifest(tmp_path / S.MANIFEST_NAME, {"file": "x.json", "kode_provinsi": "31", "http_status": 200})
    st = S.run_report(tmp_path, interim, tmp_path / "rep.md")
    assert st["n_mapped"] == 34 and st["n_source"] == 38 and st["n_master"] == 38
    text = (tmp_path / "rep.md").read_text(encoding="utf-8")
    assert "34 dari 34 provinsi" in text and "Tidak dipakai sebagai fitur atau target" in text
