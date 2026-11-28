
"""Standard experiment runner for RAWIT MLE-H1-03."""

from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import json
import re
import subprocess

from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.contract import (
    PROJECT_ROOT,
    ORIGINS,
    SEEDS,
    PRIMARY_HORIZON,
    check_columns,
    check_unique,
)

from renaro.data.io import load_panel
from renaro.eval.metrics import evaluate


RUNS = PROJECT_ROOT / "experiments" / "runs"

REGISTRY = (
    PROJECT_ROOT / "experiments" / "registry.csv"
)

DATASET = (
    PROJECT_ROOT / "data" / "processed" / "dataset_v1"
)

GLOBAL_CONFIG = (
    PROJECT_ROOT / "configs" / "global.yaml"
)

MODEL_REGISTRY = {
    "seasonal_naive":
        "renaro.baselines.naive:run_seasonal_naive",

    "naive_last":
        "renaro.baselines.naive:run_naive_last",

    "lgbm":
        "renaro.baselines.lgbm:run_lgbm",

    "gwn":
        "renaro.baselines.gwn:run_gwn",

    "mtgnn":
        "renaro.baselines.mtgnn:run_mtgnn",

    "latent_regime":
        "renaro.baselines.latent_regime:run",

    "lag_graph":
        "renaro.baselines.lag_graph:run",

    "module1":
        "renaro.models.module1:run",

    "module23":
        "renaro.models.module23:run",

    "module4":
        "renaro.models.module4:run",
}

RUN_COLUMNS = (
    "model",
    "fold",
    "seed",
    "date",
    "prov_code",
    "h",
    "y_true",
    "y_pred",
)


def git_sha_clean() -> str:
    """Return current Git SHA; reject dirty tree."""

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            text=True,
        ).strip()

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as exc:

        raise RuntimeError(
            "Git repository tidak tersedia"
        ) from exc

    if status:
        raise RuntimeError(
            "Git working tree tidak bersih.\n"
            "Commit perubahan sebelum eksperimen.\n"
            + status
        )

    return sha


def make_run_id(
    model: str,
    origin: str,
    seed: int,
) -> str:

    wib = timezone(timedelta(hours=7))

    timestamp = datetime.now(wib).strftime(
        "%Y%m%d-%H%M"
    )

    safe_model = re.sub(
        r"[^a-zA-Z0-9_-]", "_", model
    )

    return (
        f"{timestamp}_{safe_model}_{origin}_s{seed}"
    )


def prepare_run_dir(run_id: str) -> Path:

    RUNS.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_dir = RUNS / run_id

    # Never overwrite an existing experiment.
    run_dir.mkdir(exist_ok=False)

    return run_dir


def resolve_model(name: str):

    if name not in MODEL_REGISTRY:
        raise ValueError(
            f"Model tidak terdaftar: {name}"
        )

    module_name, function_name = (
        MODEL_REGISTRY[name].split(":")
    )

    module = importlib.import_module(
        module_name
    )

    function = getattr(
        module, function_name
    )

    if not callable(function):
        raise TypeError(
            f"{name} tidak callable"
        )

    signature = inspect.signature(function)

    try:
        signature.bind(
            None, {}, "O1", 0
        )

    except TypeError as exc:

        raise TypeError(
            "Model harus menerima "
            "(panel, cfg, origin, seed)"
        ) from exc

    return function


def train_and_predict(
    model,
    panel,
    cfg: dict,
    origin: str,
    seed: int,
):

    preds = model(
        panel,
        cfg,
        origin,
        seed,
    )

    if not isinstance(preds, pd.DataFrame):
        raise TypeError(
            "Model harus mengembalikan DataFrame"
        )

    check_columns(preds, "preds")
    check_unique(preds, "preds")

    required = {
        "part",
        "y_mask",
        "target_date",
    }

    missing = required - set(preds.columns)

    if missing:
        raise ValueError(
            f"Kolom evaluasi hilang: {missing}"
        )

    if preds.empty:
        raise ValueError("Prediksi kosong")

    if set(preds["part"]) != {"val", "test"}:
        raise ValueError(
            "Prediksi harus berisi val dan test"
        )

    if not preds["fold"].eq(origin).all():
        raise ValueError("Fold tidak sesuai")

    if not preds["seed"].eq(seed).all():
        raise ValueError("Seed tidak sesuai")

    if not preds["model"].eq(cfg["model"]).all():
        raise ValueError("Nama model tidak sesuai")

    holdout = pd.Timestamp(
        cfg["global"]["holdout_start"]
    )

    for col in ("date", "target_date"):

        dates = pd.to_datetime(preds[col])

        if dates.isna().any():
            raise ValueError("Tanggal tidak valid")

        if dates.ge(holdout).any():
            raise PermissionError(
                "Prediksi memasuki HOLDOUT"
            )

    metrics_df = evaluate(
        preds,
        group_cols=(
            "model",
            "fold",
            "seed",
            "part",
            "h",
        ),
    )

    primary = metrics_df.loc[
        metrics_df["part"].eq("val")
        & metrics_df["h"].eq(PRIMARY_HORIZON)
    ]

    if len(primary) != 1:
        raise ValueError(
            "Primary validation metric tidak valid"
        )

    val_mae = float(
        primary.iloc[0]["mae"]
    )

    if not np.isfinite(val_mae):
        raise ValueError("Validation MAE tidak valid")

    coverage = (
        preds.assign(
            valid_prediction=np.isfinite(
                preds["y_pred"]
            )
        )
        .loc[lambda x: x["y_mask"].eq(True)]
        .groupby(["part", "h"])
        ["valid_prediction"]
        .mean()
        .reset_index(name="coverage")
    )

    metrics = {
        "model": cfg["model"],
        "origin": origin,
        "seed": seed,
        "split_hash": panel.split_hash,
        "primary_horizon": PRIMARY_HORIZON,
        "val_mae": val_mae,
        "results": json.loads(
            metrics_df.to_json(orient="records")
        ),
        "coverage": json.loads(
            coverage.to_json(orient="records")
        ),
    }

    if "training" in preds.attrs:
        metrics["training"] = preds.attrs["training"]

    return preds, metrics


def write_outputs(
    run_dir: Path,
    preds: pd.DataFrame,
    metrics: dict,
    ckpt=None,
) -> None:

    check_columns(preds, "preds")
    check_unique(preds, "preds")

    extra_cols = [
        col for col in preds.columns
        if col not in RUN_COLUMNS
    ]

    preds = preds[
        list(RUN_COLUMNS) + extra_cols
    ]

    preds.to_parquet(
        run_dir / "preds.parquet",
        index=False,
    )

    (run_dir / "metrics.json").write_text(
        json.dumps(
            metrics,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    if ckpt is not None:

        import torch

        torch.save(
            ckpt,
            run_dir / "ckpt.pt",
        )


def append_registry(
    run_id: str,
    model: str,
    origin: str,
    seed: int,
    metrics: dict,
    cfg: dict,
) -> None:

    REGISTRY.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "run_id",
        "model",
        "origin",
        "seed",
        "split_hash",
        "val_mae",
        "status",
    ]

    row = {
        "run_id": run_id,
        "model": model,
        "origin": origin,
        "seed": seed,
        "split_hash": cfg["split_hash"],
        "val_mae": metrics["val_mae"],
        "status": "completed",
    }

    exists = (
        REGISTRY.exists()
        and REGISTRY.stat().st_size > 0
    )

    if exists:

        with REGISTRY.open(
            encoding="utf-8",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames != fields:
                raise ValueError(
                    "Skema registry berbeda"
                )

            if any(
                r["run_id"] == run_id
                for r in reader
            ):
                raise ValueError(
                    "Run ID sudah terdaftar"
                )

    with REGISTRY.open(
        "a",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="RAWIT experiment runner"
    )

    parser.add_argument(
        "--model",
        required=True,
        choices=sorted(MODEL_REGISTRY),
    )

    parser.add_argument(
        "--origin",
        required=True,
        choices=sorted(ORIGINS),
    )

    parser.add_argument(
        "--seed",
        required=True,
        type=int,
        choices=list(SEEDS),
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    if args.origin == "HOLDOUT":
        raise PermissionError(
            "HOLDOUT masih SEALED"
        )

    sha = git_sha_clean()

    config_path = args.config

    if config_path is None:

        config_path = (
            PROJECT_ROOT
            / "configs"
            / "models"
            / f"{args.model}.yaml"
        )

    if config_path.exists():

        cfg = yaml.safe_load(
            config_path.read_text(
                encoding="utf-8"
            )
        ) or {}

    elif args.model in (
        "naive_last",
        "seasonal_naive",
    ) and args.config is None:

        cfg = {}

    else:

        raise FileNotFoundError(
            f"Config tidak tersedia: {config_path}"
        )

    global_cfg = yaml.safe_load(
        GLOBAL_CONFIG.read_text(
            encoding="utf-8"
        )
    )

    default_dataset = (
        PROJECT_ROOT / "data" / "synth" / "default" if args.model == "module1" else DATASET
    )
    dataset = args.dataset or default_dataset
    panel = load_panel(dataset)

    cfg.update({
        "model": args.model,
        "origin": args.origin,
        "seed": args.seed,
        "dataset": str(dataset.resolve()),
        "split_hash": panel.split_hash,
        "global": global_cfg,
    })

    model = resolve_model(args.model)

    run_id = make_run_id(
        args.model,
        args.origin,
        args.seed,
    )

    run_dir = prepare_run_dir(run_id)

    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(
            cfg,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (run_dir / "git_sha.txt").write_text(
        sha + "\n",
        encoding="utf-8",
    )

    log_path = run_dir / "log.txt"

    log_path.write_text(
        f"Run ID: {run_id}\n"
        f"Git SHA: {sha}\n"
        f"Split hash: {panel.split_hash}\n"
        f"Model: {args.model}\n"
        f"Origin: {args.origin}\n"
        f"Seed: {args.seed}\n",
        encoding="utf-8",
    )

    print("Run ID:", run_id)
    print("Git SHA:", sha)
    print("Split hash:", panel.split_hash)

    try:

        preds, metrics = train_and_predict(
            model,
            panel,
            cfg,
            args.origin,
            args.seed,
        )

        write_outputs(
            run_dir,
            preds,
            metrics,
        )

        append_registry(
            run_id,
            args.model,
            args.origin,
            args.seed,
            metrics,
            cfg,
        )

    except Exception as exc:

        with log_path.open(
            "a", encoding="utf-8"
        ) as file:

            file.write(
                f"\nStatus: FAILED\n"
                f"Error: {exc}\n"
            )

        raise

    with log_path.open(
        "a", encoding="utf-8"
    ) as file:

        file.write(
            "\nStatus: COMPLETED\n"
        )

    print("\nValidation MAE:", metrics["val_mae"])
    print("Status: COMPLETED")
    print("Run directory:", run_dir)


if __name__ == "__main__":
    main()
