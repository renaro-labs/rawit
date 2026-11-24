"""Uji scraper + parser PIHPS tanpa jaringan (MDE-H1-01)."""
import datetime as dt
import gzip
import json
import math

import pandas as pd
import pytest

from renaro.contract import HOLDOUT_START, PROV_NAMES
from renaro.data import pihps
from renaro.data import pihps_parse as P


@pytest.mark.parametrize("raw, expected", [
    ("45.250", 45250.0), ("45,250", 45250.0), ("45250", 45250.0), (45250, 45250.0),
    ("1,045,250", 1045250.0), (" 44,750 ", 44750.0),
])
def test_numeric_id_values(raw, expected):
    assert P.numeric_id(raw) == expected


@pytest.mark.parametrize("raw", ["-", "", None, "0", 0, "45,25", "abc"])
def test_numeric_id_missing(raw):
    assert math.isnan(P.numeric_id(raw))


def _payload():
    return {"data": [
        {"no": "", "name": "Semua Provinsi", "level": 0, "01/03/2024": "50,000"},
        {"no": "1", "name": "Aceh", "level": 1, "01/03/2024": "44,750", "04/03/2024": "-"},
        {"no": "1.1", "name": "Kota Banda Aceh", "level": 2, "01/03/2024": "45,000"},
        {"no": "2", "name": "DI Yogyakarta ", "level": 1, "01/03/2024": "38.500", "04/03/2024": "39,000"},
    ]}


def _write(dir_, name, payload):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(json.dumps(payload), encoding="utf-8")


def test_parse_payload_schema_and_levels():
    long = P.parse_payload(_payload(), 1, "x.json")
    assert list(long.columns[:4]) == ["date", "prov_name_raw", "price_type", "price_raw"]
    assert long["price_raw"].dtype == "float64"
    assert set(long["prov_name_raw"]) == {"Aceh", "DI Yogyakarta"}
    row = long[(long["prov_name_raw"] == "DI Yogyakarta") & (long["date"] == "2024-03-01")].iloc[0]
    assert row["price_raw"] == 38500.0 and row["price_str"] == "38.500"
    assert long.loc[long["price_str"] == "-", "price_raw"].isna().all()


def test_file_names_both_formats():
    assert pihps.file_name(1, dt.date(2018, 1, 1), dt.date(2018, 12, 31)) == "pt1_20180101_20181231.json"
    assert P.parse_file_name("pt4_20190101_20191231.json") == (4, dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    assert P.parse_file_name("pihps_pt1_2017-07-01_2018-06-30.json.gz")[0] == 1
    assert P.parse_file_name("manifest.csv") is None


def test_windows_and_split():
    assert all(end < HOLDOUT_START for _, _, end in pihps.WINDOWS)
    t1 = [w for w in pihps.WINDOWS if w[0] == 1]
    assert t1[0][1] == dt.date(2017, 7, 1) and t1[-1][2] == dt.date(2026, 5, 31) and len(t1) == 10
    assert min(w[1] for w in pihps.WINDOWS if w[0] == 4) == dt.date(2019, 1, 1)
    parts = pihps.split_at_holdout(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert parts[-1] == (HOLDOUT_START, dt.date(2026, 12, 31), True)


def test_parse_dir_ignores_sealed_and_rejects_holdout(tmp_path):
    _write(tmp_path, "pt1_20240301_20240331.json", _payload())
    _write(tmp_path / "_sealed", "pt1_20260601_20261123.json", _payload())
    _write(tmp_path, "manifest.csv", {"x": 1})
    long = P.parse_dir(tmp_path)
    assert len(long) == 4 and long["date"].max() < pd.Timestamp(HOLDOUT_START)
    _write(tmp_path, "pt1_20260601_20260630.json", _payload())
    with pytest.raises(SystemExit):
        P.parse_dir(tmp_path)


def test_parse_dir_legacy_gz(tmp_path):
    with gzip.open(tmp_path / "pihps_pt1_2024-03-01_2024-03-31.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(_payload(), fh)
    assert len(P.parse_dir(tmp_path)) == 4


def test_parse_dir_conflicting_overlap(tmp_path):
    _write(tmp_path, "pt1_20240301_20240331.json", _payload())
    other = _payload()
    other["data"][1]["01/03/2024"] = "99,000"
    _write(tmp_path, "pt1_20240301_20240315.json", other)
    with pytest.raises(SystemExit):
        P.parse_dir(tmp_path)


def test_save_raw_and_manifest(tmp_path):
    raw = json.dumps(_payload()).encode()
    path = pihps.save_raw(raw, tmp_path, 1, dt.date(2024, 3, 1), dt.date(2024, 3, 31))
    assert path.read_bytes() == raw
    man = tmp_path / "manifest.csv"
    pihps.upsert_manifest(man, {"file": path.name, "price_type": 1, "http_status": 500})
    pihps.upsert_manifest(man, {"file": path.name, "price_type": 1, "http_status": 200})
    rows = pd.read_csv(man)
    assert len(rows) == 1 and rows.loc[0, "http_status"] == 200
    for col in ["file", "price_type", "start", "end", "n_bytes", "sha256", "fetched_at", "http_status"]:
        assert col in rows.columns


def test_validate_and_spotcheck_on_full_synthetic():
    days = pd.bdate_range("2017-07-03", "2026-05-29")
    rows = [{"name": n, "level": 1, **{d.strftime("%d/%m/%Y"): "40,000" for d in days}} for n in PROV_NAMES]
    long = P.parse_payload({"data": rows}, 1)
    assert P.validate_long(long) == []
    sample = P.spot_check_sample(long)
    assert len(sample) == 9


def test_handoff_moves_sealed(tmp_path, monkeypatch):
    out = tmp_path / "raw"
    _write(out / "_sealed", "pt1_20260601_20261123.json", _payload())
    doc = tmp_path / "holdout_seal.md"
    doc.write_text("# seal\n", encoding="utf-8")
    pihps.run_handoff(out, tmp_path / "cgs", doc)
    assert not list((out / "_sealed").glob("*.json"))
    assert (tmp_path / "cgs" / "pt1_20260601_20261123.json").exists()
    assert "Serah-terima MDE" in doc.read_text(encoding="utf-8")
