"""Uji parser PIHPS tanpa jaringan (MDE-H1-01)."""
import datetime as dt
import math

import pytest

from renaro.contract import HOLDOUT_START
from renaro.data import pihps


@pytest.mark.parametrize("raw, expected", [
    ("45.250", 45250.0), ("45,250", 45250.0), ("45250", 45250.0), (45250, 45250.0),
    ("1,045,250", 1045250.0), (" 44,750 ", 44750.0),
])
def test_numeric_id_values(raw, expected):
    assert pihps.numeric_id(raw) == expected


@pytest.mark.parametrize("raw", ["-", "", None, "0", 0, "45,25", "abc"])
def test_numeric_id_missing(raw):
    assert math.isnan(pihps.numeric_id(raw))


def _payload():
    return {"data": [
        {"no": "", "name": "Semua Provinsi", "level": 0, "01/03/2024": "50,000"},
        {"no": "1", "name": "Aceh", "level": 1, "01/03/2024": "44,750", "04/03/2024": "-"},
        {"no": "1.1", "name": "Kota Banda Aceh", "level": 2, "01/03/2024": "45,000"},
        {"no": "2", "name": "DI Yogyakarta ", "level": 1, "01/03/2024": "38.500", "04/03/2024": "39,000"},
    ]}


def test_parse_payload_keeps_only_provinces():
    long = pihps.parse_payload(_payload(), 1, "x.json.gz")
    assert set(long["prov_name_raw"]) == {"Aceh", "DI Yogyakarta"}
    assert len(long) == 4
    row = long[(long["prov_name_raw"] == "DI Yogyakarta") & (long["date"] == "2024-03-01")].iloc[0]
    assert row["price_num"] == 38500.0 and row["price_raw"] == "38.500"
    assert long.loc[long["price_raw"] == "-", "price_num"].isna().all()


def test_split_at_holdout():
    parts = pihps.split_at_holdout(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert parts == [(dt.date(2026, 1, 1), dt.date(2026, 5, 31), False),
                     (HOLDOUT_START, dt.date(2026, 12, 31), True)]
    assert all(end < HOLDOUT_START for _, _, end in pihps.WINDOWS)


def test_save_parse_roundtrip_and_manifest(tmp_path):
    json_dir = tmp_path / "json"
    path = pihps.save_payload(_payload(), json_dir, 1, dt.date(2024, 3, 1), dt.date(2024, 3, 31))
    h1 = pihps.sha256_file(path)
    pihps.save_payload(_payload(), json_dir, 1, dt.date(2024, 3, 1), dt.date(2024, 3, 31))
    assert pihps.sha256_file(path) == h1  # tulis ulang = hash sama
    assert path.suffix == ".json"
    long = pihps.parse_dir(json_dir)
    assert long["date"].max() < __import__("pandas").Timestamp(HOLDOUT_START)
    man = tmp_path / "manifest.csv"
    pihps.upsert_manifest(man, {"file": "json/a", "price_type": 1})
    pihps.upsert_manifest(man, {"file": "json/a", "price_type": 1, "http_status": 200})
    assert man.read_text().count("json/a") == 1


def test_parse_dir_refuses_holdout_file(tmp_path):
    json_dir = tmp_path / "json"
    pihps.save_payload(_payload(), json_dir, 1, dt.date(2026, 6, 1), dt.date(2026, 6, 30))
    with pytest.raises(SystemExit):
        pihps.parse_dir(json_dir)


def test_reads_legacy_gz_and_rejects_double(tmp_path):
    import gzip, json
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    gz = json_dir / "pihps_pt1_2024-03-01_2024-03-31.json.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as fh:
        json.dump(_payload(), fh)
    assert len(pihps.parse_dir(json_dir)) == 4
    pihps.save_payload(_payload(), json_dir, 1, dt.date(2024, 3, 1), dt.date(2024, 3, 31))
    with pytest.raises(SystemExit):
        pihps.parse_dir(json_dir)
