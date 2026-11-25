"""Summarize the five paired O1 runs on the verified synthetic benchmark."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from renaro.contract import SEEDS, sha256_file
from renaro.data.datasets import WindowDataset, WindowSpec
from renaro.data.io import load_panel
from renaro.eval.splits import rolling_origin, split_indices

DATASET = Path("data/synth/default")
KEYS = ["part", "h", "date", "prov_code"]


def read_run(prefix, seed, name, split_hash):
    directory = Path(f"{prefix}{seed}")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    if (summary["model"], summary["origin"], summary["seed"], summary["split_hash"]) != (
        name, "O1", seed, split_hash,
    ) or summary.get("smoke"):
        raise ValueError(f"Incompatible run metadata in {directory}")
    predictions = pd.read_csv(
        directory / "preds.csv", dtype={"prov_code": str}, parse_dates=["date"],
    ).set_index(KEYS).sort_index()
    if not predictions.index.is_unique:
        raise ValueError(f"Duplicate evaluation keys in {directory}")
    if set(predictions.index.get_level_values("part")) != {"val", "test"}:
        raise ValueError(f"Expected validation and test predictions in {directory}")
    return summary, predictions


def compare(module1_prefix, gwn_prefix):
    panel = load_panel(DATASET)
    targets = panel.target.set_index(["date", "prov_code"])["price"]
    config = yaml.safe_load(Path("configs/global.yaml").read_text(encoding="utf-8"))
    spec = WindowSpec(window=config["window"], horizons=tuple(config["horizons"]))
    split = rolling_origin("O1", panel.dates)
    expected_keys = []
    for part in ("val", "test"):
        windows = WindowDataset(panel, "O1", part, spec)
        official = set(split_indices(split, panel.dates, part, horizon=max(spec.horizons)))
        dates = [panel.dates[k] for k in windows.decision_indices if k in official]
        expected_keys.append(pd.MultiIndex.from_product(
            [[part], spec.horizons, dates, panel.node_codes], names=KEYS,
        ))
    expected = expected_keys[0].append(expected_keys[1]).sort_values()
    rows = []
    memory = []
    run_configs = {}
    for seed in SEEDS:
        stats, module1 = read_run(module1_prefix, seed, "module1", panel.split_hash)
        baseline_stats, gwn = read_run(gwn_prefix, seed, "gwn", panel.split_hash)
        for name, run in (("module1", stats), ("gwn", baseline_stats)):
            settings = {key: value for key, value in run["config"].items() if key != "benchmark"}
            if run_configs.setdefault(name, settings) != settings:
                raise ValueError(f"{name} config differs for seed {seed}")
        if not module1.index.equals(expected) or not gwn.index.equals(expected):
            raise ValueError(f"Incomplete or extra evaluation keys for seed {seed}")
        if not module1.y_mask.equals(gwn.y_mask):
            raise ValueError(f"Evaluation keys or masks differ for seed {seed}")
        if not module1.y_true.equals(gwn.y_true):
            raise ValueError(f"Evaluation labels differ for seed {seed}")

        valid = module1.y_mask
        keys = module1.index.to_frame(index=False).loc[valid.to_numpy()]
        decisions = panel.dates.get_indexer(keys.date)
        if (decisions < 0).any():
            raise ValueError(f"Unknown decision date for seed {seed}")
        dates = panel.dates[decisions + keys.h.to_numpy() - 1]
        reference = targets.reindex(pd.MultiIndex.from_arrays([dates, keys.prov_code]))
        np.testing.assert_allclose(module1.loc[valid, "y_true"], reference, rtol=1e-6)
        paired = pd.DataFrame({
            "module1_mae": (module1.loc[valid, "y_pred"] - module1.loc[valid, "y_true"]).abs(),
            "gwn_mae": (gwn.loc[valid, "y_pred"] - gwn.loc[valid, "y_true"]).abs(),
        })
        if not np.isfinite(paired.to_numpy()).all():
            raise ValueError(f"Nonfinite errors for seed {seed}")
        scores = paired.groupby(level=["part", "h"]).mean()
        if set(scores.index) != {(part, h) for part in ("val", "test") for h in spec.horizons}:
            raise ValueError(f"Incomplete evaluation for seed {seed}")
        rows.extend(scores.reset_index().assign(seed=seed).to_dict("records"))
        memory.append({
            "seed": seed,
            "device": stats["device"],
            "batch_size": stats["config"]["batch_size"],
            "window": spec.window,
            "n_nodes": len(panel.node_codes),
            "peak_allocated_gb": stats["peak_allocated_gb"],
            "peak_reserved_gb": stats["peak_reserved_gb"],
        })

    results = pd.DataFrame(rows)
    means = results.groupby(["part", "h"])[["module1_mae", "gwn_mae"]].mean()
    means["module1_beats_gwn"] = means.module1_mae < means.gwn_mae
    val = means.loc["val", ["module1_mae", "gwn_mae"]].mean()
    calendar_file = run_configs["module1"].get("calendar_file")
    report = {
        "dataset": DATASET.as_posix(),
        "split_hash": panel.split_hash,
        "sha256": {
            name: sha256_file(DATASET / name)
            for name in ("panel.parquet", "target.parquet", "nodes.csv", "bps_mask.npy", "truth.npz")
        },
        "origin": "O1",
        "seeds": list(SEEDS),
        "module1_run_prefix": module1_prefix,
        "gwn_run_prefix": gwn_prefix,
        "config": run_configs,
        "calendar_sha256": sha256_file(calendar_file) if calendar_file else None,
        "validation_average_across_horizons": val.to_dict(),
        "validation_mae_dod_pass": bool(val.module1_mae < val.gwn_mae),
        "validation_each_horizon_pass": bool(means.loc["val", "module1_beats_gwn"].all()),
        "mae_by_horizon": means.reset_index().to_dict("records"),
        "training_memory": memory,
        "batch_32_memory_dod_pass": all(
            (row["batch_size"], row["window"], row["n_nodes"]) == (32, 60, 34)
            and row["device"].startswith("cuda")
            and row["peak_allocated_gb"] is not None and row["peak_allocated_gb"] < 3
            for row in memory
        ),
    }
    return results.assign(split_hash=panel.split_hash), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module1-prefix", required=True)
    parser.add_argument("--gwn-prefix", required=True)
    parser.add_argument("--out", type=Path, default=Path("reports/module1"))
    args = parser.parse_args()
    results, report = compare(args.module1_prefix, args.gwn_prefix)
    args.out.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out / "synth_default_O1_seed_metrics.csv", index=False)
    (args.out / "synth_default_O1_benchmark.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
