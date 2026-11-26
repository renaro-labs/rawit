#!/usr/bin/env python3
"""Rebuild CGS-H5-01 artifacts from test rows and per-run retrain evidence."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/robustness"
RUNS = ROOT / "experiments/runs"
REGISTRY = ROOT / "experiments/registry.csv"
OPS = ("drop", "add", "rewire")
KEYS = ["model", "train_prior", "test_prior", "op", "p", "pert_seed",
        "model_seed", "mode", "part", "horizon", "regime"]


def _weighted(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    records = []
    for key, g in df.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        weight = g["n"].to_numpy(dtype=float)
        records.append({
            **dict(zip(keys, key)),
            "mae": float(np.average(g["mae"], weights=weight)),
            "rmse": float(np.average(g["rmse"], weights=weight)),
            "smape": float(np.average(g["smape"], weights=weight)),
            "n": int(g["n"].sum()),
        })
    return pd.DataFrame(records)


def _load() -> pd.DataFrame:
    final_path = OUT / "robustness_val.csv"
    current = pd.read_csv(final_path)
    test = current[current["mode"] == "test"].copy()
    if test.empty:
        raise SystemExit("no test-mode rows to preserve")
    train_frames = []
    for pattern in ("robustness_module1_*_s*", "robustness_gwn_*_s*"):
        for run in sorted(RUNS.glob(pattern)):
            path = run / "metrics.csv"
            if path.is_file():
                train_frames.append(pd.read_csv(path))
    train = pd.concat(
        [current[current["mode"] == "train"], *train_frames], ignore_index=True)
    frame = pd.concat([test, train], ignore_index=True)
    frame = frame.drop_duplicates(subset=KEYS, keep="last")
    return frame


def main() -> None:
    frame = _load()
    if frame.isna().any().any():
        raise SystemExit("unexpected nulls in robustness_val.csv")
    expected = {"mae", "rmse", "smape", "n", "horizon", "regime", "part"}
    missing = expected - set(frame.columns)
    if missing:
        raise SystemExit(f"missing columns: {sorted(missing)}")
    frame.to_csv(OUT / "robustness_val.csv", index=False)

    sys.path.insert(0, str(ROOT / "scripts"))
    from robustness import plot_outputs

    plot_outputs(frame, OUT)

    test_all = frame[frame["mode"] == "test"]
    train_all = frame[frame["mode"] == "train"]
    test = test_all[test_all["part"] == "test"]
    train = train_all[train_all["part"] == "test"]
    h10 = 10

    # Inference baseline (5 checkpoints, no retraining).
    inf = test[(test["model"] == "module1") & (test["horizon"] == h10)]
    inf_clean = inf[inf["op"] == "clean"]
    inf_p50 = inf[inf["op"].isin(OPS) & (inf["p"].round(2) == 0.5)]
    inf_clean_per_seed = _weighted(inf_clean, ["model_seed"])["mae"]
    inf_p50_per_seed = _weighted(inf_p50, ["model_seed"])["mae"]
    inf_clean_mean = float(inf_clean_per_seed.mean())
    inf_p50_mean = float(inf_p50_per_seed.mean())

    # Retrain table at h10 on the clean evaluation graph.
    retrain_rows = []
    for model in ("module1", "gwn"):
        sub = train[(train["model"] == model) & (train["horizon"] == h10)]
        if sub.empty:
            continue
        per_seed = _weighted(sub, ["op", "p", "model_seed"])
        clean = per_seed[per_seed["op"] == "clean"]["mae"]
        base = float(clean.mean()) if len(clean) else float("nan")
        base_std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
        retrain_rows.append({"model": model, "op": "clean", "p": 0.0,
                             "mean_mae": base, "std_mae": base_std,
                             "delta_vs_clean": 0.0, "n_seed": int(len(clean)),
                             "n_node_days": int(per_seed[per_seed["op"] == "clean"]["n"].sum())})
        for (op, p), g in per_seed[per_seed["op"].isin(OPS)].groupby(["op", "p"]):
            retrain_rows.append({
                "model": model, "op": op, "p": float(p),
                "mean_mae": float(g["mae"].mean()),
                "std_mae": float(g["mae"].std(ddof=1)) if len(g) > 1 else 0.0,
                "delta_vs_clean": float(g["mae"].mean()) - base,
                "n_seed": int(len(g)), "n_node_days": int(g["n"].sum()),
            })
    retrain = pd.DataFrame(retrain_rows)
    if not retrain.empty:
        clean_map = retrain[retrain["op"] == "clean"].set_index("model")["mean_mae"]
        retrain["delta_pct_vs_clean"] = retrain.apply(
            lambda r: 100.0 * r["delta_vs_clean"] / clean_map.get(r["model"], np.nan), axis=1)
        retrain.to_csv(OUT / "robustness_retrain_h10.csv", index=False)

    # Joint shift per climate regime for the retrained models.
    regime_rows = []
    for model in ("module1", "gwn"):
        sub = train[(train["model"] == model) & (train["horizon"] == h10)]
        if sub.empty:
            continue
        per_seed = _weighted(sub, ["regime", "op", "p", "model_seed"])
        clean = (per_seed[per_seed["op"] == "clean"]
                 .groupby("regime")["mae"].mean())
        for (regime, op, p), g in per_seed[per_seed["op"].isin(OPS)].groupby(
                ["regime", "op", "p"]):
            base = clean.get(regime, np.nan)
            regime_rows.append({
                "model": model, "regime": regime, "op": op, "p": float(p),
                "mean_mae": float(g["mae"].mean()),
                "std_mae": float(g["mae"].std(ddof=1)) if len(g) > 1 else 0.0,
                "delta_vs_clean": float(g["mae"].mean()) - base,
                "n_seed": int(len(g)),
            })
    by_regime = pd.DataFrame(regime_rows)
    if not by_regime.empty:
        by_regime["delta_pct_vs_clean"] = 100.0 * by_regime["delta_vs_clean"] / (
            by_regime["mean_mae"] - by_regime["delta_vs_clean"])
        by_regime.to_csv(OUT / "robustness_retrain_by_regime.csv", index=False)

    counts = frame.groupby(["mode", "model", "part"]).size().reset_index(name="rows")
    reg = pd.read_csv(REGISTRY, dtype=str) if REGISTRY.exists() else pd.DataFrame()
    robust_reg = reg[reg["run_id"].str.startswith("robustness_", na=False)] if len(reg) else reg
    masks = pd.read_csv(ROOT / "data/processed/perturbations/manifest.csv")
    handoff = yaml.safe_load(
        (ROOT / "experiments/handoff/module1_for_robustness.yaml").read_text())

    lines = ["# CGS-H5-01 robustness", "",
             "Graph-prior misspecification dan joint climate-graph shift, "
             "Module 1 O3/BPS dan baseline GWN.", "",
             f"Split hash: `{handoff['split_hash']}`. "
             "Semua evaluasi memakai part `val`/`test` resmi; holdout tidak disentuh.", "",
             "## Cakupan data", "",
             f"- Total CSV: {len(frame):,} baris; test-mode {len(test_all):,}, "
             f"train-mode {len(train_all):,}.",
             f"- Mask: {len(masks)} = 45 perturbasi (3 op x 5 fraksi x 3 perturbation seed) "
             "+ clean + no-prior.",
             f"- Test-mode: {len(test_all):,} baris ({len(test):,} per part) = 47 mask x "
             "5 checkpoint seed x 3 horizon x 4 regime x 2 part.",
             f"- Langkah 2 / train-mode: {len(train_all):,} baris ({len(train):,} per part) "
             "= subset p={10,50} x {drop,add,rewire} x perturbation seed 0 x model seed "
             "0-2, ditambah baseline clean, untuk Module 1 dan GWN.",
             f"- Registry evidence: {len(robust_reg)} entri `robustness_*` (75 run ablation "
             "terpisah di `reports/ablation/`).", "",
             "| mode | model | part | rows |", "|---|---|---|---:|"]
    for r in counts.itertuples(index=False):
        lines.append(f"| {r.mode} | {r.model} | {r.part} | {r.rows} |")

    lines += ["", "## Hasil inferensi (5 checkpoint, tanpa retrain)", "",
              f"- MAE clean test h10: {inf_clean_mean:.2f} "
              f"(± {inf_clean_per_seed.std(ddof=1):.2f} antar seed).",
              f"- MAE p=50 test h10: {inf_p50_mean:.2f} "
              f"(Δ {inf_p50_mean - inf_clean_mean:+.2f} vs clean).",
              "- Kurva penuh per regime: `fig_mae_vs_p.png`; joint shift p=50: "
              "`fig_joint_shift.png`."]

    if not retrain.empty:
        lines += ["", "## Hasil retrain (h10, evaluasi graph clean)", "",
                  "Δ dihitung terhadap baseline retrain clean model yang sama. "
                  "Mean ± std antar 3 model seed.", "",
                  "| model | op | p | MAE ± std | Δ vs clean | Δ % |",
                  "|---|---|---:|---:|---:|---:|"]
        for r in retrain.itertuples(index=False):
            p_label = "-" if r.op == "clean" else f"{r.p:.2f}"
            lines.append(f"| {r.model} | {r.op} | {p_label} | "
                         f"{r.mean_mae:.2f} ± {r.std_mae:.2f} | "
                         f"{r.delta_vs_clean:+.2f} | {r.delta_pct_vs_clean:+.2f}% |")
        lines += ["", "Tabel mesin: `reports/robustness/robustness_retrain_h10.csv`."]

    if not by_regime.empty:
        p50 = by_regime[by_regime["p"].round(2) == 0.5]
        lines += ["", "## Joint shift per regime (h10, p=50, graph clean)", "",
                  "Δ MAE relatif terhadap baseline clean model yang sama pada regime tersebut.", "",
                  "| model | regime | op | MAE ± std | Δ vs clean | Δ % |",
                  "|---|---|---|---:|---:|---:|"]
        for r in p50.sort_values(["model", "regime", "op"]).itertuples(index=False):
            lines.append(f"| {r.model} | {r.regime} | {r.op} | "
                         f"{r.mean_mae:.2f} ± {r.std_mae:.2f} | "
                         f"{r.delta_vs_clean:+.2f} | {r.delta_pct_vs_clean:+.2f}% |")
        lines += ["", "Tabel lengkap p=10/50: "
                  "`reports/robustness/robustness_retrain_by_regime.csv`."]

    lines += ["", "## Limitasi", "",
              "- 45 mask dibuat lokal dari `bps_mask.npy` karena paket perturbasi "
              "MDE-H4-02 belum tersedia; ini tetap dicatat sebagai limitasi sumber mask.",
              "- DoD mengizinkan subset minimal p={10,50} bila waktu kurang; p=30 tidak "
              "dijalankan dan dicatat sebagai batas waktu.",
              "- Retrain memakai anggaran tetap 2 epoch dan batch 32 (Module 1) / "
              "arsitektur `configs/models/gwn.yaml` dengan 2 epoch (GWN) agar 42 run "
              "selesai pada GPU 4 GB. Angka ini bukan hasil tuning jangka panjang.",
              "- Test-mode memakai checkpoint H4 Module 1 seed 0-4; train-mode memakai "
              "seed 0-2 sesuai batas minimum audit.", "",
              "## Bukti run", "",
              "- `experiments/runs/robustness_module1_<prior>_s<seed>/metrics.csv` dan `run.json`.",
              "- `experiments/runs/robustness_gwn_<prior>_s<seed>/metrics.csv` dan `run.json`.",
              "- `experiments/registry.csv` dengan `run_id` berprefix `robustness_`."]
    (OUT / "robustness_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(counts.to_string(index=False))
    print("rows", len(frame), "| test", len(test), "| train", len(train))
    if not retrain.empty:
        print(retrain.to_string(index=False))


if __name__ == "__main__":
    main()
