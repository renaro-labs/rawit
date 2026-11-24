# =============================================================================
#  MDE-H1-03 · Laporan cakupan per provinsi-tahun
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer (@dio)
#  Input   : data/interim/pihps_long.parquet (MDE-H1-01)
#  Output  : reports/qa/coverage_pihps.csv
#            reports/qa/coverage_pihps.md
#            reports/qa/coverage_heatmap.png
#  Handoff : RL (kriteria data Gate 1), RL-H1-01 (node yang dievaluasi)
# =============================================================================
"""Cakupan harga PIHPS tipe 1 per (provinsi, tahun). Angka ini dipakai RL untuk Gate 1.

Definisi:
- Laporan      = baris tipe 1 dengan harga valid (price_raw bukan NaN; "-" tidak dihitung).
- Hari kerja PIHPS = tanggal dengan laporan dari >= 50% dari 34 provinsi kontrak.
- n_obs        = hari kerja PIHPS di tahun itu yang punya laporan provinsi tsb.
- coverage     = n_obs / n_workdays (tidak dibulatkan di CSV).
- longest_gap_workdays = rangkaian hari kerja PIHPS berurutan terpanjang tanpa laporan, dalam tahun itu.
- Gate 1 (brief §10.1): provinsi lolos bila coverage >= 90% pada >= 5 tahun dalam 2018–2025;
  data lolos bila jumlah provinsi lolos >= 20.

Pemakaian: ``python -m renaro.data.coverage``
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import HOLDOUT_START, PROV_CODES, PROVINCES, prov_code_of

PRICES = Path("data/interim/pihps_long.parquet")
COVERAGE_CSV = Path("reports/qa/coverage_pihps.csv")
COVERAGE_MD = Path("reports/qa/coverage_pihps.md")
HEATMAP = Path("reports/qa/coverage_heatmap.png")
WORKDAY_SHARE = 0.50
MIN_COVERAGE = 0.90          # brief v2 §10.1
MIN_YEARS = 5
MIN_PROVINCES = 20
CSV_COLUMNS = ["prov_code", "prov_name", "year", "n_workdays", "n_obs", "coverage", "longest_gap_workdays"]
PROV_NAME = dict(PROVINCES)


def _code_or_none(name: str) -> str | None:
    try:
        return prov_code_of(name)
    except KeyError:
        return None


def load_type1(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Tipe 1, harga valid, nama -> prov_code. Kembalikan juga nama yang dibuang (mis. 'Dum')."""
    prices = pd.read_parquet(path)
    prices["date"] = pd.to_datetime(prices["date"])
    if prices["date"].max() >= pd.Timestamp(HOLDOUT_START):
        raise SystemExit("File interim memuat tanggal holdout!")
    t1 = prices[prices["price_type"] == 1].copy()
    t1["prov_code"] = t1["prov_name_raw"].map(_code_or_none)
    dropped = sorted(t1.loc[t1["prov_code"].isna(), "prov_name_raw"].unique())
    obs = t1[t1["prov_code"].notna() & t1["price_raw"].notna()]
    return obs[["date", "prov_code"]].drop_duplicates(), dropped


def pihps_workdays(obs: pd.DataFrame, share: float = WORKDAY_SHARE) -> pd.DatetimeIndex:
    """Tanggal dengan laporan untuk >= share x 34 provinsi."""
    per_day = obs.groupby("date")["prov_code"].nunique()
    return pd.DatetimeIndex(per_day[per_day >= share * len(PROV_CODES)].index).sort_values()


def _longest_run(flags: np.ndarray) -> int:
    best = cur = 0
    for missing in flags:
        cur = cur + 1 if missing else 0
        best = max(best, cur)
    return best


def coverage_table(obs: pd.DataFrame, workdays: pd.DatetimeIndex) -> pd.DataFrame:
    wd = pd.Series(workdays, name="date")
    has = set(zip(obs["date"], obs["prov_code"]))
    rows = []
    for year, days in wd.groupby(wd.dt.year):
        days = days.to_numpy()
        for code in PROV_CODES:
            present = np.array([(pd.Timestamp(d), code) in has for d in days])
            rows.append({
                "prov_code": code, "prov_name": PROV_NAME[code], "year": int(year),
                "n_workdays": int(len(days)), "n_obs": int(present.sum()),
                "coverage": float(present.mean()) if len(days) else np.nan,
                "longest_gap_workdays": _longest_run(~present),
            })
    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def gate1_summary(cov: pd.DataFrame, obs: pd.DataFrame, start_year: int, end_year: int) -> dict:
    window = cov[cov["year"].between(start_year, end_year)]
    n_years = end_year - start_year + 1
    good = window.assign(ok=window["coverage"] >= MIN_COVERAGE)
    per_prov = good.groupby("prov_code").agg(years_ok=("ok", "sum"), min_cov=("coverage", "min"),
                                             max_gap=("longest_gap_workdays", "max")).reset_index()
    per_prov["pass"] = per_prov["years_ok"] >= MIN_YEARS
    first_obs = obs.groupby("prov_code")["date"].min()
    failed = []
    for _, r in per_prov[~per_prov["pass"]].iterrows():
        bad = good[(good["prov_code"] == r["prov_code"]) & ~good["ok"]].sort_values("year")
        reasons = []
        late = first_obs.get(r["prov_code"])
        if late is not None and late > pd.Timestamp(f"{start_year}-01-31"):
            reasons.append(f"mulai terlambat (laporan pertama {late.date()})")
        for _, b in bad.iterrows():
            reasons.append(f"{b['year']}: {b['coverage']:.1%}, gap terpanjang {b['longest_gap_workdays']} hari kerja")
        failed.append({"prov_code": r["prov_code"], "prov_name": PROV_NAME[r["prov_code"]],
                       "years_ok": int(r["years_ok"]), "reasons": reasons})
    x = int(per_prov["pass"].sum())
    strict = int((per_prov["years_ok"] == n_years).sum())
    return {"x": x, "n": len(PROV_CODES), "threshold": MIN_PROVINCES, "go": x >= MIN_PROVINCES,
            "strict_all_years": strict, "n_years": n_years, "per_prov": per_prov, "failed": failed,
            "start_year": start_year, "end_year": end_year, "first_obs": first_obs}


def write_heatmap(cov: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    mat = cov.pivot(index="prov_code", columns="year", values="coverage").reindex(list(PROV_CODES))
    labels = [f"{c} {PROV_NAME[c]}" for c in mat.index]
    bounds = [0, 0.5, 0.8, 0.9, 0.95, 1.0001]
    cmap = ListedColormap(["#b2182b", "#ef8a62", "#fddbc7", "#a6dba0", "#1b7837"])
    fig, ax = plt.subplots(figsize=(9, 12))
    im = ax.imshow(mat.to_numpy(), aspect="auto", cmap=cmap, norm=BoundaryNorm(bounds, cmap.N))
    ax.set_xticks(range(mat.shape[1]), [str(y) for y in mat.columns])
    ax.set_yticks(range(mat.shape[0]), labels, fontsize=8)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.iat[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{np.floor(v * 1000) / 10:.1f}".rstrip("0").rstrip("."), ha="center", va="center", fontsize=6.5,
                        color="white" if v < 0.5 or v >= 0.95 else "black")
    partial = [str(y) for y in mat.columns if y in (2017, 2026)]
    ax.set_title("Cakupan harga PIHPS tipe 1 (% hari kerja PIHPS)\n"
                 f"ambang Gate 1: >= 90%; {', '.join(partial)} = tahun parsial", fontsize=10)
    cbar = fig.colorbar(im, ax=ax, ticks=[0.25, 0.65, 0.85, 0.925, 0.975], fraction=0.03)
    cbar.ax.set_yticklabels(["<50%", "50–80%", "80–90%", "90–95%", ">=95%"], fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_markdown(cov: pd.DataFrame, s: dict, workdays: pd.DatetimeIndex, dropped: list[str],
                   src: Path, path: Path) -> None:
    w = cov[cov["year"].between(s["start_year"], s["end_year"])]
    table = w.pivot(index="prov_code", columns="year", values="coverage").reindex(list(PROV_CODES))
    pp = s["per_prov"].set_index("prov_code")
    head = "| Kode | Provinsi | " + " | ".join(str(y) for y in table.columns) + " | Tahun ≥90% | Lolos |"
    sep = "|---|---|" + "---:|" * len(table.columns) + "---:|:---:|"
    lines = [head, sep]
    for code, row in table.iterrows():
        cells = " | ".join(f"{v * 100:.1f}" for v in row)
        lines.append(f"| {code} | {PROV_NAME[code]} | {cells} | {int(pp.at[code, 'years_ok'])}/{s['n_years']} | "
                     f"{'✓' if pp.at[code, 'pass'] else '✗'} |")
    per_year_wd = pd.Series(workdays.year).value_counts().sort_index()
    verdict = "memenuhi" if s["go"] else "TIDAK memenuhi"
    failed = (["Tidak ada provinsi yang gagal."] if not s["failed"] else
              [f"- **{f['prov_code']} {f['prov_name']}** ({f['years_ok']}/{s['n_years']} tahun ≥90%): "
               + "; ".join(f["reasons"]) for f in s["failed"]])
    first_obs = s["first_obs"]
    w17 = cov[(cov["year"] == 2017) & (cov["coverage"] < MIN_COVERAGE)].sort_values("coverage")
    warmup = ("Semua provinsi ≥ 90% pada 2017." if w17.empty else
              "Provinsi di bawah 90% pada Jul–Des 2017 (tidak memengaruhi Gate 1; relevan untuk jendela lag "
              "60 hari kerja di awal 2018):\n\n" + "\n".join(
                  f"- {r.prov_code} {r.prov_name}: {r.coverage:.1%}, gap terpanjang {r.longest_gap_workdays} hari kerja, "
                  f"laporan pertama {first_obs[r.prov_code].date()}" for r in w17.itertuples()))
    weakest = cov[cov["year"].between(s["start_year"], s["end_year"])].nsmallest(5, "coverage")
    md = f"""# Cakupan harga PIHPS per provinsi-tahun (MDE-H1-03)

- Sumber: `{src.as_posix()}` (tipe 1, pasar tradisional, Cabai Merah Keriting), dibuat oleh `src/renaro/data/coverage.py`
- Rentang data: {workdays.min().date()} .. {workdays.max().date()} (< holdout 2026-06-01)
- Definisi hari kerja PIHPS: tanggal dengan harga valid dari ≥ 50% dari 34 provinsi (≥ 17). Total {len(workdays)} hari kerja.
- Laporan = harga valid; nilai "-" tidak dihitung. Baris di luar 34 provinsi kontrak dibuang: {dropped or 'tidak ada'}.
- Kriteria Gate 1 (brief §10.1): cakupan ≥ 90% pada ≥ {MIN_YEARS} tahun dalam {s['start_year']}–{s['end_year']}; ambang {MIN_PROVINCES} provinsi.

## Kesimpulan

**{s['x']} dari {s['n']} provinsi memenuhi kriteria data Gate 1 (ambang {s['threshold']}).** Data {verdict} syarat Gate 1.

Versi ketat (≥ 90% di **semua** {s['n_years']} tahun {s['start_year']}–{s['end_year']}): {s['strict_all_years']} dari {s['n']} provinsi.

## Provinsi yang gagal

{chr(10).join(failed)}

## Cakupan (%) per provinsi-tahun, {s['start_year']}–{s['end_year']}

{chr(10).join(lines)}

Lima sel terendah: {", ".join(f"{r.prov_code} {r.prov_name} {r.year} ({r.coverage:.1%}, gap {r.longest_gap_workdays})" for r in weakest.itertuples())}.

## Catatan 2017 (periode pemanasan lag, Jul–Des)

{warmup}

Hari kerja PIHPS per tahun: {", ".join(f"{y}: {n}" for y, n in per_year_wd.items())}. Tahun 2017 (mulai Juli) dan 2026 (s/d Mei) parsial; keduanya ada di CSV tetapi tidak dihitung untuk Gate 1.

Heatmap: `reports/qa/coverage_heatmap.png`. Angka lengkap tanpa pembulatan: `reports/qa/coverage_pihps.csv`.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Laporan cakupan PIHPS (MDE-H1-03)")
    ap.add_argument("--prices", type=Path, default=PRICES)
    ap.add_argument("--start-year", type=int, default=2018)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--out-dir", type=Path, default=COVERAGE_CSV.parent)
    args = ap.parse_args(argv)

    obs, dropped = load_type1(args.prices)
    workdays = pihps_workdays(obs)
    cov = coverage_table(obs, workdays)
    s = gate1_summary(cov, obs, args.start_year, args.end_year)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cov.to_csv(args.out_dir / COVERAGE_CSV.name, index=False)
    write_markdown(cov, s, workdays, dropped, args.prices, args.out_dir / COVERAGE_MD.name)
    write_heatmap(cov, args.out_dir / HEATMAP.name)
    print(f"{s['x']} dari {s['n']} provinsi memenuhi kriteria data Gate 1 (ambang {s['threshold']}) -> "
          f"{'GO' if s['go'] else 'NO-GO'} data; ketat (semua tahun): {s['strict_all_years']}")
    for f in s["failed"]:
        print(f"  gagal: {f['prov_code']} {f['prov_name']}: {'; '.join(f['reasons'])}")
    print(f"[ok] {args.out_dir / COVERAGE_CSV.name}, {COVERAGE_MD.name}, {HEATMAP.name}")


if __name__ == "__main__":
    main()
