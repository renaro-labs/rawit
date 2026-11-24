# =============================================================================
#  MDE-H2-01 · Cleaning harga
# -----------------------------------------------------------------------------
#  Role    : MDE — Market Data Engineer (@dio)
#  Input   : data/interim/pihps_long.parquet, data/interim/sp2kp_long.parquet,
#            data/ref/provinces.csv (kolom pihps_name), configs/data/v1.yaml,
#            data/interim/calendar.csv (opsional; fallback tanggal Idulfitri di bawah)
#  Output  : data/interim/prices_clean.parquet   (skema kontrak `prices_clean`)
#            reports/qa/prices_clean.md + reports/qa/figures/prices_clean_*.png
#            reports/qa/sp2kp_crosscheck.csv
#  Handoff : MDE-H3-01
# =============================================================================
"""Cleaning harga PIHPS. Prinsip: flag != buang.

Urutan: map nama -> kode, dedup, validasi level, outlier deret (spike-and-revert),
pasca-Lebaran, carry-forward, available_at, tulis, validasi silang SP2KP, laporan QA.

Hanya dua hal yang membuat `price` = NaN: harga <= 0/kosong, dan titik spike-and-revert
di luar jendela pasca-Lebaran. Semua flag lain hanya menandai.

Catatan kebocoran: median/MAD memakai jendela TERPUSAT (melihat ke depan). Ini aman
karena flag hanya dipakai untuk membersihkan target/QA, bukan sebagai fitur model.
Dicatat di data card.

Pemakaian: ``python -m renaro.data.cleaning``
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import HOLDOUT_START, PROV_CODES, TABLE_COLUMNS, check_columns, check_unique

RAW_LONG = Path("data/interim/pihps_long.parquet")
SP2KP_LONG = Path("data/interim/sp2kp_long.parquet")
CALENDAR = Path("data/interim/calendar.csv")
PROVINCES = Path("data/ref/provinces.csv")
CONFIG = Path("configs/data/v1.yaml")
OUT = Path("data/interim/prices_clean.parquet")
QA_DIR = Path("reports/qa")
PLOT_PROVINCES = ("31", "32", "33", "35", "12")

DEFAULTS = {
    "commodity": "cabai_merah_keriting", "price_types": [1, 4],
    "min_price": 5000.0, "max_price": 250000.0,
    "window": 21, "k_mad": 5.0, "mad_scale": 1.0, "mad_floor": 0.02, "max_spike": 2,
    "carry_min": 10, "post_lebaran_days": 10, "max_nan_share": 0.01, "workday_share": 0.5,
    "sp2kp_start": "2024-02-01", "sp2kp_end": "2026-05-31", "sp2kp_max_diff": 0.15,
}

#: Fallback bila calendar.csv (MDE-H2-02) belum ada. Tanggal 1 Syawal penetapan pemerintah (Kemenag).
IDULFITRI = ("2017-06-25", "2018-06-15", "2019-06-05", "2020-05-24", "2021-05-13",
             "2022-05-02", "2023-04-22", "2024-04-10", "2025-03-31", "2026-03-21")

#: Baris rusak yang sudah diketahui di respons PIHPS (level 1 bernama "Dum" di 2021–2022).
#: Dibuang dan dihitung; nama lain yang tidak dikenal = error.
KNOWN_JUNK_NAMES = {"Dum"}

FLAG_COLS = ["flag_outlier", "flag_post_lebaran", "flag_carry_forward"]


# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
def load_config(path: Path = CONFIG) -> dict:
    cfg = dict(DEFAULTS)
    if not path.exists():
        print(f"[peringatan] {path} tidak ada; pakai default di kode", file=sys.stderr)
        return cfg
    try:
        import yaml
    except ImportError:
        print("[peringatan] pyyaml tidak terpasang; pakai default di kode (pip install pyyaml)", file=sys.stderr)
        return cfg
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    p, s = raw["prices"], raw["prices"]["series_outlier"]
    cfg.update({
        "commodity": p["commodity"], "price_types": list(p["price_types"]),
        "min_price": float(p["level_bounds_idr_per_kg"]["min"]), "max_price": float(p["level_bounds_idr_per_kg"]["max"]),
        "window": int(s["window_workdays"]), "k_mad": float(s["k_mad"]), "mad_scale": float(s["mad_scale"]),
        "mad_floor": float(s["mad_floor_log"]), "max_spike": int(s["max_spike_workdays"]),
        "carry_min": int(p["carry_forward_min_workdays"]), "post_lebaran_days": int(p["post_lebaran_days"]),
        "max_nan_share": float(p["max_nan_share"]), "workday_share": float(p["workday_share"]),
        "sp2kp_start": raw["sp2kp_crosscheck"]["start"], "sp2kp_end": raw["sp2kp_crosscheck"]["end"],
        "sp2kp_max_diff": float(raw["sp2kp_crosscheck"]["max_median_abs_diff"]),
    })
    return cfg


# ---------------------------------------------------------------------------
# Langkah 1–2: map + dedup
# ---------------------------------------------------------------------------
def map_provinces(raw: pd.DataFrame, provinces: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Nama mentah -> prov_code lewat kolom `pihps_name` (exact). Nama tak dikenal = error."""
    if "pihps_name" not in provinces.columns:
        raise SystemExit("provinces.csv tidak punya kolom pihps_name")
    lookup = dict(zip(provinces["pihps_name"].str.strip(), provinces["prov_code"].astype(str).str.zfill(2)))
    names = raw["prov_name_raw"].str.strip()
    junk = names.isin(KNOWN_JUNK_NAMES)
    unknown = sorted(set(names[~junk & ~names.isin(lookup)]))
    if unknown:
        raise SystemExit(f"Nama provinsi PIHPS tidak ter-map: {unknown}. Tambahkan ke pihps_name di provinces.csv.")
    out = raw[~junk].copy()
    out["prov_code"] = names[~junk].map(lookup)
    return out, {"junk_rows": int(junk.sum()), "junk_names": sorted(set(names[junk]))}


def deduplicate(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Kunci (date, prov_code, price_type). Nilai terakhir di urutan respons dipakai."""
    key = ["date", "prov_code", "price_type"]
    frame = frame.reset_index(drop=True)
    dup_mask = frame.duplicated(key, keep=False)
    conflicts = 0
    if dup_mask.any():
        conflicts = int((frame[dup_mask].groupby(key)["price_raw"].nunique(dropna=False) > 1).sum())
    out = frame.drop_duplicates(key, keep="last")
    return out, {"dup_rows": int(len(frame) - len(out)), "dup_conflicts": conflicts}


# ---------------------------------------------------------------------------
# Langkah 3: level
# ---------------------------------------------------------------------------
def flag_level(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    frame = frame.copy()
    frame["price_raw"] = frame["price_raw"].astype("float64")
    frame.loc[frame["price_raw"] <= 0, "price_raw"] = np.nan
    frame["price"] = frame["price_raw"]
    out_of_bounds = frame["price"].notna() & ~frame["price"].between(cfg["min_price"], cfg["max_price"])
    frame["flag_outlier"] = out_of_bounds
    frame["flag_level"] = out_of_bounds            # kolom bantu QA, dibuang sebelum tulis
    return frame


# ---------------------------------------------------------------------------
# Langkah 4: outlier deret (spike-and-revert) + pasca-Lebaran
# ---------------------------------------------------------------------------
def lebaran_dates(calendar_path: Path = CALENDAR) -> list[pd.Timestamp]:
    if calendar_path.exists():
        cal = pd.read_csv(calendar_path, parse_dates=["date"])
        if "days_to_lebaran" in cal.columns:
            found = cal.loc[cal["days_to_lebaran"] == 0, "date"].tolist()
            if found:
                return sorted(pd.Timestamp(d) for d in found)
    return [pd.Timestamp(d) for d in IDULFITRI]


def post_lebaran_mask(dates: pd.Series, lebaran: list[pd.Timestamp], days: int) -> pd.Series:
    mask = pd.Series(False, index=dates.index)
    for d in lebaran:
        mask |= dates.between(d, d + pd.Timedelta(days=days))
    return mask


def spike_and_revert(logp: np.ndarray, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Deret log harga valid (urut hari kerja) -> (deviasi, spike_and_revert)."""
    s = pd.Series(logp)
    w, half = cfg["window"], cfg["window"] // 2 + 1
    med = s.rolling(w, center=True, min_periods=half).median()
    mad = (s - med).abs().rolling(w, center=True, min_periods=half).median() * cfg["mad_scale"]
    mad = mad.clip(lower=cfg["mad_floor"])
    dev = ((s - med).abs() > cfg["k_mad"] * mad).fillna(False).to_numpy()
    sign = np.sign((s - med).fillna(0).to_numpy())
    spike = np.zeros(len(s), dtype=bool)
    i, n = 0, len(s)
    while i < n:
        if not dev[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and dev[j + 1] and sign[j + 1] == sign[i]:
            j += 1
        # Run deviasi pendek (<= max_spike) yang diapit titik normal di kiri dan kanan.
        if (j - i + 1) <= cfg["max_spike"] and i > 0 and j + 1 < n and not dev[i - 1] and not dev[j + 1]:
            spike[i:j + 1] = True
        i = j + 1
    return dev, spike


def flag_series(frame: pd.DataFrame, cfg: dict, lebaran: list[pd.Timestamp]) -> pd.DataFrame:
    frame = frame.sort_values(["price_type", "prov_code", "date"]).copy()
    frame["flag_post_lebaran"] = post_lebaran_mask(frame["date"], lebaran, cfg["post_lebaran_days"])
    frame["flag_spike"] = False
    frame["flag_deviation"] = False
    for _, idx in frame[frame["price"].notna()].groupby(["price_type", "prov_code"]).groups.items():
        dev, spike = spike_and_revert(np.log(frame.loc[idx, "price"].to_numpy()), cfg)
        frame.loc[idx, "flag_deviation"] = dev
        frame.loc[idx, "flag_spike"] = spike
    # Spike di jendela pasca-Lebaran dipertahankan (sinyal nyata), hanya diberi flag_post_lebaran.
    nan_it = frame["flag_spike"] & ~frame["flag_post_lebaran"]
    frame["flag_outlier"] = frame["flag_outlier"] | nan_it
    frame["flag_nan_spike"] = nan_it
    frame.loc[nan_it, "price"] = np.nan
    return frame


# ---------------------------------------------------------------------------
# Langkah 5: carry-forward
# ---------------------------------------------------------------------------
def flag_carry_forward(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Nilai identik >= carry_min hari kerja berturut-turut (pada baris berharga) -> flag."""
    frame = frame.sort_values(["price_type", "prov_code", "date"]).copy()
    frame["flag_carry_forward"] = False
    valid = frame[frame["price_raw"].notna()]
    for _, g in valid.groupby(["price_type", "prov_code"]):
        v = g["price_raw"].to_numpy()
        run_id = np.concatenate([[0], np.cumsum(v[1:] != v[:-1])])
        sizes = pd.Series(run_id).map(pd.Series(run_id).value_counts()).to_numpy()
        frame.loc[g.index[sizes >= cfg["carry_min"]], "flag_carry_forward"] = True
    return frame


# ---------------------------------------------------------------------------
# Langkah 7: available_at
# ---------------------------------------------------------------------------
def pihps_workdays(frame: pd.DataFrame, share: float) -> pd.DatetimeIndex:
    t1 = frame[(frame["price_type"] == 1) & frame["price_raw"].notna()]
    per_day = t1.groupby("date")["prov_code"].nunique()
    return pd.DatetimeIndex(per_day[per_day >= share * len(PROV_CODES)].index).sort_values()


def next_workday(dates: pd.Series, workdays: pd.DatetimeIndex) -> pd.Series:
    """Hari kerja PIHPS berikutnya (bukan date + 1 kalender). Setelah hari kerja terakhir: BDay+1."""
    arr = workdays.to_numpy()
    pos = np.searchsorted(arr, dates.to_numpy(), side="right")
    nxt = np.where(pos < len(arr), arr[np.minimum(pos, len(arr) - 1)], np.datetime64("NaT", "ns"))
    out = pd.Series(pd.to_datetime(nxt), index=dates.index)
    missing = out.isna()
    out[missing] = dates[missing] + pd.offsets.BDay(1)
    return out.dt.normalize()


# ---------------------------------------------------------------------------
# Langkah 6: validasi silang SP2KP
# ---------------------------------------------------------------------------
def crosscheck_sp2kp(clean: pd.DataFrame, sp2kp: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per provinsi: korelasi log-harga dan median |PIHPS - SP2KP| / SP2KP. Tidak mengubah target."""
    a = clean[(clean["price_type"] == 1) & clean["price"].notna()][["date", "prov_code", "price"]]
    b = sp2kp[sp2kp["price"].notna()][["date", "prov_code", "price", "is_aggregated"]].rename(columns={"price": "sp2kp"})
    b["date"] = pd.to_datetime(b["date"])
    m = a.merge(b, on=["date", "prov_code"])
    m = m[m["date"].between(pd.Timestamp(cfg["sp2kp_start"]), pd.Timestamp(cfg["sp2kp_end"]))]
    rows = []
    for code, g in m.groupby("prov_code"):
        diff = (g["price"] - g["sp2kp"]).abs() / g["sp2kp"]
        rows.append({"prov_code": code, "n_days": len(g),
                     "corr_log": float(np.corrcoef(np.log(g["price"]), np.log(g["sp2kp"]))[0, 1]),
                     "median_abs_diff_pct": float(diff.median()),
                     "median_ratio_pihps_sp2kp": float((g["price"] / g["sp2kp"]).median()),
                     "sp2kp_is_aggregated": bool(g["is_aggregated"].any())})
    out = pd.DataFrame(rows)
    out["over_threshold"] = out["median_abs_diff_pct"] > cfg["sp2kp_max_diff"]
    return out.sort_values("median_abs_diff_pct", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Tulis + QA
# ---------------------------------------------------------------------------
def finalize(frame: pd.DataFrame, cfg: dict, workdays: pd.DatetimeIndex) -> pd.DataFrame:
    out = frame.copy()
    out["commodity"] = cfg["commodity"]
    out["source"] = "pihps"
    out["is_observed"] = out["price"].notna()
    out["available_at"] = next_workday(out["date"], workdays)
    out["date"] = out["date"].astype("datetime64[ns]")
    out["available_at"] = out["available_at"].astype("datetime64[ns]")
    out["prov_code"] = out["prov_code"].astype(str)
    out["price_type"] = out["price_type"].astype("int64")
    for c in ["price_raw", "price"]:
        out[c] = out[c].astype("float64")
    for c in ["is_observed", *FLAG_COLS]:
        out[c] = out[c].astype(bool)
    cols = list(TABLE_COLUMNS["prices_clean"])
    return out[cols].sort_values(["date", "prov_code", "price_type"]).reset_index(drop=True)


def validate_clean(clean: pd.DataFrame) -> None:
    check_columns(clean, "prices_clean", allow_extra=False)
    check_unique(clean, "prices_clean")
    if clean["date"].max() >= pd.Timestamp(HOLDOUT_START):
        raise ValueError("Ada tanggal holdout di prices_clean!")
    if not set(clean["prov_code"]) <= set(PROV_CODES):
        raise ValueError(f"prov_code di luar kontrak: {sorted(set(clean['prov_code']) - set(PROV_CODES))}")
    if (clean["price"] <= 0).any() or (clean["price_raw"] <= 0).any():
        raise ValueError("Ada harga <= 0")
    if not (clean["available_at"] > clean["date"]).all():
        raise ValueError("available_at harus > date")


def write_plots(work: pd.DataFrame, qa_dir: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = qa_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    names = dict(zip(work["prov_code"], work["prov_name_raw"]))
    for code in PLOT_PROVINCES:
        g = work[(work["prov_code"] == code) & (work["price_type"] == 1)].sort_values("date")
        fig, ax = plt.subplots(figsize=(11, 3.6))
        ax.plot(g["date"], g["price_raw"] / 1000, lw=0.7, color="#5b6b7a", label="harga mentah")
        layers = [("flag_carry_forward", "#e6a700", "carry-forward (tetap)", 6),
                  ("flag_post_lebaran", "#2b8cbe", "pasca-Lebaran (tetap)", 8),
                  ("flag_level", "#7b3294", "di luar batas level (tetap)", 14),
                  ("flag_nan_spike", "#d7301f", "spike-and-revert (→ NaN)", 22)]
        for col, color, label, size in layers:
            p = g[g[col] & g["price_raw"].notna()]
            ax.scatter(p["date"], p["price_raw"] / 1000, s=size, color=color, zorder=3,
                       label=f"{label}: {len(p)}")
        ax.set_title(f"{code} {names.get(code, '')} — PIHPS tipe 1", fontsize=10)
        ax.set_ylabel("ribu Rp/kg")
        ax.legend(fontsize=7, loc="upper left", frameon=False)
        ax.grid(alpha=0.2)
        fig.tight_layout()
        path = fig_dir / f"prices_clean_{code}.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)
    return paths


def write_report(work: pd.DataFrame, clean: pd.DataFrame, xc: pd.DataFrame, stats: dict, cfg: dict,
                 plots: list[Path], qa_dir: Path) -> Path:
    names = dict(zip(work["prov_code"], work["prov_name_raw"]))
    per = (work.groupby(["prov_code", "price_type"])
               .agg(n=("date", "size"), observed=("price_raw", lambda s: int(s.notna().sum())),
                    level=("flag_level", "sum"), spike_nan=("flag_nan_spike", "sum"),
                    spike_kept_lebaran=("flag_spike", "sum"), post_lebaran=("flag_post_lebaran", "sum"),
                    carry=("flag_carry_forward", "sum"))
               .reset_index())
    per["spike_kept_lebaran"] -= per["spike_nan"]
    t1 = per[per["price_type"] == 1]
    t4 = per[per["price_type"] == 4]

    def table(df):
        head = "| Kode | Provinsi | Baris | Berharga | Level | Spike→NaN | Spike Lebaran (tetap) | Pasca-Lebaran | Carry-fwd |"
        lines = [head, "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for r in df.itertuples():
            lines.append(f"| {r.prov_code} | {names.get(r.prov_code, '')} | {r.n} | {r.observed} | {r.level} | "
                         f"{r.spike_nan} | {r.spike_kept_lebaran} | {r.post_lebaran} | {r.carry} |")
        tot = df[["n", "observed", "level", "spike_nan", "spike_kept_lebaran", "post_lebaran", "carry"]].sum()
        lines.append(f"| | **Total** | {tot.n} | {tot.observed} | {tot.level} | {tot.spike_nan} | "
                     f"{tot.spike_kept_lebaran} | {tot.post_lebaran} | {tot.carry} |")
        return "\n".join(lines)

    over = xc[xc["over_threshold"]]
    cf_rate = clean[clean["price_type"] == 1].groupby("prov_code")["flag_carry_forward"].mean().sort_values(ascending=False)
    top_cf = ", ".join(f"{c} {names.get(c, '')} ({v:.1%})" for c, v in cf_rate.head(3).items())
    xc_lines = ["| Kode | Provinsi | Hari | Korelasi log | Median \\|selisih\\| | Median PIHPS/SP2KP | SP2KP agregat |",
                "|---|---|---:|---:|---:|---:|:---:|"]
    for r in xc.itertuples():
        xc_lines.append(f"| {r.prov_code} | {names.get(r.prov_code, '')} | {r.n_days} | {r.corr_log:.3f} | "
                        f"{r.median_abs_diff_pct:.1%}{' ⚠' if r.over_threshold else ''} | {r.median_ratio_pihps_sp2kp:.3f} | "
                        f"{'ya' if r.sp2kp_is_aggregated else ''} |")
    n1, n4 = int((clean["price_type"] == 1).sum()), int((clean["price_type"] == 4).sum())
    cf1 = int(clean.loc[clean["price_type"] == 1, "flag_carry_forward"].sum())
    cf4 = int(clean.loc[clean["price_type"] == 4, "flag_carry_forward"].sum())
    nan_share = stats["nan_by_cleaning"] / stats["observed_raw"]
    verdict = "di bawah" if nan_share < cfg["max_nan_share"] else "**DI ATAS — eskalasi ke RL**"
    rp19 = stats["rp19000"]
    md = f"""# QA cleaning harga (MDE-H2-01)

- Input: `data/interim/pihps_long.parquet` → output `data/interim/prices_clean.parquet` ({len(clean):,} baris, skema kontrak `prices_clean`, 12 kolom)
- Kode: `src/renaro/data/cleaning.py`; parameter: `configs/data/v1.yaml`; dibuat ulang dengan `python -m renaro.data.cleaning`
- Rentang: {clean['date'].min().date()} .. {clean['date'].max().date()} (< holdout {HOLDOUT_START}); price_type {sorted(clean['price_type'].unique().tolist())}
- Tanggal Idulfitri: {stats['lebaran_source']}

## Ringkasan

| Item | Nilai |
|---|---|
| Baris masuk / dibuang sebagai baris rusak ({', '.join(stats['junk_names']) or '-'}) | {stats['rows_in']:,} / {stats['junk_rows']:,} |
| Nama provinsi tak ter-map | 0 (nama baru akan menghentikan proses) |
| Duplikat kunci (date, prov_code, price_type) / yang nilainya berbeda | {stats['dup_rows']} / {stats['dup_conflicts']} |
| Harga ≤ 0 → NaN | {stats['nonpositive']} |
| Titik berharga sebelum cleaning | {stats['observed_raw']:,} |
| **Titik yang di-NaN-kan cleaning (spike-and-revert)** | **{stats['nan_by_cleaning']:,} ({nan_share:.3%}) — {verdict} ambang {cfg['max_nan_share']:.0%}** |
| Spike di jendela pasca-Lebaran (dipertahankan) | {stats['spike_kept']:,} |
| flag_outlier total (level + spike) | {int(clean['flag_outlier'].sum()):,} |
| flag_post_lebaran | {int(clean['flag_post_lebaran'].sum()):,} |
| flag_carry_forward — tipe 1 / tipe 4 | {cf1:,} ({cf1 / max(n1, 1):.1%}) / {cf4:,} ({cf4 / max(n4, 1):.1%}) |

Aturan: median bergulir {cfg['window']} hari kerja (terpusat) pada log harga per (provinsi, tipe); deviasi bila |log p − median| > {cfg['k_mad']:g}·MAD (MAD mentah, batas bawah {cfg['mad_floor']:g}); spike-and-revert = run deviasi searah ≤ {cfg['max_spike']} hari kerja yang diapit titik normal. Hanya spike-and-revert di luar jendela Idulfitri..+{cfg['post_lebaran_days']} hari yang di-NaN-kan. Batas level [{cfg['min_price']:,.0f}, {cfg['max_price']:,.0f}] Rp/kg hanya diberi flag (perlu konfirmasi RL). `available_at` = hari kerja PIHPS berikutnya (tanggal dengan laporan ≥ {cfg['workday_share']:.0%} provinsi).

Catatan carry-forward: tipe 4 (produsen) hampir selalu berupa nilai yang sama berminggu-minggu, sehingga sebagian besar barisnya ditandai; ini sifat sumber, bukan galat. Untuk tipe 1, provinsi dengan proporsi tertinggi: {top_cf}. Perlakuan diputuskan RL di protokol; tidak ada titik yang dihapus karena flag ini.

**Kasus audit brief §7.1 (Rp19.000 nasional, 1 Feb 2022): dilewati atas keputusan tim (2026-11-25).** Data 2022 tetap dipakai utuh. Catatan: {rp19}

## Validasi silang SP2KP ({cfg['sp2kp_start']} .. {cfg['sp2kp_end']}, tipe 1)

SP2KP hanya pembanding; target tidak diubah. Provinsi dengan median |selisih| > {cfg['sp2kp_max_diff']:.0%}: **{len(over)}** {('(' + ', '.join(f"{r.prov_code} {names.get(r.prov_code, '')}" for r in over.itertuples()) + ')') if len(over) else ''}. Median korelasi log-harga: {xc['corr_log'].median():.3f}. Tabel lengkap juga di `reports/qa/sp2kp_crosscheck.csv`.

{chr(10).join(xc_lines)}

## Plot contoh (tipe 1)

{chr(10).join(f"![{p.stem}](figures/{p.name})" for p in plots)}

## Flag per provinsi — tipe 1 (pasar tradisional, target)

{table(t1)}

## Flag per provinsi — tipe 4 (produsen)

{table(t4)}
"""
    path = qa_dir / "prices_clean.md"
    path.write_text(md, encoding="utf-8")
    xc.assign(prov_name=xc["prov_code"].map(names)).to_csv(qa_dir / "sp2kp_crosscheck.csv", index=False)
    return path


def rp19000_check(work: pd.DataFrame) -> str:
    d = pd.Timestamp("2022-02-01")
    day = work[(work["date"] == d) & (work["price_type"] == 1)]
    near = day[day["price_raw"].between(17_000, 21_000)]
    if day["price_raw"].notna().sum() == 0:
        return ("pada 2022-02-01 semua provinsi bernilai \"-\" (Imlek) dan baris nasional juga \"-\" di unduhan "
                "2026-11-24, jadi nilai Rp19.000 tidak muncul di level provinsi. Aturan spike-and-revert diuji "
                "dengan kasus sintetis yang sama di `tests/test_prices_clean.py`.")
    if near.empty:
        return "tidak ada provinsi bernilai sekitar Rp19.000 pada 2022-02-01."
    flagged = near["flag_nan_spike"].all()
    return f"{len(near)} provinsi bernilai sekitar Rp19.000; {'semua tertandai' if flagged else 'TIDAK semua tertandai'}."


def run(raw_path: Path, sp2kp_path: Path, provinces_path: Path, out: Path, qa_dir: Path,
        cfg: dict | None = None, calendar_path: Path = CALENDAR) -> tuple[pd.DataFrame, dict]:
    cfg = cfg or load_config()
    raw = pd.read_parquet(raw_path)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw[raw["price_type"].isin(cfg["price_types"])]
    provinces = pd.read_csv(provinces_path, dtype=str)
    mapped, mstats = map_provinces(raw, provinces)
    dedup, dstats = deduplicate(mapped)
    nonpos = int((dedup["price_raw"] <= 0).sum())
    work = flag_level(dedup, cfg)
    lebaran = lebaran_dates(calendar_path)
    work = flag_series(work, cfg, lebaran)
    work = flag_carry_forward(work, cfg)
    workdays = pihps_workdays(work, cfg["workday_share"])
    clean = finalize(work, cfg, workdays)
    validate_clean(clean)
    stats = {"rows_in": len(raw), **mstats, **dstats, "nonpositive": nonpos,
             "observed_raw": int(work["price_raw"].notna().sum()),
             "nan_by_cleaning": int(work["flag_nan_spike"].sum()),
             "spike_kept": int((work["flag_spike"] & ~work["flag_nan_spike"]).sum()),
             "lebaran_source": (f"`{calendar_path.as_posix()}`" if calendar_path.exists()
                                else "fallback di kode (calendar.csv MDE-H2-02 belum ada): " + ", ".join(IDULFITRI)),
             "rp19000": rp19000_check(work)}
    out.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(out, index=False)
    qa_dir.mkdir(parents=True, exist_ok=True)
    xc = crosscheck_sp2kp(clean, pd.read_parquet(sp2kp_path), cfg) if sp2kp_path.exists() else pd.DataFrame(
        columns=["prov_code", "n_days", "corr_log", "median_abs_diff_pct", "median_ratio_pihps_sp2kp",
                 "sp2kp_is_aggregated", "over_threshold"])
    plots = write_plots(work, qa_dir)
    write_report(work, clean, xc, stats, cfg, plots, qa_dir)
    stats["nan_share"] = stats["nan_by_cleaning"] / stats["observed_raw"]
    stats["sp2kp_over"] = xc.loc[xc["over_threshold"], "prov_code"].tolist() if len(xc) else []
    return clean, stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Cleaning harga PIHPS (MDE-H2-01)")
    ap.add_argument("--raw", type=Path, default=RAW_LONG)
    ap.add_argument("--sp2kp", type=Path, default=SP2KP_LONG)
    ap.add_argument("--provinces", type=Path, default=PROVINCES)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--qa-dir", type=Path, default=QA_DIR)
    args = ap.parse_args(argv)
    cfg = load_config()
    clean, s = run(args.raw, args.sp2kp, args.provinces, args.out, args.qa_dir, cfg)
    print(f"[ok] {args.out} baris={len(clean):,} {clean['date'].min().date()}..{clean['date'].max().date()}")
    print(f"     di-NaN-kan cleaning: {s['nan_by_cleaning']:,} dari {s['observed_raw']:,} ({s['nan_share']:.3%}); "
          f"baris rusak dibuang: {s['junk_rows']}; duplikat: {s['dup_rows']}")
    print(f"     SP2KP median |selisih| > {cfg['sp2kp_max_diff']:.0%}: {s['sp2kp_over'] or 'tidak ada'}")
    print(f"[ok] {args.qa_dir / 'prices_clean.md'}")
    if s["nan_share"] >= cfg["max_nan_share"]:
        print(f"[ESKALASI RL] proporsi NaN {s['nan_share']:.2%} >= {cfg['max_nan_share']:.0%}", file=sys.stderr)


if __name__ == "__main__":
    main()
