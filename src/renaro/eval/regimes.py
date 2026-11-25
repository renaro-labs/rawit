"""H4-01: regime-aware evaluation splits and filtering.

The evaluation split tables are the single source of truth for all models:
`date, prov_code, is_target_observed, enso_phase, is_dry, is_extreme_rain,
is_normal, label_primary, episode_id`.

`filter()` is intentionally small and stable so MLE can use the exact same
row subset for every model. It only joins on (date, prov_code), filters the
requested regime, and keeps target-observed rows by default.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from renaro.contract import HOLDOUT_START, PROJECT_ROOT, parse_range
from renaro.eval.splits import load_global_config

REGIMES = ("dry", "extreme_wet", "el_nino", "la_nina", "normal")
SPLIT_COLUMNS = [
    "date", "prov_code", "is_target_observed", "enso_phase", "is_dry",
    "is_extreme_rain", "is_normal", "label_primary", "episode_id",
]
DEFAULT_SPLITS_DIR = PROJECT_ROOT / "data/processed/eval_splits"


def split_path(origin: str, part: str, splits_dir: Path | str = DEFAULT_SPLITS_DIR) -> Path:
    if origin == "HOLDOUT":
        raise PermissionError("HOLDOUT tidak boleh dipakai untuk eval_splits H4-01")
    if part not in ("val", "test"):
        raise ValueError("part harus 'val' atau 'test'")
    if origin not in ("O1", "O2", "O3"):
        raise ValueError(f"origin tidak dikenal: {origin}")
    return Path(splits_dir) / f"{origin}_{part}.parquet"


def load_split(origin: str, part: str, splits_dir: Path | str = DEFAULT_SPLITS_DIR) -> pd.DataFrame:
    path = split_path(origin, part, splits_dir)
    if not path.is_file():
        raise FileNotFoundError(f"eval split belum dibuat: {path}")
    frame = pd.read_parquet(path)
    missing = set(SPLIT_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: kolom hilang {sorted(missing)}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).astype("datetime64[ns]")
    frame["prov_code"] = frame["prov_code"].astype(str).str.zfill(2)
    if (frame["date"] >= pd.Timestamp(HOLDOUT_START)).any():
        raise ValueError(f"{path}: berisi tanggal holdout")
    return frame


def filter(
    preds: pd.DataFrame,
    origin: str,
    part: str,
    regime: str,
    *,
    splits_dir: Path | str = DEFAULT_SPLITS_DIR,
    observed_only: bool = True,
) -> pd.DataFrame:
    """Return predictions for one origin/part/regime.

    The result contains the prediction columns plus the split metadata. Rows
    without an observed target are dropped by default; pass observed_only=False
    for diagnosis. This function does not know about model names or horizons.
    """
    if regime not in REGIMES:
        raise ValueError(f"regime tidak dikenal: {regime!r}; pilih {REGIMES}")
    if "date" not in preds.columns or "prov_code" not in preds.columns:
        raise ValueError("preds wajib memiliki kolom date dan prov_code")
    split = load_split(origin, part, splits_dir)
    left = preds.copy()
    left["date"] = pd.to_datetime(left["date"]).astype("datetime64[ns]")
    left["prov_code"] = left["prov_code"].astype(str).str.zfill(2)
    merged = left.merge(split, on=["date", "prov_code"], how="inner", suffixes=("", "_split"))
    if observed_only:
        merged = merged[merged["is_target_observed"].astype(bool)]
    merged = merged[merged["label_primary"] == regime]
    return merged.reset_index(drop=True)


def _regime_columns(regimes: pd.DataFrame) -> pd.DataFrame:
    need = {
        "date", "prov_code", "enso_phase", "is_dry", "is_extreme_rain",
        "is_normal", "label_primary", "episode_id",
    }
    missing = need - set(regimes.columns)
    if missing:
        raise ValueError(f"regime_labels: kolom hilang {sorted(missing)}")
    frame = regimes[list(need)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).astype("datetime64[ns]")
    frame["prov_code"] = frame["prov_code"].astype(str).str.zfill(2)
    if frame.duplicated(["date", "prov_code"]).any():
        raise ValueError("regime_labels duplikat (date, prov_code)")
    return frame


def build_split(
    panel: pd.DataFrame,
    regimes: pd.DataFrame,
    origin: str,
    part: str,
    *,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Build one split from the dataset panel and regime labels."""
    need = {"date", "prov_code", "is_observed"}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel: kolom hilang {sorted(missing)}")
    p = panel[["date", "prov_code", "is_observed"]].copy()
    p["date"] = pd.to_datetime(p["date"]).astype("datetime64[ns]")
    p["prov_code"] = p["prov_code"].astype(str).str.zfill(2)
    a, b = parse_range(f"{start}..{end}")
    p = p[(p["date"] >= pd.Timestamp(a)) & (p["date"] <= pd.Timestamp(b))]
    if p.empty:
        raise ValueError(f"{origin}/{part}: tidak ada baris pada {start}..{end}")
    r = _regime_columns(regimes)
    out = p.merge(r, on=["date", "prov_code"], how="left", validate="many_to_one")
    if out["label_primary"].isna().any():
        missing_n = int(out["label_primary"].isna().sum())
        raise ValueError(f"{origin}/{part}: {missing_n} baris tanpa label regime")
    out = out.rename(columns={"is_observed": "is_target_observed"})
    return out[SPLIT_COLUMNS].sort_values(["date", "prov_code"]).reset_index(drop=True)


def build_eval_splits(
    panel: pd.DataFrame,
    regimes: pd.DataFrame,
    *,
    out_dir: Path | str = DEFAULT_SPLITS_DIR,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build O1/O2/O3 val/test splits and the summary table."""
    cfg = config or load_global_config()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for origin in ("O1", "O2", "O3"):
        for part in ("val", "test"):
            start, end = parse_range(cfg["origins"][origin][part])
            frame = build_split(panel, regimes, origin, part,
                                start=str(start), end=str(end))
            path = out / f"{origin}_{part}.parquet"
            frame.to_parquet(path, index=False)
            counts = (
                frame.groupby("label_primary", dropna=False)
                .agg(n_node_days=("date", "size"),
                     n_target_observed=("is_target_observed", "sum"))
                .reset_index()
                .rename(columns={"label_primary": "regime"})
            )
            counts.insert(0, "part", part)
            counts.insert(0, "origin", origin)
            counts["ci_wide"] = counts["n_target_observed"] < 200
            summaries.append(counts)
    summary = pd.concat(summaries, ignore_index=True)
    summary = summary.sort_values(["origin", "part", "regime"]).reset_index(drop=True)
    summary.to_csv(out / "summary.csv", index=False)
    return summary, summary


def summary_markdown(summary: pd.DataFrame, *, min_node_days: int = 200) -> str:
    lines = [
        "# CGS-H4-01 — eval splits per regime",
        "",
        "Sumber: `data/processed/dataset_v1/panel.parquet` + `data/interim/regime_labels.csv`.",
        "Rentang val/test mengikuti `configs/global.yaml`; tidak ada tanggal holdout.",
        "",
        "| origin | part | regime | node-hari | target observed | CI lebar |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.origin} | {row.part} | {row.regime} | {int(row.n_node_days):,} | "
            f"{int(row.n_target_observed):,} | {'ya' if row.ci_wide else 'tidak'} |"
        )
    lines += ["", "## DoD", ""]
    for origin, group in summary.groupby("origin"):
        enough = group[(group["n_target_observed"] >= min_node_days)]["regime"].nunique()
        lines.append(f"- {origin}: {enough} regime dengan ≥{min_node_days} target observed"
                     + (" (memenuhi)" if enough >= 2 else " (terbatas; catat untuk RL)"))
    lines += [
        "",
        "`ci_wide` memakai target observed < 200 sebagai penanda CI lebar.",
        "Subset identik untuk semua model: gunakan `renaro.eval.regimes.filter(preds, origin, part, regime)`.",
        "",
    ]
    return "\n".join(lines)
