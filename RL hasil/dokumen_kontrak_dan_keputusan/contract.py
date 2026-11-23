# =============================================================================
#  SHARED CONTRACT · ALL ROLES · Sprint 1 (brief v2)
#  Bukan job card. Ini satu-satunya sumber konstanta & validator skema.
#  Target: src/renaro/contract.py        (disalin sekali oleh MLE-H0-01)
#  Sumber: sprint1_playbook/01_SETUP_ENV_DAN_KONTRAK.md §5–§7
#  Aturan: JANGAN mengubah nilai di sini tanpa keputusan RL (protocol-v1).
# =============================================================================
"""Konstanta kontrak Renaro Sprint 1.

Semua role mengimpor dari sini supaya nama kolom, urutan node, horizon, dan
aturan holdout tidak bercabang. Modul ini sengaja hanya berisi konstanta dan
helper murah; logika pipeline tetap milik job masing-masing.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------
def _find_project_root(start: Path) -> Path:
    """Cari root repo dari lokasi file (tahan terhadap handout vs src/)."""
    for candidate in [start, *start.parents]:
        if (candidate / "sprint1_playbook").is_dir() or (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
DATA_ROOT = Path(os.environ.get("RENARO_DATA_ROOT", PROJECT_ROOT / "data")).resolve()
RAW = DATA_ROOT / "raw"
INTERIM = DATA_ROOT / "interim"
PROCESSED = DATA_ROOT / "processed"
REPORTS = PROJECT_ROOT / "reports"
RUNS = PROJECT_ROOT / "experiments" / "runs"

# ---------------------------------------------------------------------------
# Waktu & split
# ---------------------------------------------------------------------------
PANEL_START = date(2017, 7, 1)       # pemanasan lag; panel latih efektif 2018-01-02
TRAIN_START = date(2018, 1, 2)
HOLDOUT_START = date(2026, 6, 1)     # SEALED. Hanya CGS.
WINDOW = 60                          # hari kerja input
HORIZONS: tuple[int, ...] = (5, 10, 20)
PRIMARY_HORIZON = 10
EMBARGO_WORKDAYS = 20                # >= horizon maks
SEEDS: tuple[int, ...] = (0, 1, 2, 3, 4)

#: Rolling origin. Tanggal inklusif. `train` sudah dipotong embargo oleh splits.py.
ORIGINS: dict[str, dict[str, str]] = {
    "O1": {"train": "2018-01-02..2022-06-30", "val": "2022-07-01..2022-12-31", "test": "2023-01-01..2023-12-31"},
    "O2": {"train": "2018-01-02..2023-06-30", "val": "2023-07-01..2023-12-31", "test": "2024-01-01..2024-12-31"},
    "O3": {"train": "2018-01-02..2024-06-30", "val": "2024-07-01..2024-12-31", "test": "2025-01-01..2026-05-31"},
    "HOLDOUT": {"train": "2018-01-02..2025-12-31", "val": "2026-01-01..2026-05-31", "test": "SEALED"},
}

# ---------------------------------------------------------------------------
# Node: 34 provinsi struktur lama. Urutan = indeks node di semua matriks.
# ---------------------------------------------------------------------------
PROVINCES: tuple[tuple[str, str], ...] = (
    ("11", "Aceh"),
    ("12", "Sumatera Utara"),
    ("13", "Sumatera Barat"),
    ("14", "Riau"),
    ("15", "Jambi"),
    ("16", "Sumatera Selatan"),
    ("17", "Bengkulu"),
    ("18", "Lampung"),
    ("19", "Kepulauan Bangka Belitung"),
    ("21", "Kepulauan Riau"),
    ("31", "DKI Jakarta"),
    ("32", "Jawa Barat"),
    ("33", "Jawa Tengah"),
    ("34", "DI Yogyakarta"),
    ("35", "Jawa Timur"),
    ("36", "Banten"),
    ("51", "Bali"),
    ("52", "Nusa Tenggara Barat"),
    ("53", "Nusa Tenggara Timur"),
    ("61", "Kalimantan Barat"),
    ("62", "Kalimantan Tengah"),
    ("63", "Kalimantan Selatan"),
    ("64", "Kalimantan Timur"),
    ("65", "Kalimantan Utara"),
    ("71", "Sulawesi Utara"),
    ("72", "Sulawesi Tengah"),
    ("73", "Sulawesi Selatan"),
    ("74", "Sulawesi Tenggara"),
    ("75", "Gorontalo"),
    ("76", "Sulawesi Barat"),
    ("81", "Maluku"),
    ("82", "Maluku Utara"),
    ("91", "Papua Barat"),
    ("94", "Papua"),
)
PROV_CODES: tuple[str, ...] = tuple(code for code, _ in PROVINCES)
PROV_NAMES: tuple[str, ...] = tuple(name for _, name in PROVINCES)
NODE_INDEX: dict[str, int] = {code: i for i, code in enumerate(PROV_CODES)}
N_NODES = len(PROVINCES)

_NAME_ALIASES = {
    "d.i. yogyakarta": "34",
    "di yogyakarta": "34",
    "yogyakarta": "34",
    "dki jakarta": "31",
    "jakarta": "31",
    "kep. bangka belitung": "19",
    "bangka belitung": "19",
    "kepulauan bangka belitung": "19",
    "kep. riau": "21",
    "kepulauan riau": "21",
    "ntb": "52",
    "nusa tenggara barat": "52",
    "ntt": "53",
    "nusa tenggara timur": "53",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


PROV_NAME_TO_CODE: dict[str, str] = {
    **{_norm(name): code for code, name in PROVINCES},
    **_NAME_ALIASES,
}


def prov_code_of(name: str) -> str:
    """Nama provinsi mentah -> kode BPS. Gagal keras agar tidak ada baris hilang."""
    key = _norm(name)
    if key in PROV_NAME_TO_CODE:
        return PROV_NAME_TO_CODE[key]
    raise KeyError(f"Nama provinsi tidak dikenal: {name!r}. Tambahkan alias di provinces.csv, bukan di sini.")


# ---------------------------------------------------------------------------
# Fitur iklim & lag (resolusi pentad)
# ---------------------------------------------------------------------------
PENTAD_LAGS: tuple[int, ...] = tuple(range(0, 9))   # 0..8 pentad ke belakang
N_LAG_BINS = 8                                      # L di Modul 1
DRY_PENTAD_MM = 5.0                                 # [usulan default]
EXTREME_QUANTILE = 0.95
DROUGHT_QUANTILE = 0.20
CLIMATE_VARS: tuple[str, ...] = (
    "rain_mm",
    "rain_pentad_mm",
    "rain_pentad_anom",
    "rain_30d_anom",
    "dry_spell_days",
    "extreme_5d",
)
ENSO_PHASES = ("el_nino", "la_nina", "neutral")

# ---------------------------------------------------------------------------
# Skema tabel (kolom wajib). Nama kolom = hukum; tambahan boleh, rename tidak.
# ---------------------------------------------------------------------------
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "prices_clean": (
        "date", "prov_code", "commodity", "price_type", "price_raw", "price",
        "is_observed", "flag_outlier", "flag_post_lebaran", "flag_carry_forward",
        "source", "available_at",
    ),
    "calendar": (
        "date", "is_workday_pihps", "is_holiday", "is_cuti_bersama", "is_ramadan",
        "days_to_lebaran", "days_to_iduladha", "is_natal_tahunbaru",
        "dow", "month", "doy",
    ),
    "climate_features": (
        "date", "prov_code", "variant", "rain_mm", "rain_pentad_mm",
        "rain_pentad_anom", "rain_30d_anom", "dry_spell_days", "extreme_5d",
        "available_at",
    ),
    "roni": ("season", "year", "center_month", "roni", "vintage_date", "available_at"),
    "regime_labels": (
        "date", "prov_code", "enso_phase", "episode_id", "is_dry",
        "is_extreme_rain", "is_normal", "label_primary",
    ),
    "panel": (
        "date", "prov_code", "price", "is_observed",
        "rain_pentad_anom", "rain_30d_anom", "dry_spell_days", "extreme_5d",
        "roni", "is_ramadan", "days_to_lebaran", "dow", "month",
    ),
    "target": ("date", "prov_code", "price", "is_observed"),
    "preds": ("model", "fold", "seed", "date", "prov_code", "h", "y_true", "y_pred"),
    "availability": (
        "feature_family", "source", "variant", "rule", "lag_days", "evidence", "decided_by",
    ),
    "regime_label_types": ("prov_code", "label_type", "label"),
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "prices_clean": ("date", "prov_code", "commodity", "price_type"),
    "calendar": ("date",),
    "climate_features": ("date", "prov_code", "variant"),
    "roni": ("season", "year", "vintage_date"),
    "regime_labels": ("date", "prov_code"),
    "panel": ("date", "prov_code"),
    "target": ("date", "prov_code"),
    "preds": ("model", "fold", "seed", "date", "prov_code", "h"),
    "availability": ("feature_family", "source", "variant"),
}


def check_columns(frame: pd.DataFrame, table: str, *, allow_extra: bool = True) -> None:
    """Validasi kolom wajib. Dipanggil sebelum menulis artefak."""
    required = set(TABLE_COLUMNS[table])
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{table}: kolom wajib hilang -> {sorted(missing)}")
    if not allow_extra:
        extra = set(frame.columns) - required
        if extra:
            raise ValueError(f"{table}: kolom tak terduga -> {sorted(extra)}")


def check_unique(frame: pd.DataFrame, table: str) -> None:
    keys = list(PRIMARY_KEYS[table])
    dup = frame.duplicated(keys).sum()
    if dup:
        raise ValueError(f"{table}: {dup} baris duplikat pada kunci {keys}")


# ---------------------------------------------------------------------------
# Guard holdout / availability
# ---------------------------------------------------------------------------
def assert_before_holdout(frame: pd.DataFrame, date_col: str = "date") -> None:
    """Gagal bila ada baris pada/ setelah HOLDOUT_START. Dipakai semua role."""
    dates = pd.to_datetime(frame[date_col])
    bad = dates >= pd.Timestamp(HOLDOUT_START)
    if bad.any():
        raise ValueError(
            f"Kebocoran holdout: {int(bad.sum())} baris >= {HOLDOUT_START} "
            f"(max={dates.max().date()}). Hanya CGS-H6-01 yang boleh membuka."
        )


def assert_available(frame: pd.DataFrame, date_col: str = "date", avail_col: str = "available_at") -> None:
    """Aturan emas: available_at <= date untuk setiap baris fitur."""
    if avail_col not in frame.columns:
        raise ValueError(f"Kolom {avail_col!r} tidak ada; fitur tidak boleh tanpa available_at.")
    bad = pd.to_datetime(frame[avail_col]) > pd.to_datetime(frame[date_col])
    if bad.any():
        raise ValueError(f"{int(bad.sum())} baris punya {avail_col} > {date_col} (bocor ke depan).")


def sealed_dir(*, required: bool = True) -> Path:
    """Folder holdout di luar repo. Hanya CGS yang boleh menyetel env ini."""
    raw = os.environ.get("RENARO_SEALED_DIR", "").strip()
    if not raw:
        if required:
            raise RuntimeError("RENARO_SEALED_DIR belum diset. Jangan buka holdout tanpa ini.")
        return Path("")
    return Path(raw).resolve()


def has_unseal_key() -> bool:
    """Kunci dibuka CGS-H6-01. Kehadiran file = izin membuka holdout."""
    raw = os.environ.get("RENARO_SEALED_DIR", "").strip()
    if not raw:
        return False
    return (Path(raw).resolve() / "HOLDOUT_UNSEALED").is_file()


# ---------------------------------------------------------------------------
# Hash & reproduksi
# ---------------------------------------------------------------------------
def content_hash(frame: pd.DataFrame, keys: Sequence[str]) -> str:
    """Hash isi tabel, tidak bergantung pada byte Parquet."""
    ordered = frame.sort_values(list(keys)).reset_index(drop=True)
    row_hashes = pd.util.hash_pandas_object(ordered, index=False).to_numpy()
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def write_sha256sums(folder: str | Path, out_name: str = "SHA256SUMS") -> Path:
    """Tulis SHA256SUMS untuk semua file di folder (kecuali file itu sendiri)."""
    folder = Path(folder)
    lines = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != out_name):
        lines.append(f"{sha256_file(path)}  {path.relative_to(folder).as_posix()}")
    out = folder / out_name
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def as_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def parse_range(spec: str) -> tuple[date, date]:
    """'2018-01-02..2022-06-30' -> (date, date)."""
    start, _, end = spec.partition("..")
    if not end:
        raise ValueError(f"Rentang tidak valid: {spec!r}")
    return as_date(start), as_date(end)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    print(f"project_root={PROJECT_ROOT}")
    print(f"nodes={N_NODES} horizons={HORIZONS} holdout={HOLDOUT_START}")
    for key, spec in ORIGINS.items():
        print(f"{key:8s} {spec}")
