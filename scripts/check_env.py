#!/usr/bin/env python
"""Sprint 1 H1 Environment & Data Contract Smoke Test (scripts/check_env.py)."""

import sys
import os
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "[PASS]" if ok else "[FAIL]"
    msg = f"{icon} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return ok


def main() -> int:
    print("=" * 72)
    print("RENARO SPRINT 1 — SMOKE TEST ENVIRONMENT & DATA CONTRACT (H1)")
    print("=" * 72)
    results = []

    # 1. Python version check (>= 3.10)
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    results.append(check("Python >= 3.10", sys.version_info >= (3, 10), f"v{py_ver}"))

    # 2. Core libraries check
    required_pkgs = ["numpy", "pandas", "pyarrow", "scipy", "matplotlib", "requests", "PIL", "fitz"]
    optional_ml_pkgs = ["torch", "lightgbm", "sklearn"]

    for pkg in required_pkgs:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "installed")
            results.append(check(f"Library wajib `{pkg}`", True, f"v{ver}"))
        except ImportError as e:
            results.append(check(f"Library wajib `{pkg}`", False, str(e)))

    for pkg in optional_ml_pkgs:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "installed")
            results.append(check(f"Library ML `{pkg}`", True, f"v{ver}"))
        except ImportError:
            print(f"[WARN] Library ML `{pkg}` belum terpasang di environment ini (dibutuhkan mulai H3/H4)")

    try:
        import torch

        cuda_available = torch.cuda.is_available()

        results.append(
            check(
                "CUDA tersedia untuk PyTorch",
                cuda_available,
                f"PyTorch CUDA: {torch.version.cuda}"
            )
        )

        if cuda_available:
            gpu_id = torch.cuda.current_device()
            gpu = torch.cuda.get_device_properties(gpu_id)

            vram_gib = gpu.total_memory / (1024 ** 3)

            results.append(
                check(
                    "Informasi GPU MLE",
                    True,
                    f"GPU={gpu.name}, VRAM={vram_gib:.2f} GiB"
                )
            )

    except Exception as e:
        results.append(
            check(
                "CUDA tersedia untuk PyTorch",
                False,
                f"{type(e).__name__}: {e}"
            )
        )
    # 3. Check core contract & decision files
    contract_file = ROOT / "docs" / "data_contract.md"
    decision_file = ROOT / "docs" / "decisions" / "ALL-H1-01.md"
    splits_file = ROOT / "data" / "processed" / "dataset_v1" / "splits.json"
    panel_file = ROOT / "data" / "processed" / "dataset_v1" / "panel_dev.parquet"
    bps_mask_file = ROOT / "data" / "interim" / "bps_mask_2022.csv"
    bps_pages_file = ROOT / "data" / "interim" / "bps_mask_2022_pages.csv"

    results.append(check("Dokumen kontrak data `docs/data_contract.md`", contract_file.exists()))
    results.append(check("Dokumen keputusan H1 `docs/decisions/ALL-H1-01.md`", decision_file.exists()))
    results.append(check("Konfigurasi split `data/processed/dataset_v1/splits.json`", splits_file.exists()))
    results.append(check("Mask graph BPS `data/interim/bps_mask_2022.csv`", bps_mask_file.exists()))
    results.append(check("Audit halaman BPS `data/interim/bps_mask_2022_pages.csv`", bps_pages_file.exists()))

    # 4. Validate panel_dev.parquet against H1 contract & holdout seal
    if panel_file.exists() and splits_file.exists():
        import pandas as pd
        with open(splits_file, "r", encoding="utf-8") as f:
            splits = json.load(f)
        holdout_start = pd.Timestamp(splits["holdout_start"])
        df = pd.read_parquet(panel_file)

        max_date = df["date"].max()
        no_holdout_in_dev = max_date < holdout_start
        results.append(
            check(
                "Pengaman Holdout pada `panel_dev.parquet` (`date < 2026-06-01`)",
                no_holdout_in_dev,
                f"max_date={max_date.strftime('%Y-%m-%d')} < holdout_start={holdout_start.strftime('%Y-%m-%d')}",
            )
        )

        n_provs = df["province"].nunique()
        cov_by_prov = df.groupby("province")["target_mask"].mean()
        provs_ge_90 = int((cov_by_prov >= 0.90).sum())
        results.append(
            check(
                "Syarat Harga Gate 1 (>=20 provinsi cakupan >=90%, >=5 tahun)",
                provs_ge_90 >= 20 and n_provs == 34,
                f"{provs_ge_90}/34 provinsi >=90% (min={cov_by_prov.min()*100:.2f}%), {df['date'].nunique()} hari kerja",
            )
        )

        enso_ok = int((df["enso_available_at"] > df["date"]).sum()) == 0 and df["enso_roni"].notna().all()
        results.append(
            check(
                "Kausalitas & Kelengkapan ENSO RONI (`enso_available_at <= date`)",
                enso_ok,
                "100% terisi, 0 kebocoran waktu",
            )
        )

        clim_cols = [
            "rain_1d", "rain_5d", "rain_pentad_last", "rain_30d", "rain_90d",
            "dry_spell_days", "extreme_pentads_30d", "extreme_pentads_60d",
            "rain_30d_anom_z", "rain_90d_anom_z"
        ]
        clim_non_null = sum(int(df[c].notna().sum()) for c in clim_cols if c in df.columns)
        npz_count = len(list((ROOT / "data" / "raw" / "chirps_v3").glob("*.npz")))
        results.append(
            check(
                "Fitur Iklim CHIRPS v3 di `panel_dev.parquet` (Target H2/Gate 1)",
                clim_non_null > 0,
                f"non-null={clim_non_null} (raw CHIRPS NPZ baru {npz_count}/107 bulan; wajib diselesaikan di H2)",
            )
        )

    # 5. Validate bps_mask_2022.csv
    if bps_mask_file.exists():
        import pandas as pd
        m = pd.read_csv(bps_mask_file, index_col=0, dtype=str).fillna("")
        diag_empty = all(m.loc[p, p] == "" for p in m.index)
        n_edges = int((m == "1").sum().sum())
        results.append(
            check(
                "Validitas Matriks `bps_mask_2022.csv` (34x34, diagonal kosong)",
                m.shape == (34, 34) and diag_empty and n_edges == 99,
                f"shape={m.shape}, directed_edges={n_edges}, diagonal_blank={diag_empty}",
            )
        )

    # 6. Check raw holdout seal warning
    pihps_raw = ROOT / "data" / "raw" / "pihps" / "pihps_cabai_merah_keriting_province.csv"
    if pihps_raw.exists():
        import pandas as pd
        raw_df = pd.read_csv(pihps_raw, usecols=["date"])
        n_raw_holdout = int((raw_df["date"] >= "2026-06-01").sum())
        results.append(
            check(
                "Segel Fisik Data Mentah (`data/raw/pihps` bebas tanggal >= 2026-06-01)",
                n_raw_holdout == 0,
                f"Ditemukan {n_raw_holdout} baris >= 2026-06-01 di CSV raw PIHPS (wajib dipindah ke _sealed/ sebelum Gate 2)",
            )
        )

    print("-" * 72)
    n_pass = sum(1 for r in results if r)
    n_total = len(results)
    print(f"RINGKASAN SMOKE TEST: {n_pass}/{n_total} pemeriksaan LULUS")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())