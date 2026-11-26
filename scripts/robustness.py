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

from renaro.data.io import load_panel
from renaro.eval.metrics import mae, rmse, smape
from renaro.graph_perturb import perturbation_grid
from renaro.models.module1_training import fit, predict, prepare

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "experiments/handoff/module1_for_robustness.yaml"
SPLITS = ROOT / "data/processed/eval_splits"
OUT = ROOT / "reports/robustness"
PERT_DIR = ROOT / "data/processed/perturbations"
ORIGIN = "O3"
TRAIN_PRIOR = "bps"


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


def _metric_rows(preds: pd.DataFrame, split: pd.DataFrame, *, model_seed: int,
                 mask_name: str, op: str, p: float, pert_seed: int,
                 mode: str, part: str, train_prior: str, test_prior: str) -> list[dict]:
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
        rows.append({"model": "module1", "train_prior": train_prior,
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
    rows = []
    for mask_name, mask, op, frac, pert_seed in masks:
        if not (op in ("drop", "add", "rewire") and int(round(frac * 100)) in (10, 50)
                and pert_seed == 0):
            continue
        for seed in model_seeds:
            model, spec, loaders, device, prior = prepare(
                panel, cfg, glob, ORIGIN, seed, ("val", "test"))
            train_cand = torch.as_tensor(mask, dtype=torch.bool, device=device)
            stats = fit(model, loaders["train"], loaders["val"], device=device,
                        a_prior=(prior[0], train_cand), lr=float(cfg["lr"]), epochs=epochs,
                        patience=min(int(cfg.get("patience", 5)), epochs),
                        grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]))
            clean = torch.as_tensor(panel.mask > 0, dtype=torch.bool, device=device)
            for part in ("val", "test"):
                preds = _predict_frame(model, loaders, device, (prior[0], clean), spec, part, panel)
                split = pd.read_parquet(SPLITS / f"{ORIGIN}_{part}.parquet")
                rows.extend(_metric_rows(
                    preds, split, model_seed=seed, mask_name=mask_name, op=op,
                    p=frac, pert_seed=pert_seed, mode="train", part=part,
                    train_prior=mask_name, test_prior="clean"))
            print(f"retrain {mask_name} seed {seed}: done", flush=True)
    return pd.DataFrame(rows)


def plot_outputs(frame: pd.DataFrame, out: Path) -> None:
    test = frame[(frame["mode"] == "test") & (frame["part"] == "test")]
    if test.empty:
        return
    # MAE vs p, split by operation and regime.
    curves = (test[test["op"].isin(("drop", "add", "rewire"))]
              .groupby(["regime", "op", "p"], as_index=False)["mae"].mean())
    if curves.empty:
        return
    regimes = sorted(curves["regime"].unique())
    fig, axes = plt.subplots(1, len(regimes), figsize=(4 * len(regimes), 3), squeeze=False)
    for ax, regime in zip(axes[0], regimes):
        for op in ("drop", "add", "rewire"):
            g = curves[(curves["regime"] == regime) & (curves["op"] == op)]
            ax.plot(g["p"] * 100, g["mae"], marker="o", label=op)
        ax.set_title(regime)
        ax.set_xlabel("perturbation (%)")
        ax.set_ylabel("MAE")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_mae_vs_p.png", dpi=140)
    plt.close(fig)

    # Joint shift at p=50: mean MAE relative to clean.
    clean = (test[test["op"] == "clean"].groupby("regime")["mae"].mean())
    p50 = (test[(test["op"].isin(("drop", "add", "rewire"))) & (test["p"].round(2) == 0.5)]
           .groupby(["regime", "op"])["mae"].mean().reset_index())
    p50["delta"] = p50.apply(lambda r: r["mae"] - clean.get(r["regime"], np.nan), axis=1)
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [f"{r.regime}\n{r.op}" for r in p50.itertuples(index=False)]
    ax.bar(range(len(p50)), p50["delta"])
    ax.set_xticks(range(len(p50)), labels, rotation=45, ha="right", fontsize=7)
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
    if args.mode == "train" and (OUT / "robustness_val.csv").is_file():
        old = pd.read_csv(OUT / "robustness_val.csv")
        if "mode" in old:
            frames.append(old[old["mode"] == "test"])
    if args.mode in ("test", "both"):
        frames.append(evaluate_test_mode(handoff, panel, cfg, cfg["global"], masks))
    if args.mode in ("train", "both"):
        seeds = tuple(int(x) for x in args.model_seeds.split(",") if x.strip())
        frames.append(retrain_mode(panel, cfg, cfg["global"], masks, seeds, args.epochs))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
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
    if not train.empty:
        lines += ["", "## Retrain subset", "",
                  "Prior rusak p=10/50, op drop/add/rewire, perturbation seed 0.", ""]
    lines += ["", "Catatan: `data/processed/perturbations/` dibuat dari `bps_mask.npy` "
              "karena paket perturbasi MDE belum tersedia; 45 mask = 3 op x 5 fraksi x "
              "3 perturbation seed. Baseline GWN belum dijalankan pada subset ini."]
    (OUT / "robustness_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("DONE", len(frame), "rows", flush=True)


if __name__ == "__main__":
    main()
