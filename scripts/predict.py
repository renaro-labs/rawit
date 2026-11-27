#!/usr/bin/env python3
"""MLE-H5-03 · Inferensi model beku Gate 2 (TIDAK melatih apa pun).

Pemakaian resmi (CGS-H6-01, sekali, setelah tag ``gate2-freeze``)::

    python scripts/predict.py --manifest frozen/manifest.yaml \
        --context data/processed/dataset_v1 \
        --holdout $env:RENARO_SEALED_DIR\\holdout_v1\\panel_v1 \
        --out reports/holdout/predictions

Langkah:
1. verifikasi SHA-256 semua checkpoint di manifest (satu saja tidak cocok -> berhenti);
2. sambungkan konteks ``dataset_v1`` (< ``--start``) dengan panel periode baru
   (>= ``--start``); prefix panel baru wajib identik dengan konteks;
3. untuk setiap model x seed: muat checkpoint, prediksi semua decision date
   ``start <= d_k <= end`` dengan ``d_{k+h} <= end`` (aturan bagian uji), tulis
   ``preds_<model>_s<seed>.parquet``;
4. tulis ``predict_log.json`` (commit, waktu, SHA-256 manifest/checkpoint/output).

Membaca tanggal >= 2026-06-01 butuh kunci ``HOLDOUT_UNSEALED`` di
``RENARO_SEALED_DIR``. File output yang sudah ada tidak pernah ditimpa.
``--start/--end/--fold`` hanya untuk uji kering (mis. periode uji O3).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renaro.frozen import combine_panels, load_ckpt, load_global, predict_frozen, sha256_file, tidy  # noqa: E402


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def manifest_entries(manifest: dict) -> list[dict]:
    rows = []
    for entry in manifest["models"]:
        ckpts, shas, seeds = entry["checkpoints"], entry["sha256"], entry["seeds"]
        if not (len(ckpts) == len(shas) == len(seeds)):
            raise ValueError(f"{entry['name']}: jumlah checkpoints/sha256/seeds tidak sama")
        for seed, ckpt, sha in zip(seeds, ckpts, shas):
            rows.append({"name": entry["name"], "seed": int(seed), "ckpt": ckpt, "sha256": sha})
    return rows


def verify_checkpoints(rows: list[dict]) -> None:
    bad = []
    for r in rows:
        path = resolve(r["ckpt"])
        if not path.is_file():
            bad.append(f"{r['ckpt']}: tidak ada")
            continue
        got = sha256_file(path)
        if got != r["sha256"]:
            bad.append(f"{r['ckpt']}: {got} != {r['sha256']}")
    if bad:
        raise SystemExit("BERHENTI: checkpoint tidak cocok dengan manifest (lapor RL):\n  " + "\n  ".join(bad))
    print(f"[ok] SHA-256 {len(rows)}/{len(rows)} checkpoint cocok dengan manifest", flush=True)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    glob = load_global()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--context", required=True, help="dataset_v1 (konteks < start)")
    ap.add_argument("--holdout", required=True, help="panel periode baru (format dataset_v1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", default=glob["holdout_start"])
    ap.add_argument("--end", default=glob["holdout_end"])
    ap.add_argument("--fold", default="HOLDOUT")
    ap.add_argument("--models", help="subset nama model (default: semua di manifest)")
    args = ap.parse_args(argv)

    wib = timezone(timedelta(hours=7))
    started = datetime.now(wib).isoformat(timespec="seconds")
    manifest_path = resolve(args.manifest)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    rows = manifest_entries(manifest)
    if args.models:
        keep = set(args.models.split(","))
        unknown = keep - {r["name"] for r in rows}
        if unknown:
            raise SystemExit(f"Model tidak ada di manifest: {sorted(unknown)}")
        rows = [r for r in rows if r["name"] in keep]
    verify_checkpoints(rows)

    out = resolve(args.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / f"preds_{r['name']}_s{r['seed']}.parquet" for r in rows]
    existing = [t.name for t in targets if t.exists()]
    if existing or (out / "predict_log.json").exists():
        raise SystemExit(f"BERHENTI: output sudah ada di {out} (tidak ditimpa): {existing or ['predict_log.json']}")

    panel = combine_panels(resolve(args.context), resolve(args.holdout), pd.Timestamp(args.start))
    print(f"[ok] panel gabungan {panel.dates.min().date()}..{panel.dates.max().date()} "
          f"({len(panel.dates)} hari kerja); periode baru >= {args.start}", flush=True)

    log = {"started_at": started, "git_head": git_head(), "manifest": str(args.manifest),
           "manifest_sha256": sha256_file(manifest_path),
           "freeze_commit": manifest.get("freeze_commit"), "context": str(args.context),
           "holdout": str(args.holdout), "start": str(args.start), "end": str(args.end),
           "fold": args.fold, "reads_holdout": panel.meta["reads_holdout"], "outputs": []}
    for r, target in zip(rows, targets):
        ckpt = load_ckpt(resolve(r["ckpt"]), r["sha256"])
        if ckpt["model"] != r["name"] or int(ckpt["seed"]) != r["seed"]:
            raise SystemExit(f"Isi checkpoint {r['ckpt']} tidak sesuai manifest ({ckpt['model']}/{ckpt['seed']})")
        preds = tidy(predict_frozen(ckpt, panel, args.start, args.end, fold=args.fold))
        preds.to_parquet(target, index=False)
        log["outputs"].append({"model": r["name"], "seed": r["seed"], "file": target.name,
                               "rows": int(len(preds)), "sha256": sha256_file(target),
                               "date_min": str(preds["date"].min().date()),
                               "date_max": str(preds["date"].max().date()),
                               "checkpoint": r["ckpt"], "checkpoint_sha256": r["sha256"]})
        print(f"[ok] {target.name}: {len(preds)} baris", flush=True)
    log["finished_at"] = datetime.now(wib).isoformat(timespec="seconds")
    (out / "predict_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"SELESAI: {len(rows)} file prediksi di {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
