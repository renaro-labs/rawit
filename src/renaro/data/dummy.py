"""Deterministic schema-faithful dummy dataset; not a synthetic mechanism."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from renaro.contract import HOLDOUT_START, PROV_CODES, PROV_NAMES, TABLE_COLUMNS, check_columns, write_sha256sums

OUT = Path('data/dummy/dataset_v1')
START, END, DENSITY = '2017-07-01', '2026-05-31', 0.14


def business_days(start: str = START, end: str = END) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


def make_panel(days: pd.DatetimeIndex, seed: int = 0) -> pd.DataFrame:
    days = pd.DatetimeIndex(days)
    if not len(days) or days.max() >= pd.Timestamp(HOLDOUT_START) or (days.day_of_week >= 5).any():
        raise ValueError('Dummy hanya menerima hari kerja sebelum HOLDOUT_START')
    rng = np.random.default_rng(seed)
    n, t = len(PROV_CODES), len(days)
    grid = pd.MultiIndex.from_product([days, PROV_CODES], names=['date', 'prov_code'])
    df = grid.to_frame(index=False)
    df['prov_code'] = df['prov_code'].astype(str)
    date_idx = np.repeat(np.arange(t), n)
    seasonal = np.sin(2 * np.pi * days.day_of_year.to_numpy() / 365.25)
    # Iklim AR(1) dengan musiman, bukan sinyal prediktif terhadap harga dummy.
    ar = np.empty((t, n), dtype=np.float32)
    ar[0] = rng.normal(size=n)
    for i in range(1, t):
        ar[i] = 0.75 * ar[i - 1] + rng.normal(0, 0.8, n)
    ar += seasonal[:, None] * 0.8
    df['rain_pentad_anom'] = ar.reshape(-1)
    df['rain_30d_anom'] = (0.6 * ar + rng.normal(0, 0.5, (t, n))).reshape(-1)
    df['dry_spell_days'] = rng.integers(0, 16, t * n).astype('float32')
    df['extreme_5d'] = (rng.random(t * n) < 0.05)
    df['roni'] = np.repeat(rng.normal(0, 0.6, t), n).astype('float32')
    df['is_ramadan'] = np.repeat(((days.month == 3) | (days.month == 4)).astype(bool), n)
    df['days_to_lebaran'] = np.repeat(np.where((days.month == 3) | (days.month == 4), 15 - days.day, 180), n).astype('int16')
    df['dow'] = days.day_of_week.to_numpy()[date_idx].astype('int8')
    df['month'] = days.month.to_numpy()[date_idx].astype('int8')
    df['is_observed'] = rng.random(t * n) < 0.90
    # Published price available on the next business date; do not use same-day price as feature.
    df['price'] = np.where(df['is_observed'], np.clip(rng.lognormal(np.log(40000), 0.25, t * n), 20000, 80000), np.nan)
    # Noncontract optional availability metadata. Upstream actual data may have longer lags.
    df['available_at'] = df['date']
    check_columns(df, 'panel')
    return df


def make_target(panel: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    out = panel[['date', 'prov_code', 'is_observed', 'price']].copy()
    check_columns(out, 'target')
    return out


def make_mask(seed: int = 0, density: float = DENSITY) -> np.ndarray:
    if not (0 <= density <= 1):
        raise ValueError('density harus antara 0 dan 1')
    rng = np.random.default_rng(seed + 20_000)
    mask = (rng.random((len(PROV_CODES), len(PROV_CODES))) < density).astype(np.uint8)
    np.fill_diagonal(mask, 0)
    return mask


def make_nodes() -> pd.DataFrame:
    return pd.DataFrame({'prov_code': PROV_CODES, 'prov_name': PROV_NAMES, 'include': True})


def write_dummy(out: Path = OUT, seed: int = 0) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    days = business_days()
    panel = make_panel(days, seed)
    target = make_target(panel, seed)
    panel.to_parquet(out / 'panel.parquet', index=False)
    target.to_parquet(out / 'target.parquet', index=False)
    make_nodes().to_csv(out / 'nodes.csv', index=False)
    np.save(out / 'bps_mask.npy', make_mask(seed))
    feature_cols = [c for c in TABLE_COLUMNS['panel'] if c not in ('date', 'prov_code', 'price', 'is_observed')]
    pd.DataFrame({'feature': feature_cols, 'dtype': [str(panel[c].dtype) for c in feature_cols],
                  'description': ['Dummy schema-aligned feature'] * len(feature_cols)}).to_csv(out / 'feature_dict.csv', index=False)
    (out / 'VERSION').write_text('dataset_v1 dummy\n', encoding='utf-8')
    write_sha256sums(out)


def main() -> None:
    ap = argparse.ArgumentParser(description='Generate dummy dataset_v1')
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()
    write_dummy(args.out, args.seed)


if __name__ == '__main__':
    main()
