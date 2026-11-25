"""CGS-H4-02: diagnostic lead-lag between source rainfall and destination prices.

This is a predictive-dependency diagnostic, not evidence of physical supply
flow. It uses only the O3 training period (<= 2024-06-30), never holdout.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from renaro.climate.pentad import pentad_end
from renaro.contract import PROV_CODES, PROV_NAMES

PHASES = ("el_nino", "la_nina", "neutral")
LAGS = tuple(range(13))
MIN_OBS = 30
PHASE_MAP = {
    "el_nino": "el_nino", "elnino": "el_nino", "el-nino": "el_nino",
    "la_nina": "la_nina", "lanina": "la_nina", "la-nina": "la_nina",
    "neutral": "neutral",
}


def normalize_phase(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map(PHASE_MAP).fillna("neutral")


def pentadize(panel: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    """Aggregate prices/rain/regimes to pentads.

    Required panel columns: date, prov_code, price, is_observed,
    rain_pentad_anom. Required regime columns: date, prov_code, enso_phase,
    is_dry.
    """
    need_p = {"date", "prov_code", "price", "is_observed", "rain_pentad_anom"}
    need_r = {"date", "prov_code", "enso_phase", "is_dry"}
    mp = need_p - set(panel.columns)
    mr = need_r - set(regimes.columns)
    if mp:
        raise ValueError(f"panel kolom hilang: {sorted(mp)}")
    if mr:
        raise ValueError(f"regime kolom hilang: {sorted(mr)}")
    p = panel[["date", "prov_code", "price", "is_observed", "rain_pentad_anom"]].copy()
    p["date"] = pd.to_datetime(p["date"]).astype("datetime64[ns]")
    p["prov_code"] = p["prov_code"].astype(str).str.zfill(2)
    r = regimes[["date", "prov_code", "enso_phase", "is_dry"]].copy()
    r["date"] = pd.to_datetime(r["date"]).astype("datetime64[ns]")
    r["prov_code"] = r["prov_code"].astype(str).str.zfill(2)
    r["enso_phase"] = normalize_phase(r["enso_phase"])
    p = p.merge(r, on=["date", "prov_code"], how="left", validate="many_to_one")
    if p["enso_phase"].isna().any():
        raise ValueError("regime_labels tidak lengkap untuk tanggal panel")
    p["pentad"] = p["date"].map(pentad_end)
    p["is_dry"] = p["is_dry"].fillna(False).astype(bool)
    obs = p[p["is_observed"].astype(bool) & p["price"].notna() & (p["price"] > 0)].copy()
    obs["log_price"] = np.log(obs["price"].astype(float))
    price = (
        obs.groupby(["prov_code", "pentad"], as_index=False)
        .agg(log_price=("log_price", "mean"), n_price=("log_price", "size"))
        .sort_values(["prov_code", "pentad"])
    )
    price["delta_log"] = price.groupby("prov_code")["log_price"].diff()
    meta = (
        p.groupby(["prov_code", "pentad"], as_index=False)
        .agg(rain_anom=("rain_pentad_anom", "mean"),
             enso_phase=("enso_phase", "first"),
             is_dry=("is_dry", "max"))
    )
    out = price.merge(meta, on=["prov_code", "pentad"], how="left", validate="one_to_one")
    out = out.sort_values(["prov_code", "pentad"]).reset_index(drop=True)
    return out


def edges_from_mask(mask: np.ndarray) -> list[tuple[str, str]]:
    """Return (origin, dest) for mask[dest, origin] == 1, contract order."""
    m = np.asarray(mask)
    if m.shape != (len(PROV_CODES), len(PROV_CODES)):
        raise ValueError(f"mask shape {m.shape} != {(len(PROV_CODES), len(PROV_CODES))}")
    return [(PROV_CODES[origin], PROV_CODES[dest])
            for dest, origin in zip(*np.where(m != 0))]


def bh_fdr(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values, NaNs preserved."""
    p = np.asarray(pvalues, dtype=float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    vals = p[ok]
    order = np.argsort(vals)
    ranked = vals[order] * len(vals) / np.arange(1, len(vals) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(ranked)
    out[order] = np.clip(ranked, 0, 1)
    q[ok] = out
    return q


def correlation_table(
    pentad: pd.DataFrame,
    edges: list[tuple[str, str]],
    *,
    lags: tuple[int, ...] = LAGS,
    min_obs: int = MIN_OBS,
) -> pd.DataFrame:
    rain = pentad.pivot(index="pentad", columns="prov_code", values="rain_anom").sort_index()
    ret = pentad.pivot(index="pentad", columns="prov_code", values="delta_log").sort_index()
    dry = pentad.pivot(index="pentad", columns="prov_code", values="is_dry").sort_index()
    phase = (pentad.groupby("pentad")["enso_phase"]
             .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "neutral"))
    rows = []
    name = dict(zip(PROV_CODES, PROV_NAMES))
    for ph in PHASES:
        phase_mask = phase.eq(ph)
        for dry_origin in (True, False):
            for origin, dest in edges:
                if origin not in rain.columns or dest not in ret.columns:
                    continue
                dry_mask = dry[origin].fillna(False).astype(bool).eq(dry_origin) if origin in dry else pd.Series(False, index=rain.index)
                base_mask = phase_mask & dry_mask
                for lag in lags:
                    x = rain[origin].shift(lag)
                    y = ret[dest]
                    mask = base_mask & x.notna() & y.notna()
                    if int(mask.sum()) < min_obs:
                        continue
                    xv = x[mask].to_numpy(dtype=float)
                    yv = y[mask].to_numpy(dtype=float)
                    if np.nanstd(xv) == 0 or np.nanstd(yv) == 0:
                        continue
                    corr, p = pearsonr(xv, yv)
                    rows.append({
                        "origin": origin, "origin_name": name.get(origin, origin),
                        "dest": dest, "dest_name": name.get(dest, dest),
                        "phase": ph, "dry_origin": bool(dry_origin),
                        "lag": int(lag), "corr": float(corr), "p": float(p),
                        "n": int(mask.sum()),
                    })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["q"] = bh_fdr(frame["p"].to_numpy())
    frame["significant"] = frame["q"] < 0.05
    frame["abs_corr"] = frame["corr"].abs()
    return frame.sort_values(["origin", "dest", "phase", "dry_origin", "lag"]).reset_index(drop=True)


def peak_table(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges.copy()
    keys = ["origin", "dest", "phase", "dry_origin"]
    idx = edges.groupby(keys)["abs_corr"].idxmax()
    return edges.loc[idx].sort_values("abs_corr", ascending=False).reset_index(drop=True)


def write_figures(peaks: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    hist = out_dir / "fig_peak_lag_hist.png"
    sig = peaks[peaks.get("significant", False).astype(bool)] if "significant" in peaks else peaks
    data = (sig if len(sig) else peaks)["lag"].to_numpy()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(data, bins=np.arange(-0.5, 13.5, 1), color="#2f7d5b", edgecolor="white")
    ax.set_xlabel("peak lag (pentad)")
    ax.set_ylabel("jumlah edge/grup")
    ax.set_title("Distribusi lag puncak — rain → price (train O3)")
    fig.tight_layout()
    fig.savefig(hist, dpi=140)
    plt.close(fig)

    top = peaks.head(6).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = [f"{r.origin}->{r.dest} ({r.phase}{', kering' if r.dry_origin else ', tidak kering'})"
              for r in top.itertuples(index=False)]
    colors = ["#b7791f" if r.dry_origin else "#2f7d5b" for r in top.itertuples(index=False)]
    ax.barh(labels, top["corr"].to_numpy(), color=colors)
    ax.axvline(0, color="#444", linewidth=0.8)
    ax.set_xlabel("korelasi pada lag puncak")
    ax.set_title("Top 6 edge — korelasi hujan asal vs Δlog harga tujuan")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_top_edges.png", dpi=140)
    plt.close(fig)
    return hist, out_dir / "fig_top_edges.png"


def summary_markdown(edges: pd.DataFrame, peaks: pd.DataFrame) -> str:
    n_edges = int(edges[["origin", "dest"]].drop_duplicates().shape[0]) if not edges.empty else 0
    n_tests = len(edges)
    n_sig = int(edges["significant"].sum()) if "significant" in edges else 0
    sig_peaks = peaks[peaks["significant"].astype(bool)] if "significant" in peaks else peaks.iloc[0:0]
    top = peaks.head(1)
    top_text = "tidak ada"
    if len(top):
        r = top.iloc[0]
        top_text = f"{r['origin']}->{r['dest']} ({r['phase']}, lag {int(r['lag'])}, r={r['corr']:.3f}, q={r['q']:.4f})"
    if len(sig_peaks):
        second = f"Median lag puncak pada uji signifikan adalah {float(sig_peaks['lag'].median()):.1f} pentad; edge terkuat: {top_text}."
    else:
        second = f"Tidak ada uji yang lolos q<0.05 setelah BH-FDR; korelasi terkuat adalah {top_text} dan masih deskriptif."
    return "\n".join([
        "# CGS-H4-02 — Diagnostik lead-lag hujan asal → harga",
        "",
        f"Diagnostik memakai {n_edges} edge BPS dan {n_tests:,} uji korelasi pada data latih O3 (≤ 2024-06-30); {n_sig:,} uji signifikan q<0.05 (BH-FDR).",
        second,
        "Analisis dipisah per fase ENSO (El Niño/La Niña/netral) dan asal kering vs tidak, dengan lag 0–12 pentad.",
        "Hasil ini adalah dependensi prediktif, bukan bukti arus pasokan fisik; interpretasi kausal memerlukan validasi tambahan.",
        "Output lengkap: `leadlag_edges.csv`, `leadlag_peak.csv`, `fig_peak_lag_hist.png`, dan `fig_top_edges.png`; hanya data latih, tanpa holdout.",
        "",
    ])
