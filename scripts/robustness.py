#!/usr/bin/env python3
"""CGS-H5-01: graph-prior misspecification and joint climate-graph shift."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml

from renaro.data.datasets import FEATURES
from renaro.data.io import load_panel
from renaro.eval.metrics import mae, rmse, smape
from renaro.graph_perturb import perturbation_grid
from renaro.models.module1_training import fit, predict, prepare
from renaro.baselines.gwn import GraphWaveNetLite
from renaro.train_loop import fit as gwn_fit

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "experiments/handoff/module1_for_robustness.yaml"
SPLITS = ROOT / "data/processed/eval_splits"
OUT = ROOT / "reports/robustness"
PERT_DIR = ROOT / "data/processed/perturbations"
RUNS = ROOT / "experiments/runs"
REGISTRY = ROOT / "experiments/registry.csv"
ORIGIN = "O3"
TRAIN_PRIOR = "bps"
REGISTRY_FIELDS = ["run_id", "model", "origin", "seed", "split_hash",
                   "val_mae", "status"]


def load_handoff(path: Path = HANDOFF) -> dict:
    data = yaml.safe_load(path.read_text())
    if not data.get("checkpoints"):
        raise ValueError("handoff has no checkpoints")
    for item in data["checkpoints"]:
        p = ROOT / item["checkpoint"]
        if not p.is_file():
            raise FileNotFoundError(p)
    return data


def save_masks(base: np.ndarray) -> pd.DataFrame:
    PERT_DIR.mkdir(parents=True, exist_ok=True)
    rows, arrays = [], {}
    for name, mask, op, frac, seed in perturbation_grid(base):
        arrays[name] = mask.astype(np.uint8)
        rows.append({"name": name, "op": op, "p": float(frac), "pert_seed": seed,
                     "n_edges": int(mask.sum())})
    np.savez_compressed(PERT_DIR / "masks.npz", **arrays)
    manifest = pd.DataFrame(rows)
    manifest.to_csv(PERT_DIR / "manifest.csv", index=False)
    return manifest


def select_retrain_masks(masks):
    """Step 2 subset: clean baseline + p={10,50} x {drop,add,rewire}, pert seed 0."""
    selected = []
    for item in masks:
        _, _, op, frac, pert_seed = item
        if op == "clean":
            selected.append(item)
        elif (op in ("drop", "add", "rewire")
              and int(round(frac * 100)) in (10, 50) and pert_seed == 0):
            selected.append(item)
    return selected


def _register_run(run_id: str, model: str, seed: int, split_hash: str,
                  val_mae: float) -> None:
    fields = REGISTRY_FIELDS
    if REGISTRY.exists() and REGISTRY.stat().st_size > 0:
        reg = pd.read_csv(REGISTRY, dtype=str)
    else:
        reg = pd.DataFrame(columns=fields)
    reg = reg[reg["run_id"] != run_id]
    entry = pd.DataFrame([{
        "run_id": run_id, "model": model, "origin": ORIGIN, "seed": str(seed),
        "split_hash": split_hash, "val_mae": f"{val_mae:.6f}",
        "status": "completed",
    }], columns=fields)
    reg = pd.concat([reg, entry], ignore_index=True)
    reg.to_csv(REGISTRY, index=False)


def _save_retrain_run(run_id: str, rows: list[dict], *, model: str, mask_name: str,
                      seed: int, split_hash: str, stats: dict | None = None) -> None:
    """Persist per-run evidence under experiments/runs and the tracked registry."""
    frame = pd.DataFrame(rows)
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "metrics.csv", index=False)
    payload = {"run_id": run_id, "model": model, "origin": ORIGIN, "seed": seed,
               "train_prior": mask_name, "test_prior": "clean", "mode": "train",
               "split_hash": split_hash, "n_rows": int(len(frame))}
    if stats:
        payload.update({k: v for k, v in stats.items() if k != "history"})
    (out / "run.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    primary = frame[(frame["part"] == "val") & (frame["horizon"] == 10)]
    val_mae = float(primary["mae"].mean()) if len(primary) else float("nan")
    _register_run(run_id, model, seed, split_hash, val_mae)


def _metric_rows(preds: pd.DataFrame, split: pd.DataFrame, *, model_seed: int,
                 mask_name: str, op: str, p: float, pert_seed: int,
                 mode: str, part: str, train_prior: str, test_prior: str,
                 model_name: str = "module1") -> list[dict]:
    split = split.copy()
    split["date"] = pd.to_datetime(split["date"]).astype("datetime64[ns]")
    split["prov_code"] = split["prov_code"].astype(str).str.zfill(2)
    merged = preds.merge(split[["date", "prov_code", "label_primary"]],
                         on=["date", "prov_code"], how="left", validate="many_to_one")
    if merged["label_primary"].isna().any():
        raise ValueError("missing regime labels")
    merged = merged.rename(columns={"label_primary": "regime"})
    valid = merged[merged["y_mask"].astype(bool) &
                   np.isfinite(merged["y_true"]) & np.isfinite(merged["y_pred"])]
    rows = []
    for (h, regime), g in valid.groupby(["h", "regime"]):
        rows.append({"model": model_name, "train_prior": train_prior,
                     "test_prior": test_prior, "op": op, "p": p,
                     "pert_seed": pert_seed, "model_seed": model_seed,
                     "mode": mode, "part": part, "horizon": int(h),
                     "regime": regime, "mae": mae(g["y_true"], g["y_pred"]),
                     "rmse": rmse(g["y_true"], g["y_pred"]),
                     "smape": smape(g["y_true"], g["y_pred"]), "n": len(g)})
    return rows


def _predict_frame(model, loaders, device, prior, spec, part: str, panel) -> pd.DataFrame:
    frames = []
    for batch in loaders[part]:
        log_pred, _ = predict(model, batch, device, prior)
        pred = log_pred.float().exp().cpu().numpy()
        for i, k in enumerate(batch["t_index"].tolist()):
            for j, h in enumerate(spec.horizons):
                frames.append(pd.DataFrame({
                    "date": panel.dates[k], "prov_code": list(panel.node_codes),
                    "h": h, "y_true": batch["y"][i, j].numpy(),
                    "y_mask": batch["y_mask"][i, j].numpy(), "y_pred": pred[i, j],
                }))
    out = pd.concat(frames, ignore_index=True)
    out.loc[~out["y_mask"].astype(bool), "y_true"] = np.nan
    return out


def evaluate_test_mode(handoff: dict, panel, cfg: dict, glob: dict,
                       masks: list[tuple[str, np.ndarray, str, float, int]]) -> pd.DataFrame:
    rows = []
    for item in handoff["checkpoints"]:
        seed = int(item["seed"])
        model, spec, loaders, device, prior = prepare(
            panel, cfg, glob, ORIGIN, seed, ("val", "test"))
        ckpt = torch.load(ROOT / item["checkpoint"], map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
        model.to(device).eval()
        for mask_name, mask, op, frac, pert_seed in masks:
            cand = torch.as_tensor(mask, dtype=torch.bool, device=device)
            override = (prior[0], cand)
            for part in ("val", "test"):
                preds = _predict_frame(model, loaders, device, override, spec, part, panel)
                split = pd.read_parquet(SPLITS / f"{ORIGIN}_{part}.parquet")
                rows.extend(_metric_rows(
                    preds, split, model_seed=seed, mask_name=mask_name, op=op,
                    p=frac, pert_seed=pert_seed, mode="test", part=part,
                    train_prior=TRAIN_PRIOR, test_prior=mask_name))
            print(f"seed {seed} mask {mask_name}: done", flush=True)
    return pd.DataFrame(rows)


def retrain_mode(panel, cfg: dict, glob: dict, masks: list[tuple[str, np.ndarray, str, float, int]],
                 model_seeds: tuple[int, ...], epochs: int) -> pd.DataFrame:
    cfg = copy.deepcopy(cfg)
    cfg["batch_size"] = 32
    rows = []
    for mask_name, mask, op, frac, pert_seed in select_retrain_masks(masks):
        for seed in model_seeds:
            model, spec, loaders, device, prior = prepare(
                panel, cfg, glob, ORIGIN, seed, ("val", "test"))
            train_cand = torch.as_tensor(mask, dtype=torch.bool, device=device)
            stats = fit(model, loaders["train"], loaders["val"], device=device,
                        a_prior=(prior[0], train_cand), lr=float(cfg["lr"]), epochs=epochs,
                        patience=min(int(cfg.get("patience", 5)), epochs),
                        grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]))
            clean = torch.as_tensor(panel.mask > 0, dtype=torch.bool, device=device)
            run_rows = []
            for part in ("val", "test"):
                preds = _predict_frame(model, loaders, device, (prior[0], clean), spec, part, panel)
                split = pd.read_parquet(SPLITS / f"{ORIGIN}_{part}.parquet")
                run_rows.extend(_metric_rows(
                    preds, split, model_seed=seed, mask_name=mask_name, op=op,
                    p=frac, pert_seed=pert_seed, mode="train", part=part,
                    train_prior=mask_name, test_prior="clean"))
            run_id = f"robustness_module1_{mask_name}_s{seed}"
            _save_retrain_run(run_id, run_rows, model="module1", mask_name=mask_name,
                              seed=seed, split_hash=panel.split_hash, stats=stats)
            rows.extend(run_rows)
            print(f"retrain {mask_name} seed {seed}: done", flush=True)
    return pd.DataFrame(rows)


def _gwn_predict(model, loaders, device, prior, spec, part: str, panel) -> pd.DataFrame:
    import torch
    frames = []
    model.eval()
    with torch.no_grad():
        for batch in loaders[part]:
            x = batch["X"].to(device)
            log_pred = model(x, prior).float().cpu().numpy()
            for i, k in enumerate(batch["t_index"].tolist()):
                for j, h in enumerate(spec.horizons):
                    frames.append(pd.DataFrame({
                        "date": panel.dates[k], "prov_code": list(panel.node_codes),
                        "h": h, "y_true": batch["y"][i, j].numpy(),
                        "y_mask": batch["y_mask"][i, j].numpy(),
                        "y_pred": np.exp(log_pred[i, j]),
                    }))
    out = pd.concat(frames, ignore_index=True)
    out.loc[~out["y_mask"].astype(bool), "y_true"] = np.nan
    return out


def gwn_retrain_mode(panel, cfg: dict, glob: dict,
                     masks: list[tuple[str, np.ndarray, str, float, int]],
                     model_seeds: tuple[int, ...], epochs: int) -> pd.DataFrame:
    rows = []
    cfg = copy.deepcopy(cfg)
    cfg["batch_size"] = 32
    gwn_cfg = yaml.safe_load((ROOT / "configs/models/gwn.yaml").read_text())
    for mask_name, mask, op, frac, pert_seed in select_retrain_masks(masks):
        for seed in model_seeds:
            _, spec, loaders, device, prior = prepare(
                panel, cfg, glob, ORIGIN, seed, ("val", "test"))
            model = GraphWaveNetLite(
                n_features=len(FEATURES), hidden=int(gwn_cfg["hidden"]),
                n_layers=int(gwn_cfg["n_layers"]), horizons=spec.horizons,
                dropout=float(gwn_cfg["dropout"]), use_prior=bool(gwn_cfg["use_prior"]),
                n_nodes=panel.mask.shape[0],
                embedding_dim=int(gwn_cfg.get("embedding_dim", 10)),
            ).to(device)
            # Match run_graph_baseline.py: start the log-level head at the train
            # median, otherwise exp(0) produces pathological first-epoch errors.
            logs = []
            for batch in loaders["train"]:
                y = batch["y"]
                valid = batch["y_mask"].bool()
                if valid.any():
                    logs.append(y[valid].float().log())
            center = torch.cat(logs).median().to(device)
            with torch.no_grad():
                model.output_head[-1].bias.fill_(center)
            train_prior = torch.as_tensor(mask, dtype=torch.float32, device=device)
            stats = gwn_fit(model, loaders["train"], loaders["val"], device=device,
                            a_prior=train_prior, lr=float(gwn_cfg["lr"]), epochs=epochs,
                            patience=min(int(gwn_cfg.get("patience", 15)), epochs),
                            grad_clip=float(gwn_cfg["grad_clip"]),
                            amp=bool(gwn_cfg["amp"]))
            clean = torch.as_tensor(panel.mask > 0, dtype=torch.float32, device=device)
            run_rows = []
            for part in ("val", "test"):
                preds = _gwn_predict(model, loaders, device, clean, spec, part, panel)
                split = pd.read_parquet(SPLITS / f"{ORIGIN}_{part}.parquet")
                run_rows.extend(_metric_rows(
                    preds, split, model_seed=seed, mask_name=mask_name, op=op,
                    p=frac, pert_seed=pert_seed, mode="train", part=part,
                    train_prior=mask_name, test_prior="clean", model_name="gwn"))
            run_id = f"robustness_gwn_{mask_name}_s{seed}"
            _save_retrain_run(run_id, run_rows, model="gwn", mask_name=mask_name,
                              seed=seed, split_hash=panel.split_hash, stats=stats)
            rows.extend(run_rows)
            print(f"gwn retrain {mask_name} seed {seed}: done", flush=True)
    return pd.DataFrame(rows)


def _series(frame: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    test = frame[(frame["mode"] == "test") & (frame["part"] == "test")]
    train = frame[(frame["mode"] == "train") & (frame["part"] == "test")]
    series = []
    if not test.empty:
        series.append(("inference (clean ckpt)", test[test["model"] == "module1"]))
    for model, label in (("module1", "retrain Module 1"), ("gwn", "retrain GWN")):
        sub = train[train["model"] == model]
        if not sub.empty:
            series.append((label, sub))
    return [(label, sub) for label, sub in series if not sub.empty]


def plot_outputs(frame: pd.DataFrame, out: Path) -> None:
    series = _series(frame)
    if not series:
        return
    ops = ("drop", "add", "rewire")
    regimes = sorted(frame["regime"].unique())
    fig, axes = plt.subplots(len(series), len(regimes),
                             figsize=(4 * len(regimes), 2.9 * len(series)), squeeze=False)
    for i, (label, sub) in enumerate(series):
        curves = (sub[sub["op"].isin(ops)]
                  .groupby(["regime", "op", "p"], as_index=False)["mae"].mean())
        clean = sub[sub["op"] == "clean"].groupby("regime")["mae"].mean()
        for j, regime in enumerate(regimes):
            ax = axes[i, j]
            for op in ops:
                g = curves[(curves["regime"] == regime) & (curves["op"] == op)]
                if not g.empty:
                    ax.plot(g["p"] * 100, g["mae"], marker="o", label=op)
            base = clean.get(regime, np.nan)
            if np.isfinite(base):
                ax.axhline(base, color="black", linestyle="--", linewidth=1, label="clean")
            ax.set_xlabel("perturbation (%)")
            ax.grid(alpha=0.25)
            if j == 0:
                ax.set_ylabel(f"{label}\nMAE")
            if i == 0:
                ax.set_title(regime)
            if i == 0 and j == 0:
                ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_mae_vs_p.png", dpi=140)
    plt.close(fig)

    # Joint shift at p=50: delta MAE vs each series' clean baseline.
    frames = []
    for label, sub in series:
        clean = sub[sub["op"] == "clean"].groupby("regime")["mae"].mean()
        p50 = (sub[sub["op"].isin(ops) & (sub["p"].round(2) == 0.5)]
               .groupby(["regime", "op"])["mae"].mean().reset_index())
        if p50.empty or clean.empty:
            continue
        p50["delta"] = p50.apply(
            lambda r: r["mae"] - clean.get(r["regime"], np.nan), axis=1)
        p50["series"] = label
        frames.append(p50.dropna(subset=["delta"]))
    if not frames:
        return
    long = pd.concat(frames, ignore_index=True)
    piv = long.pivot_table(index=["regime", "op"], columns="series",
                           values="delta", aggfunc="mean")
    piv = piv.reindex(columns=[label for label, _ in series])
    fig, ax = plt.subplots(figsize=(max(9, 0.62 * len(piv)), 4.5))
    piv.plot(kind="bar", ax=ax, width=0.82)
    labels = [f"{regime}\n{op}" for regime, op in piv.index]
    ax.set_xticks(range(len(piv)), labels, rotation=45, ha="right", fontsize=7)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("MAE delta vs clean")
    ax.set_title("Joint climate-graph shift at p=50%")
    fig.tight_layout()
    fig.savefig(out / "fig_joint_shift.png", dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("test", "train", "both"), default="test")
    ap.add_argument("--epochs", type=int, default=2, help="retrain epochs")
    ap.add_argument("--model-seeds", default="0,1,2")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--baseline-gwn", action="store_true")
    ap.add_argument("--gwn-only", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    handoff = load_handoff()
    cfg = copy.deepcopy(yaml.safe_load((ROOT / "configs/models/module1.yaml").read_text()))
    cfg["global"] = yaml.safe_load((ROOT / "configs/global.yaml").read_text())
    panel = load_panel(ROOT / "data/processed/dataset_v1")
    manifest = save_masks(panel.mask)
    masks = list(perturbation_grid(panel.mask))
    if args.limit:
        masks = masks[:args.limit]
    frames = []
    if args.mode in ("train", "both") and (OUT / "robustness_val.csv").is_file():
        old = pd.read_csv(OUT / "robustness_val.csv")
        if "mode" in old:
            frames.append(old)
    if args.mode in ("test", "both"):
        frames.append(evaluate_test_mode(handoff, panel, cfg, cfg["global"], masks))
    if args.mode in ("train", "both"):
        seeds = tuple(int(x) for x in args.model_seeds.split(",") if x.strip())
        if not args.gwn_only:
            frames.append(retrain_mode(panel, cfg, cfg["global"], masks, seeds, args.epochs))
        if args.baseline_gwn or args.gwn_only:
            frames.append(gwn_retrain_mode(panel, cfg, cfg["global"], masks, seeds, args.epochs))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    keys = ["model", "train_prior", "test_prior", "op", "p", "pert_seed",
            "model_seed", "mode", "part", "horizon", "regime"]
    if not frame.empty:
        frame = frame.drop_duplicates(subset=keys, keep="last")
    frame.to_csv(OUT / "robustness_val.csv", index=False)
    plot_outputs(frame, OUT)
    test = frame[frame["mode"] == "test"]
    lines = ["# CGS-H5-01 robustness", "",
             f"Model: Module 1 O3 bps, {len(handoff['checkpoints'])} seeds; "
             f"{len(manifest)} masks including clean/no-prior.", "",
             "## Hasil inferensi", ""]
    if not test.empty:
        clean = test[(test["op"] == "clean") & (test["part"] == "test")]["mae"].mean()
        p50 = test[(test["op"].isin(("drop", "add", "rewire"))) &
                   (test["p"].round(2) == 0.5) & (test["part"] == "test")]["mae"].mean()
        lines.append(f"- MAE clean test: {clean:.2f}; MAE p=50 rata-rata: {p50:.2f} "
                     f"(delta {p50 - clean:+.2f}).")
        lines.append("- Kurva per regime: `fig_mae_vs_p.png`; joint shift: `fig_joint_shift.png`.")
    train = frame[frame["mode"] == "train"]
    lines.insert(4, f"Baris CSV: test-mode {len(test):,}; train-mode {len(train):,}.")
    lines.insert(5, "")
    if not train.empty:
        lines += ["", "## Retrain subset", "",
                  "Prior rusak p=10/50, op drop/add/rewire, perturbation seed 0, "
                  "model seed 0-2; dievaluasi pada graph clean.",
                  f"Model: {train['model'].value_counts().to_dict()}.", ""]
    lines += ["", "Catatan: `data/processed/perturbations/` dibuat dari `bps_mask.npy` "
              "karena paket perturbasi MDE belum tersedia; 45 mask = 3 op x 5 fraksi x "
              "3 perturbation seed. Clean/no-prior dan baseline GWN memakai subset prior "
              "yang sama."]
    (OUT / "robustness_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("DONE", len(frame), "rows", flush=True)


if __name__ == "__main__":
    main()
