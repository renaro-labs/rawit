
"""Rolling-origin evaluation splits for RAWIT."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.contract import (
    PROJECT_ROOT,
    EMBARGO_WORKDAYS,
    HORIZONS,
    HOLDOUT_START,
    parse_range,
)


GLOBAL_CONFIG = PROJECT_ROOT / "configs" / "global.yaml"


@dataclass(frozen=True)
class Split:
    origin: str
    train: tuple[pd.Timestamp, pd.Timestamp]
    val: tuple[pd.Timestamp, pd.Timestamp]
    test: tuple[pd.Timestamp, pd.Timestamp]
    embargo_workdays: int = EMBARGO_WORKDAYS


def load_global_config(
    path: Path = GLOBAL_CONFIG,
) -> dict:

    with open(path, encoding="utf-8") as file:
        cfg = yaml.safe_load(file)

    required = {
        "origins",
        "horizons",
        "embargo_workdays",
        "holdout_start",
    }

    missing = required - set(cfg)

    if missing:
        raise ValueError(
            f"Global config tidak lengkap: {missing}"
        )

    if tuple(cfg["horizons"]) != HORIZONS:
        raise ValueError(
            "Horizon berbeda dari contract.py"
        )

    if cfg["embargo_workdays"] < max(cfg["horizons"]):
        raise ValueError(
            "Embargo lebih kecil dari horizon maksimum"
        )

    if pd.Timestamp(cfg["holdout_start"]) != pd.Timestamp(
        HOLDOUT_START
    ):
        raise ValueError(
            "Holdout berbeda dari contract.py"
        )

    return cfg


def rolling_origin(
    origin: str,
    dates: pd.DatetimeIndex,
) -> Split:

    cfg = load_global_config()
    origins = cfg["origins"]

    if origin not in origins:
        raise ValueError(f"Origin tidak dikenal: {origin}")

    if origin == "HOLDOUT":
        raise PermissionError("HOLDOUT masih SEALED")

    dates = pd.DatetimeIndex(dates).normalize()

    if dates.hasnans:
        raise ValueError("Tanggal mengandung NaT")

    dates = dates.unique().sort_values()

    if (dates.day_of_week >= 5).any():
        raise ValueError("Ditemukan tanggal akhir pekan")

    if (dates >= pd.Timestamp(HOLDOUT_START)).any():
        raise ValueError("Dataset mengandung HOLDOUT")

    embargo = int(cfg["embargo_workdays"])

    ranges = {}

    for part in ("train", "val", "test"):

        start, end = parse_range(
            origins[origin][part]
        )

        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

        selected = dates[
            (dates >= start) & (dates <= end)
        ]

        if len(selected) == 0:
            raise ValueError(
                f"Split {origin}/{part} kosong"
            )

        # Embargo pada batas train-val dan val-test.
        if part in ("train", "val"):

            if len(selected) <= embargo:
                raise ValueError(
                    f"Split {part} terlalu pendek"
                )

            selected = selected[:-embargo]

        ranges[part] = (
            selected[0],
            selected[-1],
        )

    split = Split(
        origin=origin,
        train=ranges["train"],
        val=ranges["val"],
        test=ranges["test"],
        embargo_workdays=embargo,
    )

    assert_no_overlap(split)

    return split


def assert_no_overlap(split: Split) -> None:

    for name in ("train", "val", "test"):
        start, end = getattr(split, name)

        if start > end:
            raise ValueError(
                f"Rentang {name} tidak valid"
            )

    boundaries = (
        (split.train[1], split.val[0]),
        (split.val[1], split.test[0]),
    )

    for left_end, right_start in boundaries:

        if left_end >= right_start:
            raise ValueError("Split overlap")

        gap = np.busday_count(
            np.datetime64(left_end.date()) + np.timedelta64(1, "D"),
            np.datetime64(right_start.date()),
        )

        if gap < split.embargo_workdays:
            raise ValueError(
                f"Embargo tidak cukup: {gap} hari kerja"
            )

    if split.test[1] >= pd.Timestamp(HOLDOUT_START):
        raise PermissionError(
            "Split memasuki periode HOLDOUT"
        )


def split_indices(
    split: Split,
    dates: pd.DatetimeIndex,
    part: str,
    *,
    horizon: int | None = None,
    window: int | None = None,
) -> np.ndarray:
    """Indeks decision date tanpa kebocoran target."""

    cfg = load_global_config()

    if horizon is None:
        horizon = max(cfg["horizons"])

    if window is None:
        window = int(cfg["window"])

    if horizon not in cfg["horizons"]:
        raise ValueError("Horizon tidak dikenal")

    if part not in ("train", "val", "test"):
        raise ValueError("Part tidak dikenal")

    if window < 1:
        raise ValueError("Window harus positif")

    dates = pd.DatetimeIndex(dates)

    if not dates.is_monotonic_increasing or not dates.is_unique:
        raise ValueError("Decision dates harus unik dan terurut")

    start, effective_end = getattr(split, part)

    # Embargo sudah memperpendek decision dates.
    # Target harus tersedia sebelum akhir split asli.
    _, original_end = parse_range(
        cfg["origins"][split.origin][part]
    )

    original_end = pd.Timestamp(original_end)

    result = []

    for k in range(window - 1, len(dates) - horizon):

        decision_date = dates[k]
        available_date = dates[k + horizon]

        if (
            start <= decision_date <= effective_end
            and available_date <= original_end
            and available_date < pd.Timestamp(HOLDOUT_START)
        ):
            result.append(k)

    if not result:
        raise ValueError(
            f"Tidak ada decision index untuk {part}"
        )

    return np.asarray(result, dtype=np.int64)
