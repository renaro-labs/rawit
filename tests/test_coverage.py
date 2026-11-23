"""Uji laporan cakupan (MDE-H1-03) dengan data sintetis."""
import numpy as np
import pandas as pd

from renaro.contract import PROV_CODES, PROV_NAMES
from renaro.data import coverage as C


def _long(days, missing=None):
    """Long table tipe 1; missing = {(prov_name, date_str), ...} diberi harga '-'."""
    missing = missing or set()
    rows = []
    for d in days:
        for n in PROV_NAMES:
            gone = (n, d.strftime("%Y-%m-%d")) in missing
            rows.append((d, n, 1, np.nan if gone else 40000.0, "-" if gone else "40,000"))
    rows.append((days[0], "Dum", 1, 1.0, "1"))
    return pd.DataFrame(rows, columns=["date", "prov_name_raw", "price_type", "price_raw", "price_str"])


def test_longest_run():
    assert C._longest_run(np.array([0, 1, 1, 0, 1, 1, 1, 0], dtype=bool)) == 3
    assert C._longest_run(np.array([], dtype=bool)) == 0


def test_workday_definition_and_gate(tmp_path):
    days = pd.bdate_range("2018-01-01", "2025-12-31")
    holiday = days[10]
    missing = {(n, holiday.strftime("%Y-%m-%d")) for n in PROV_NAMES[:20]}       # < 50% lapor -> bukan hari kerja
    aceh_2019 = [d for d in days if d.year == 2019][:40]                         # Aceh hilang 40 hari di 2019
    missing |= {("Aceh", d.strftime("%Y-%m-%d")) for d in aceh_2019}
    for y in (2020, 2021, 2022, 2023):                                           # Riau < 90% di 4 tahun
        missing |= {("Riau", d.strftime("%Y-%m-%d")) for d in [x for x in days if x.year == y][:60]}
    path = tmp_path / "long.parquet"
    _long(days, missing).to_parquet(path)

    obs, dropped = C.load_type1(path)
    assert dropped == ["Dum"]
    wd = C.pihps_workdays(obs)
    assert holiday not in wd and len(wd) == len(days) - 1
    cov = C.coverage_table(obs, wd)
    assert list(cov.columns) == C.CSV_COLUMNS and len(cov) == 34 * 8
    aceh = cov[(cov["prov_code"] == "11") & (cov["year"] == 2019)].iloc[0]
    assert aceh["n_obs"] == aceh["n_workdays"] - 40 and aceh["longest_gap_workdays"] == 40
    s = C.gate1_summary(cov, obs, 2018, 2025)
    assert s["x"] == 33 and s["go"] and s["strict_all_years"] == 32
    assert [f["prov_code"] for f in s["failed"]] == ["14"]
    assert "gap terpanjang 60" in s["failed"][0]["reasons"][0]
