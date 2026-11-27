#!/usr/bin/env python3
"""MLE-H5-03 · Gate 2: latih model wajib (O1-O3 + refit HOLDOUT) dengan config beku.

Satu run = satu (model, origin, seed) -> ``experiments/runs/g2_<model>_<origin>_s<seed>/``:
``config.yaml``, ``git_sha.txt``, ``ckpt.pt`` (+ ``ckpt.sha256``), ``preds.parquet``,
``summary.json``, ``log.txt``; plus satu baris di ``experiments/registry.csv``.

Aturan:
* working tree harus bersih (kecuali ``experiments/registry.csv`` yang memang
  bertambah per run) -> SHA commit tercatat di setiap run;
* origin ``HOLDOUT`` = refit (train <= 2025-12-31, val 2026-01-01..05-31);
  bagian test HOLDOUT tetap SEALED dan tidak pernah dibentuk;
* run yang sudah ada tidak ditimpa (dilewati bila lengkap).

Contoh::

    python scripts/run_gate2.py --model module1 --origin O1 --seed 0
    python scripts/run_gate2.py --models module1,gwn --origins O1,O2,O3,HOLDOUT --seeds 0,1,2,3,4
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renaro.contract import SEEDS  # noqa: E402
from renaro.data.io import load_panel  # noqa: E402
from renaro.frozen import MODELS, config_path, load_config, load_global, metrics, save_ckpt, tidy, train_frozen  # noqa: E402

# Impor eager semua modul yang dipakai train_frozen, supaya kode yang dieksekusi
# = kode pada commit yang dicatat di git_sha.txt walau antrean berjalan berjam-jam.
import renaro.baselines.gwn  # noqa: E402,F401
import renaro.baselines.lag_graph  # noqa: E402,F401
import renaro.baselines.latent_regime  # noqa: E402,F401
import renaro.baselines.lgbm  # noqa: E402,F401
import renaro.baselines.mtgnn  # noqa: E402,F401
import renaro.features.tabular  # noqa: E402,F401
import renaro.models.module1  # noqa: E402,F401
import renaro.models.module1_training  # noqa: E402,F401
import renaro.models.module23  # noqa: E402,F401
import renaro.train_loop  # noqa: E402,F401

RUNS = ROOT / "experiments" / "runs"
REGISTRY = ROOT / "experiments" / "registry.csv"
LOCK = ROOT / "experiments" / ".registry.lock"
FIELDS = ["run_id", "model", "origin", "seed", "split_hash", "val_mae", "status"]
ALLOWED_DIRTY = {"experiments/registry.csv", "experiments/.registry.lock"}
ORIGINS = ("O1", "O2", "O3", "HOLDOUT")


def git_sha_clean() -> str:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    dirty = [ln for ln in status.splitlines() if ln.strip() and ln[3:].strip() not in ALLOWED_DIRTY]
    if dirty:
        raise RuntimeError("Working tree tidak bersih; commit dulu:\n" + "\n".join(dirty))
    return sha


@contextmanager
def registry_lock(timeout: float = 600.0):
    start = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Lock registry macet: {LOCK}")
            time.sleep(0.2)
    try:
        yield
    finally:
        os.close(fd)
        os.unlink(LOCK)


def append_registry(run_id: str, model: str, origin: str, seed: int, split_hash: str, val_mae: float) -> None:
    with registry_lock():
        with REGISTRY.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != FIELDS:
                raise ValueError("Skema registry berbeda")
            if any(r["run_id"] == run_id for r in reader):
                raise ValueError(f"Run ID sudah terdaftar: {run_id}")
        with REGISTRY.open("a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writerow({
                "run_id": run_id, "model": model, "origin": origin, "seed": seed,
                "split_hash": split_hash, "val_mae": f"{val_mae:.4f}", "status": "completed"})


def registered(run_id: str) -> bool:
    with REGISTRY.open(encoding="utf-8", newline="") as fh:
        return any(r["run_id"] == run_id for r in csv.DictReader(fh))


def run_one(panel, model: str, origin: str, seed: int, sha: str) -> str:
    run_id = f"g2_{model}_{origin}_s{seed}"
    out = RUNS / run_id
    if out.exists():
        if (out / "ckpt.pt").is_file() and (out / "summary.json").is_file() and registered(run_id):
            print(f"[skip] {run_id} sudah lengkap", flush=True)
            return "skip"
        raise FileExistsError(f"{out} ada tetapi tidak lengkap; periksa manual (tidak ditimpa)")
    cfg = load_config(model)
    glob = load_global()
    wib = timezone(timedelta(hours=7))
    t0 = time.time()
    started = datetime.now(wib).isoformat(timespec="seconds")
    print(f"[run ] {run_id} (sha {sha[:7]})", flush=True)
    preds, ckpt, stats = train_frozen(model, panel, origin, seed, cfg=cfg, glob=glob)
    ckpt.update(run_id=run_id, git_sha=sha, config_path=config_path(model).relative_to(ROOT).as_posix())
    preds = tidy(preds)
    m = metrics(preds)
    val_mae = m["val_h10_mae"]
    tmp = RUNS / f".tmp_{run_id}"
    tmp.mkdir(parents=True, exist_ok=False)
    (tmp / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (tmp / "git_sha.txt").write_text(sha + "\n", encoding="utf-8")
    digest = save_ckpt(ckpt, tmp / "ckpt.pt")
    (tmp / "ckpt.sha256").write_text(f"{digest}  ckpt.pt\n", encoding="utf-8")
    preds.to_parquet(tmp / "preds.parquet", index=False)
    summary = {
        "run_id": run_id, "model": model, "family": MODELS[model], "origin": origin, "seed": seed,
        "git_sha": sha, "split_hash": panel.split_hash,
        "config_path": config_path(model).relative_to(ROOT).as_posix(), "config": cfg,
        "ckpt_sha256": digest, "metrics": m, "training": stats,
        "started_at": started, "seconds": round(time.time() - t0, 1),
        "max_date": str(preds["date"].max().date()), "max_target_date": str(preds["target_date"].max().date()),
    }
    (tmp / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (tmp / "log.txt").write_text(
        f"Run ID: {run_id}\nGit SHA: {sha}\nSplit hash: {panel.split_hash}\nModel: {model}\n"
        f"Origin: {origin}\nSeed: {seed}\nval_h10_mae: {val_mae:.4f}\nStatus: COMPLETED\n", encoding="utf-8")
    tmp.rename(out)
    append_registry(run_id, model, origin, seed, panel.split_hash, val_mae)
    print(f"[done] {run_id} val_h10_mae={val_mae:.2f} ({summary['seconds']} s)", flush=True)
    return "done"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--origin", choices=ORIGINS)
    ap.add_argument("--seed", type=int, choices=list(SEEDS))
    ap.add_argument("--models", help="daftar dipisah koma")
    ap.add_argument("--origins", help="daftar dipisah koma")
    ap.add_argument("--seeds", help="daftar dipisah koma")
    ap.add_argument("--threads", type=int, default=0, help="torch.set_num_threads (0 = default)")
    args = ap.parse_args()
    models = (args.models or args.model or "").split(",")
    origins = (args.origins or args.origin or "").split(",")
    seeds = [int(s) for s in (args.seeds or ("" if args.seed is None else str(args.seed))).split(",") if s != ""]
    if not models[0] or not origins[0] or not seeds:
        ap.error("butuh --model/--models, --origin/--origins, --seed/--seeds")
    for m in models:
        if m not in MODELS:
            ap.error(f"model tidak dikenal: {m}")
    for o in origins:
        if o not in ORIGINS:
            ap.error(f"origin tidak dikenal: {o}")
    if args.threads:
        import torch
        torch.set_num_threads(args.threads)
    sha = git_sha_clean()
    panel = load_panel(ROOT / "data" / "processed" / "dataset_v1")
    failed = []
    for model in models:
        for origin in origins:
            for seed in seeds:
                try:
                    run_one(panel, model, origin, seed, sha)
                except Exception as exc:  # noqa: BLE001 - lanjutkan antrean, laporkan di akhir
                    traceback.print_exc()
                    failed.append(f"g2_{model}_{origin}_s{seed}: {exc}")
                    tmp = RUNS / f".tmp_g2_{model}_{origin}_s{seed}"
                    if tmp.exists():
                        for f in tmp.iterdir():
                            f.unlink()
                        tmp.rmdir()
    if failed:
        print("GAGAL:\n" + "\n".join(failed), flush=True)
        sys.exit(1)
    print("SEMUA SELESAI", flush=True)


if __name__ == "__main__":
    main()
