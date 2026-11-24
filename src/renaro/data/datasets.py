"""RAWIT MLE-H1-01: tensor windows dari keluaran renaro.data.io.load_panel.

Kompatibel dengan load_panel() yang mengembalikan objek Panel.

Konvensi: indeks decision k, target h ialah observasi k+h-1 yang
baru tersedia pada hari k+h. Harga pada hari k belum boleh masuk fitur X[k].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from renaro.contract import HOLDOUT_START, ORIGINS, PROV_CODES, parse_range
from renaro.data.io import Panel


FEATURES = (
    "price", "rain_pentad_anom", "rain_30d_anom", "dry_spell_days",
    "extreme_5d", "roni", "is_ramadan", "days_to_lebaran", "dow", "month",
)
CLIMATE_FEATURES = (
    "rain_pentad_anom", "rain_30d_anom", "dry_spell_days", "extreme_5d", "roni",
)


@dataclass(frozen=True)
class WindowSpec:
    window: int = 60
    horizons: tuple[int, ...] = (5, 10, 20)
    node_subset: tuple[str, ...] | None = None


class Normalizer:
    """Rata-rata/std per fitur; fit HARUS menerima data train saja."""

    def fit(self, x: np.ndarray) -> "Normalizer":
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 3:
            raise ValueError("Normalizer membutuhkan array [T, N, F]")
        finite = np.isfinite(x)
        counts = finite.sum(axis=(0, 1))
        sums = np.where(finite, x, 0).sum(axis=(0, 1))
        self.mean = np.divide(sums, counts, out=np.zeros(x.shape[2]), where=counts > 0)
        diff = np.where(finite, x - self.mean, 0)
        var = np.divide((diff * diff).sum(axis=(0, 1)), counts,
                        out=np.zeros(x.shape[2]), where=counts > 0)
        self.std = np.where((counts > 0) & (var > 1e-12), np.sqrt(var), 1.0)
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if not hasattr(self, "mean"):
            raise RuntimeError("Jalankan fit() menggunakan TRAIN terlebih dahulu")
        x = np.asarray(x, dtype=np.float64)
        z = (x - self.mean) / self.std
        return np.where(np.isfinite(z), z, 0.0).astype(np.float32)


class WindowDataset(Dataset):
    """Satu sampel per decision date, berisi semua 34 provinsi.

    panel: objek Panel hasil load_panel(...).
    origin: 'O1', 'O2', 'O3' (split resmi dari renaro.contract.ORIGINS).
    part: 'train', 'val', 'test'. HOLDOUT/test SEALED dilarang.

    Kolom fitur iklim dan RONI diasumsikan SUDAH melewati as-of join upstream;
    dataset ini tidak dapat membuktikan available_at dari panel gabungan.
    """

    def __init__(self, panel: Panel, origin: str, part: str,
                 spec: WindowSpec = WindowSpec()):
        if not isinstance(panel, Panel):
            raise TypeError("panel harus objek Panel dari renaro.data.io.load_panel")
        if origin not in ORIGINS:
            raise ValueError(f"Origin tidak dikenal: {origin!r}")
        if part not in ("train", "val", "test"):
            raise ValueError("part harus 'train', 'val', atau 'test'")
        if origin == "HOLDOUT" and part == "test":
            raise ValueError("HOLDOUT test SEALED; tidak boleh dibuka di H1")
        if spec.window <= 0 or not spec.horizons or any(h <= 0 for h in spec.horizons):
            raise ValueError("window dan horizons harus positif")
        if len(set(spec.horizons)) != len(spec.horizons):
            raise ValueError("horizons harus unik")

        df, target, nodes, graph = panel.panel, panel.target, panel.nodes, panel.mask
        self.panel, self.spec, self.origin, self.part = panel, spec, origin, part
        self.features = FEATURES
        self.climate_features = CLIMATE_FEATURES
        self.graph = np.asarray(graph, dtype=np.uint8)
        if self.graph.shape != (34, 34):
            raise ValueError("Graph wajib berbentuk (34, 34)")
        codes = [str(c) for c in PROV_CODES]
        if nodes["prov_code"].astype(str).tolist() != codes:
            raise ValueError("Urutan nodes.csv berbeda dari PROV_CODES")
        self.codes = tuple(codes)
        for name, frame, needed in (
            ("panel", df, ("date", "prov_code", *FEATURES)),
            ("target", target, ("date", "prov_code", "price", "is_observed")),
        ):
            missing = set(needed) - set(frame.columns)
            if missing:
                raise ValueError(f"{name}: kolom hilang {sorted(missing)}")

        df, target = df.copy(), target.copy()
        df["date"] = pd.to_datetime(df["date"])
        target["date"] = pd.to_datetime(target["date"])
        for frame in (df, target):
            frame["prov_code"] = frame["prov_code"].astype(str)
            if frame.duplicated(["date", "prov_code"]).any():
                raise ValueError("Duplikat (date, prov_code)")
            if (frame["date"] >= pd.Timestamp(HOLDOUT_START)).any():
                raise ValueError("Ada tanggal HOLDOUT pada dataset")

        dates = pd.DatetimeIndex(sorted(df["date"].unique()))
        if not len(dates):
            raise ValueError("Panel kosong")
        if not dates.equals(pd.DatetimeIndex(sorted(target["date"].unique()))):
            raise ValueError("Tanggal panel dan target tidak sama")
        self.dates = dates
        n, t = len(codes), len(dates)
        grid = pd.MultiIndex.from_product([dates, codes], names=["date", "prov_code"])
        df = df.set_index(["date", "prov_code"])
        target = target.set_index(["date", "prov_code"])
        if len(df) != len(grid) or len(target) != len(grid) or not grid.isin(df.index).all() or not grid.isin(target.index).all():
            raise ValueError("Panel/target harus grid lengkap tanggal x 34 provinsi")
        df, target = df.reindex(grid), target.reindex(grid)

        raw = df.loc[:, FEATURES].astype(float).to_numpy().reshape(t, n, len(FEATURES))
        # Harga observasi hari k tersedia H+1: input pada decision k
        # memakai harga k-1, TIDAK harga k.
        price_idx = FEATURES.index("price")
        raw[1:, :, price_idx] = raw[:-1, :, price_idx].copy()
        raw[0, :, price_idx] = np.nan

        begin_train, end_train = parse_range(ORIGINS[origin]["train"])
        train_sel = (dates >= pd.Timestamp(begin_train)) & (dates <= pd.Timestamp(end_train))
        if not train_sel.any():
            raise ValueError("Tidak ada data TRAIN untuk origin ini")
        self.normalizer = Normalizer().fit(raw[train_sel])
        self.mean, self.std = self.normalizer.mean, self.normalizer.std
        self.x = self.normalizer.transform(raw)

        clim_indices = [FEATURES.index(f) for f in CLIMATE_FEATURES]
        # Iklim memakai normalisasi TRAIN yang sama dengan X.
        self.climate = self.x[:, :, clim_indices].copy()

        raw_y = target["price"].astype(float).to_numpy().reshape(t, n)
        observed = target["is_observed"].to_numpy(dtype=bool).reshape(t, n)
        if np.any(observed & (~np.isfinite(raw_y) | (raw_y <= 0))):
            raise ValueError("Harga target teramati harus finite dan positif")
        # Mask missing, nilai y untuk missing diisi 0 hanya sebagai placeholder;
        # jangan pernah hitung loss pada y_mask=False.
        # Validitas target menggunakan method kontrak Panel.target_at().
        self.y = np.where(observed, raw_y, 0.0).astype(np.float32)
        self.observed = observed

        include = nodes["include"].to_numpy(dtype=bool, copy=True)
        if spec.node_subset is not None:
            selected = set(map(str, spec.node_subset))
            if not selected.issubset(codes):
                raise ValueError(
                f"node_subset tidak dikenal: {sorted(selected - set(codes))}"
        )
            include &= np.array([c in selected for c in codes])
        self.include = include

        bounds = ORIGINS[origin][part]
        if bounds == "SEALED":
            raise ValueError("Split masih SEALED")
        start, stop = parse_range(bounds)
        start, stop = pd.Timestamp(start), pd.Timestamp(stop)
        self.decision_indices = []
        max_h = max(spec.horizons)
        for k in range(spec.window - 1, t - max_h):
            # Decision harus di bagian yang diminta. Semua label pada horizon
            # tersedia k+h (observasi k+h-1), dan harus tetap dalam part.
            if not (start <= dates[k] <= stop):
                continue
            available_dates = dates[k + np.asarray(spec.horizons)]
            if np.all((available_dates >= start) & (available_dates <= stop)):
                self.decision_indices.append(k)
        if not self.decision_indices:
            raise ValueError(f"Tidak ada window valid untuk {origin}/{part}")

    def __len__(self) -> int:
        return len(self.decision_indices)

    def __getitem__(self, i: int) -> dict[str, Any]:
        k = self.decision_indices[i]
        start = k - self.spec.window + 1
        indices = k + np.asarray(self.spec.horizons) - 1
        targets = [self.panel.target_at(k, h) for h in self.spec.horizons]
        y = np.stack([pair[0] for pair in targets])
        observed = np.stack([pair[1] for pair in targets]) & self.include[None, :]
        return {
            "X": torch.from_numpy(self.x[start:k+1].copy()),
            "C": torch.from_numpy(self.climate[start:k+1].copy()),
            "y": torch.from_numpy(y.copy()),
            "y_mask": torch.from_numpy(observed.copy()),
            "t_index": torch.tensor(k, dtype=torch.int64),
            "date": self.dates[k].strftime("%Y-%m-%d"),
        }


def make_loader(dataset: WindowDataset, *, batch_size: int, shuffle: bool,
                num_workers: int = 0) -> DataLoader:
    """DataLoader standar. Gunakan num_workers=0 di Windows untuk mulai."""
    if batch_size <= 0:
        raise ValueError("batch_size harus positif")
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      num_workers=num_workers)
