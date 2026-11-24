"""Uji kalender (MDE-H2-02)."""
from pathlib import Path

import pandas as pd
import pytest

from renaro.contract import TABLE_COLUMNS
from renaro.data import calendar as K

CAL = Path("data/interim/calendar.csv")


def test_refs_have_source_and_no_duplicates():
    rel, cb = K.load_refs()
    assert rel.loc[rel["idulfitri"].notna(), "source_url"].str.startswith("http").all()
    assert cb["source_url"].str.startswith("http").all()
    assert set(range(2017, 2027)) <= set(rel["year"].astype(int))
    assert (rel["ramadan_start"].dropna() < rel.loc[rel["ramadan_start"].notna(), "idulfitri"]).all()


def _build(start="2021-01-01", end="2022-12-31"):
    rel, cb = K.load_refs()
    lib = K.library_holidays(range(2021, 2024))
    return K.build_calendar(start, end, rel, cb, lib, None, None)[0], rel


def test_schema_and_no_gaps():
    cal, rel = _build()
    K.validate(cal, rel, "2021-01-01", "2022-12-31")
    assert list(cal.columns[:11]) == list(TABLE_COLUMNS["calendar"])
    assert len(cal) == 730


def test_lebaran_ramadan_iduladha_2022():
    cal, _ = _build()
    c = cal.set_index("date")
    assert c.at[pd.Timestamp("2022-05-02"), "days_to_lebaran"] == 0
    assert c.at[pd.Timestamp("2022-05-01"), "days_to_lebaran"] == 1
    assert c.at[pd.Timestamp("2022-04-03"), "is_ramadan"] and not c.at[pd.Timestamp("2022-04-02"), "is_ramadan"]
    assert not c.at[pd.Timestamp("2022-05-02"), "is_ramadan"]
    assert c.at[pd.Timestamp("2022-07-10"), "days_to_iduladha"] == 0          # isbat, bukan SKB 9 Jul
    assert c.at[pd.Timestamp("2022-05-12"), "is_post_lebaran"] and not c.at[pd.Timestamp("2022-05-13"), "is_post_lebaran"]


def test_cuti_bersama_and_holiday():
    cal, _ = _build()
    c = cal.set_index("date")
    for d in ["2022-04-29", "2022-05-04", "2022-05-05", "2022-05-06", "2021-05-12"]:
        assert c.at[pd.Timestamp(d), "is_cuti_bersama"], d
    assert not c.at[pd.Timestamp("2021-12-24"), "is_cuti_bersama"]          # dihapus SKB 712/2021
    assert c.at[pd.Timestamp("2022-05-02"), "is_holiday"] and c.at[pd.Timestamp("2022-05-03"), "is_holiday"]
    assert c.at[pd.Timestamp("2021-12-25"), "is_holiday"]


def test_natal_window_and_dow():
    cal, _ = _build()
    c = cal.set_index("date")
    assert c.at[pd.Timestamp("2021-12-20"), "is_natal_tahunbaru"] and c.at[pd.Timestamp("2022-01-05"), "is_natal_tahunbaru"]
    assert not c.at[pd.Timestamp("2022-01-06"), "is_natal_tahunbaru"]
    assert c.at[pd.Timestamp("2022-05-02"), "dow"] == 0                       # Senin


def test_workday_from_pihps_inside_range_rule_outside():
    rel, cb = K.load_refs()
    lib = K.library_holidays(range(2021, 2024))
    wd = pd.DatetimeIndex(["2022-01-03", "2022-01-05"])
    cal, _ = K.build_calendar("2022-01-01", "2022-01-12", rel, cb, lib, wd,
                              (pd.Timestamp("2022-01-03"), pd.Timestamp("2022-01-07")))
    c = cal.set_index("date")
    assert not c.at[pd.Timestamp("2022-01-04"), "is_workday_pihps"]          # Selasa, tapi PIHPS tidak melapor
    assert c.at[pd.Timestamp("2022-01-05"), "workday_source"] == "pihps"
    assert c.at[pd.Timestamp("2022-01-10"), "is_workday_pihps"] and c.at[pd.Timestamp("2022-01-10"), "workday_source"] == "rule"


def test_real_calendar_file():
    if not CAL.exists():
        pytest.skip("calendar.csv belum dibuat")
    cal = pd.read_csv(CAL, parse_dates=["date"])
    assert cal["date"].min() <= pd.Timestamp("2017-09-01") and cal["date"].max() >= pd.Timestamp("2026-12-31")
    assert (cal["date"].diff().dropna() == pd.Timedelta(days=1)).all()
    assert set(cal.columns) >= set(TABLE_COLUMNS["calendar"])
