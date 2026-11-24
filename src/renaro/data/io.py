"""RAWIT dataset_v1 loader — contract-aligned; no unofficial holdout access."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import yaml
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import (
    HOLDOUT_START, ORIGINS, PROV_CODES, TABLE_COLUMNS,
    check_columns, check_unique, content_hash, has_unseal_key,
)


@dataclass
class Panel:
    panel: pd.DataFrame
    target: pd.DataFrame
    nodes: pd.DataFrame
    mask: np.ndarray
    dates: pd.DatetimeIndex
    node_codes: list[str]
    split_hash: str = ""
    meta: dict = field(default_factory=dict)

    def target_at(self, k: int, h: int) -> tuple[np.ndarray, np.ndarray]:
        """As-of decision k: h = observation at k+h-1, known at k+h."""
        if not isinstance(k, (int, np.integer)) or not isinstance(h, (int, np.integer)):
            raise TypeError("k dan h harus integer")
        if h <= 0 or k < 0 or k + h >= len(self.dates):
            raise IndexError("Indeks target di luar rentang decision dates")
        date = self.dates[k + h - 1]
        rows = self.target[self.target['date'] == date].set_index('prov_code').reindex(self.node_codes)
        prices = pd.to_numeric(rows['price'], errors='coerce').to_numpy(dtype=float)
        valid = rows['is_observed'].fillna(False).to_numpy(dtype=bool) & np.isfinite(prices) & (prices > 0)
        # Honor optional bad-target flags if present.
        for col in ('flag_outlier', 'flag_carry_forward', 'flag_post_lebaran'):
            if col in rows:
                valid &= ~rows[col].fillna(False).to_numpy(dtype=bool)
        result = np.where(valid, prices, 0).astype(np.float32)
        return result, valid


def _read(path: Path):
    panel = pd.read_parquet(path / 'panel.parquet')
    target = pd.read_parquet(path / 'target.parquet')
    nodes = pd.read_csv(path / 'nodes.csv', dtype={'prov_code': str})
    mask = np.load(path / 'bps_mask.npy', allow_pickle=False)
    return panel, target, nodes, mask


def validate_dataset(path: Path) -> None:
    path = Path(path)
    required = ('panel.parquet','target.parquet','nodes.csv','bps_mask.npy')
    missing = [f for f in required if not (path / f).is_file()]
    if missing:
        raise FileNotFoundError(f'Dataset tidak lengkap: {missing}')
    panel, target, nodes, mask = _read(path)
    for name, frame in [('panel', panel), ('target', target)]:
        check_columns(frame, name)
        check_unique(frame, name)
        dates = pd.to_datetime(frame['date'], errors='raise')
        if dates.isna().any():
            raise ValueError(f'{name}: ada tanggal kosong')
        if not frame['prov_code'].map(lambda c: isinstance(c, str) and c in PROV_CODES).all():
            raise ValueError(f'{name}: prov_code harus string BPS dari PROV_CODES')
        if frame['is_observed'].dtype != bool:
            raise ValueError(f'{name}: is_observed harus bool')
        if not dates.dt.day_of_week.lt(5).all():
            raise ValueError(f'{name}: ditemukan tanggal akhir pekan')
    if not {'prov_code','prov_name','include'}.issubset(nodes.columns):
        raise ValueError('nodes.csv wajib prov_code, prov_name, include')
    if nodes['prov_code'].tolist() != list(PROV_CODES):
        raise ValueError('Urutan nodes.csv berbeda dari PROV_CODES')
    if nodes['include'].isna().any() or not nodes['include'].isin([True, False, 'True', 'False', 'true', 'false']).all():
        raise ValueError('nodes.include tidak valid')
    n = len(PROV_CODES)
    if mask.shape != (n, n) or mask.dtype != np.uint8:
        raise ValueError(f'Mask harus uint8 {n}x{n}')
    if not np.isin(mask, [0, 1]).all() or np.diag(mask).any():
        raise ValueError('Mask harus biner dan diagonal nol')
    forbidden = ('regime_labels', 'enso_phase', 'label_primary', 'episode_id', 'is_dry', 'is_normal', 'is_extreme_rain')
    if any(c in panel.columns for c in forbidden):
        raise ValueError('Regime labels eval-only dilarang dalam panel')


def load_panel(path: Path, *, unseal: bool = False) -> Panel:
    path = Path(path)

    if unseal and not has_unseal_key():
        raise PermissionError(
            "Holdout terkunci: HOLDOUT_UNSEALED tidak ada."
        )

    validate_dataset(path)
    panel, target, nodes, mask = _read(path)

    # Konversi tanggal
    panel["date"] = pd.to_datetime(panel["date"])
    target["date"] = pd.to_datetime(target["date"])

    # Urutkan berdasarkan tanggal dan provinsi
    panel = panel.sort_values(
        ["date", "prov_code"]
    ).reset_index(drop=True)

    target = target.sort_values(
        ["date", "prov_code"]
    ).reset_index(drop=True)

    # Proteksi holdout
    if not unseal:
        cutoff = pd.Timestamp(HOLDOUT_START)

        panel = panel.loc[
            panel["date"] < cutoff
        ].copy()

        target = target.loc[
            target["date"] < cutoff
        ].copy()

        holdout_guard(panel)
        holdout_guard(target)

    # Pastikan data tidak kosong
    if panel.empty or target.empty:
        raise ValueError("Dataset kosong setelah filtering")

    # Tanggal keputusan
    dates = pd.DatetimeIndex(
        sorted(panel["date"].unique())
    )

    # Hash stabil berdasarkan data dan split
    marker = (
        content_hash(panel, ("date", "prov_code"))
        + content_hash(target, ("date", "prov_code"))
        + repr(ORIGINS)
        + repr(PROV_CODES)
    )

    split_hash = sha256(
        marker.encode("utf-8")
    ).hexdigest()

    # Metadata
    meta = {
        "path": str(path),
        "sealed": not unseal,
        "n_dates": len(dates),
        "n_nodes": len(PROV_CODES),
    }

    return Panel(
        panel=panel,
        target=target,
        nodes=nodes,
        mask=mask,
        dates=dates,
        node_codes=list(PROV_CODES),
        split_hash=split_hash,
        meta=meta,
    )

def holdout_guard(frame: pd.DataFrame) -> None:
    """Memastikan dataset tidak mengandung data holdout."""
    if "date" not in frame.columns:
        raise ValueError("Kolom date tidak ditemukan")

    dates = pd.to_datetime(frame["date"])

    if dates.isna().any():
        raise ValueError("Ada tanggal tidak valid")

    if (dates >= pd.Timestamp(HOLDOUT_START)).any():
        raise ValueError("Dataset mengandung data holdout")