"""MDE-H3-01 · Bangun dataset v1 (CLI). Logika ada di src/renaro/data/dataset_v1.py.

Contoh:
  python scripts/build_dataset.py --start 2017-07-01 --end 2026-05-31 --out data/processed/dataset_v1
  # CGS-H3-02 (holdout, kode yang sama):
  #   $env:RENARO_SEALED_DIR=...; python scripts/build_dataset.py --raw-root <dir> --end 2026-11-30 --allow-holdout --out <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renaro.contract import HOLDOUT_START, has_unseal_key, sealed_dir  # noqa: E402
from renaro.data import dataset_v1 as D  # noqa: E402


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Build dataset v1")
    ap.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2017, 7, 1))
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2026, 5, 31))
    ap.add_argument("--raw-root", type=Path, default=Path("data"),
                    help="akar input: <raw-root>/interim/*, <raw-root>/ref/provinces.csv")
    ap.add_argument("--coverage", type=Path, default=Path("reports/qa/coverage_pihps.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/processed/dataset_v1"))
    ap.add_argument("--allow-holdout", action="store_true",
                    help="HANYA CGS-H3-02/H6-01; butuh RENARO_SEALED_DIR berisi HOLDOUT_UNSEALED")
    ap.add_argument("--report", type=Path, default=None,
                    help="laporan QA (default reports/qa/dataset_v1.md; tidak ditulis saat --allow-holdout)")
    ap.add_argument("--truncation-samples", type=int, default=3, help="jumlah T acak uji truncation")
    ap.add_argument("--allow-missing-climate", action="store_true",
                    help="fallback 'v1-price' (playbook: kalau iklim belum siap); kolom iklim NaN")
    args = ap.parse_args(argv)

    if args.allow_holdout:
        sealed_dir()  # gagal bila RENARO_SEALED_DIR tidak diset
        if not has_unseal_key():
            raise SystemExit("Holdout terkunci: HOLDOUT_UNSEALED tidak ada di RENARO_SEALED_DIR.")
    elif args.end >= HOLDOUT_START:
        raise SystemExit(f"--end {args.end} >= {HOLDOUT_START} tanpa --allow-holdout. Ditolak.")

    paths = D.input_paths(args.raw_root, args.coverage)
    inp = D.read_inputs(paths, allow_missing_climate=args.allow_missing_climate)
    if not args.allow_holdout:
        inp = D.truncate_inputs(inp, pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1))
    panel, target, nodes = D.build(inp, args.start, args.end, allow_holdout=args.allow_holdout)

    if args.allow_holdout:
        checks = {k: v for k, v in D.quick_checks(panel).items() if k != "max_date<holdout"}
    else:
        checks = D.leakage_suite(panel, inp, args.start, args.end, args.truncation_samples)
    if not all(checks.values()):
        bad = [k for k, v in checks.items() if not v]
        raise SystemExit(f"Uji kebocoran GAGAL (tidak ada yang ditulis): {bad}")

    no_clim = inp.climate is None
    used = {"prices", "calendar", "provinces", "mask", "coverage", "roni"} | (set() if no_clim else {"climate"})
    meta = {"start": args.start, "end": args.end,
            "version": "v1-price" if no_clim else D.VERSION,
            "climate": "TIDAK ADA (v1-price)" if no_clim else Path(paths["climate"]).as_posix(),
            "inputs_sha256": D.inputs_sha256(paths, used)}
    v = D.write_outputs(args.out, panel, target, nodes, inp.mask, meta)
    report = args.report or (None if args.allow_holdout else Path("reports/qa/dataset_v1.md"))
    if report:
        D.qa_report(report, panel, target, nodes, v, checks, args.out)

    n_obs = int(target["is_observed"].sum())
    print(f"[panel] {len(panel):,} baris = {v['n_dates']} hari kerja x 34; {v['date_min']}..{v['date_max']}; "
          f"{len(panel.columns)} kolom")
    print(f"[target] observasi {n_obs:,}/{len(target):,} ({n_obs / len(target):.1%})")
    print(f"[nodes] include={int(nodes['include'].sum())}/34")
    print(f"[iklim] {'TIDAK ADA -> v1-price (kolom iklim NaN)' if no_clim else 'ok'}; "
          f"missing rain_pentad_anom={panel['rain_pentad_anom'].isna().mean():.1%}, roni={panel['roni'].isna().mean():.1%}")
    print("[cek] " + ", ".join(f"{k}={'OK' if ok else 'GAGAL'}" for k, ok in checks.items()))
    if report:
        print(f"[qa] {report}")
    print(f"[out] {args.out}  version={v['version']}  content_hash panel={v['content_hash']['panel'][:12]} "
          f"target={v['content_hash']['target'][:12]}")


if __name__ == "__main__":
    main()
