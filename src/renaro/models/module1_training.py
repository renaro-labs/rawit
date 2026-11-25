"""Training/evaluation plumbing for MLE-H2-02 Module 1.

This module is the missing runner imported by `run_module1.py` and by
`scripts/train.py` (through `renaro.models.module1:run`). It deliberately keeps
the synthetic prototype separate from the production dataset loader.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, Subset

from renaro.baselines.naive import asof_prices
from renaro.contract import N_LAG_BINS, PROV_CODES
from renaro.data.datasets import CLIMATE_FEATURES, FEATURES, WindowDataset, WindowSpec
from renaro.data.io import Panel
from renaro.eval.splits import rolling_origin, split_indices
from renaro.models.module1 import ClimateConditionedLagGraph
from renaro.train_loop import masked_log_mae, seed_everything


@dataclass
class Prepared:
    model: ClimateConditionedLagGraph
    spec: WindowSpec
    loaders: dict[str, DataLoader]
    device: torch.device
    prior: tuple[torch.Tensor, torch.Tensor]


def _edge_tensors(panel: Panel, prior_mode: str) -> tuple[torch.Tensor, torch.Tensor]:
    mask = np.asarray(panel.mask, dtype=np.float32)
    n = mask.shape[0]
    if mask.shape != (n, n):
        raise ValueError("mask harus N x N")
    if prior_mode not in ("bps", "none"):
        raise ValueError("prior harus 'bps' atau 'none'")
    cand = mask.astype(bool) if prior_mode == "bps" else ~np.eye(n, dtype=bool)
    np.fill_diagonal(cand, False)
    row = mask.sum(axis=1, keepdims=True)
    share = np.divide(mask, np.maximum(row, 1.0))
    # 4 static channels: reserved distance channel (0 for synthetic), BPS flag,
    # BPS share, and an inverse-distance placeholder (0).
    edge = np.zeros((n, n, 4), dtype=np.float32)
    edge[:, :, 1] = (mask > 0).astype(np.float32)
    edge[:, :, 2] = share.astype(np.float32)
    return torch.from_numpy(edge), torch.from_numpy(cand)


class Module1Dataset(Dataset):
    """WindowDataset + target-date calendar features."""

    def __init__(self, base: WindowDataset, panel: Panel):
        self.base = base
        self.panel = panel
        cal = panel.panel[["date", "is_ramadan", "days_to_lebaran", "dow", "month"]].copy()
        cal["date"] = pd.to_datetime(cal["date"]).astype("datetime64[ns]")
        cal = cal.drop_duplicates("date").set_index("date")
        self.cal = cal
        source = base if hasattr(base, "spec") else base.dataset
        self.horizons = tuple(source.spec.horizons)

    def __len__(self) -> int:
        return len(self.base)

    def __getitem__(self, i: int) -> dict[str, Any]:
        item = self.base[i]
        k = int(item["t_index"])
        target_idx = k + np.asarray(self.horizons, dtype=int) - 1
        target_dates = pd.DatetimeIndex(self.panel.dates[target_idx])
        rows = self.cal.reindex(target_dates)
        if rows[["dow", "month"]].isna().any().any():
            raise ValueError("kalender target tidak lengkap")
        cal = np.column_stack([
            rows["is_ramadan"].fillna(False).astype(float).to_numpy(),
            rows["days_to_lebaran"].fillna(0).astype(float).to_numpy() / 366.0,
            rows["dow"].astype(float).to_numpy() / 6.0,
            (rows["month"].astype(float).to_numpy() - 1.0) / 11.0,
        ]).astype(np.float32)
        item["cal"] = torch.from_numpy(cal)
        item["target_date"] = [str(d.date()) for d in target_dates]
        return item


def prepare(panel: Panel, cfg: dict, glob: dict, origin: str, seed: int,
            eval_parts: tuple[str, ...] = ("val", "test"), *, smoke: bool = False) -> Prepared:
    seed_everything(seed)
    spec = WindowSpec(window=int(glob["window"]), horizons=tuple(glob["horizons"]))
    split = rolling_origin(origin, panel.dates)
    prior_mode = str(cfg.get("prior", "bps"))
    edge, cand = _edge_tensors(panel, prior_mode)
    loaders: dict[str, DataLoader] = {}
    for part in ("train", "val", "test"):
        if part in ("val", "test") and part not in eval_parts:
            continue
        base = WindowDataset(panel, origin, part, spec)
        official = set(split_indices(split, panel.dates, part, horizon=max(spec.horizons)))
        keep = [i for i, k in enumerate(base.decision_indices) if k in official]
        if not keep:
            raise ValueError(f"{origin}/{part}: tidak ada window resmi")
        if smoke:
            keep = keep[:16]
        ds = Module1Dataset(Subset(base, keep), panel)
        loaders[part] = DataLoader(ds, batch_size=int(cfg.get("batch_size", 32)),
                                   shuffle=part == "train", num_workers=0)
        print(f"{part}: {len(keep)} windows")
    model = ClimateConditionedLagGraph(
        n_features=len(FEATURES), n_climate=len(CLIMATE_FEATURES),
        n_edge_features=4, n_calendar_future=4,
        hidden=int(cfg.get("hidden", 64)), n_lags=int(cfg.get("n_lags", N_LAG_BINS)),
        horizons=spec.horizons, null_option=True,
        forecast_aligned=bool(cfg.get("forecast_aligned", False)),
        n_nodes=panel.mask.shape[0] if cfg.get("edge_lag_bias", True) else None,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return model, spec, loaders, device, (edge.to(device), cand.to(device))


def _batch_parts(batch: dict[str, Any], device: torch.device):
    return (batch["X"].to(device), batch["C"].to(device), batch["y"].to(device),
            batch["y_mask"].to(device).bool(), batch["cal"].to(device))


def evaluate(model: ClimateConditionedLagGraph, loader: DataLoader, device: torch.device,
             prior: tuple[torch.Tensor, torch.Tensor]) -> float:
    model.eval()
    edge, cand = prior
    edge = edge.to(device)
    cand = cand.to(device)
    total, count = 0.0, 0
    with torch.no_grad():
        for batch in loader:
            x, c, y, mask, cal = _batch_parts(batch, device)
            pred, _ = model(x, c, edge, cand, cal)
            if not mask.any():
                continue
            errors = (pred.float().exp()[mask] - y[mask]).abs()
            total += errors.double().sum().item()
            count += int(mask.sum().item())
    if not count:
        raise ValueError("Tidak ada target validasi")
    return total / count


def fit(model: ClimateConditionedLagGraph, train_loader: DataLoader, val_loader: DataLoader,
        *, device: torch.device, a_prior: tuple[torch.Tensor, torch.Tensor],
        lr: float = 1e-3, epochs: int = 200, patience: int = 15,
        grad_clip: float = 5.0, amp: bool = True, checkpoint: Path | None = None,
        entropy_lambda: float = 0.0) -> dict:
    device = torch.device(device)
    edge, cand = a_prior
    edge = edge.to(device)
    cand = cand.to(device)
    model = model.to(device)
    # Match the graph baseline: start the log-level head at the train median,
    # never at a random level. This keeps the synthetic MAE comparable.
    logs = []
    for batch in train_loader:
        y = batch["y"]
        mask = batch["y_mask"].bool()
        if mask.any():
            logs.append(y[mask].float().log())
    if not logs:
        raise ValueError("Tidak ada target training")
    center = torch.cat(logs).median().to(device)
    with torch.no_grad():
        model.head[-1].bias.fill_(center)
    use_amp = bool(amp) and device.type == "cuda"
    if device.type == "cuda":
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(lr))
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    best, best_state, best_epoch, stale = float("inf"), None, 0, 0
    history = []
    for epoch in range(1, int(epochs) + 1):
        model.train()
        total, count = 0.0, 0
        for batch in train_loader:
            x, c, y, mask, cal = _batch_parts(batch, device)
            if not mask.any():
                continue
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                pred, a = model(x, c, edge, cand, cal)
                loss = masked_log_mae(pred, y, mask)
                if entropy_lambda:
                    loss = loss + float(entropy_lambda) * model.entropy_regularizer(a)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite training loss")
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(grad_clip))
            scaler.step(opt)
            scaler.update()
            total += float(loss.item()) * int(mask.sum().item())
            count += int(mask.sum().item())
        if not count:
            raise ValueError("Tidak ada target training")
        val = evaluate(model, val_loader, device, a_prior)
        history.append({"epoch": epoch, "train_log_mae": total / count, "val_mae_rp": val})
        print(f"Epoch {epoch:03d} | log MAE={total / count:.6f} | val MAE={val:.2f}")
        if val < best:
            best, best_epoch, stale = val, epoch, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= int(patience):
                break
    model.load_state_dict(best_state)
    model.eval()
    if checkpoint is not None:
        path = Path(checkpoint)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model_state_dict": best_state, "best_epoch": best_epoch,
                    "val_mae_rp": best}, path)
    allocated = reserved = None
    if device.type == "cuda":
        torch.cuda.synchronize(device)
        allocated = torch.cuda.max_memory_allocated(device) / 1e9
        reserved = torch.cuda.max_memory_reserved(device) / 1e9
    return {"best_epoch": best_epoch, "best_val_mae_rp": best, "history": history,
            "peak_allocated_gb": allocated, "peak_reserved_gb": reserved,
            "epochs_run": len(history)}


@torch.no_grad()
def predict(model: ClimateConditionedLagGraph, batch: dict[str, Any], device: torch.device,
            prior: tuple[torch.Tensor, torch.Tensor]):
    model.eval()
    edge, cand = prior
    x, c, y, mask, cal = _batch_parts(batch, device)
    pred, a = model(x, c, edge.to(device), cand.to(device), cal)
    return pred, a


def run_registered(panel: Panel, cfg: dict, origin: str, seed: int) -> pd.DataFrame:
    glob = cfg["global"]
    model, spec, loaders, device, prior = prepare(panel, cfg, glob, origin, seed, ("val", "test"))
    stats = fit(model, loaders["train"], loaders["val"], device=device, a_prior=prior,
                lr=float(cfg.get("lr", 1e-3)), epochs=int(cfg.get("epochs", 200)),
                patience=int(cfg.get("patience", 15)), grad_clip=float(cfg.get("grad_clip", 5.0)),
                amp=bool(cfg.get("amp", True)), entropy_lambda=float(cfg.get("entropy_lambda", 0.0)))
    prices = asof_prices(panel)
    frames = []
    for part in ("val", "test"):
        for batch in loaders[part]:
            log_pred, _ = predict(model, batch, device, prior)
            pred = log_pred.float().exp().cpu().numpy()
            for i, k in enumerate(batch["t_index"].tolist()):
                for j, h in enumerate(spec.horizons):
                    frames.append(pd.DataFrame({
                        "model": cfg.get("model", "module1"), "fold": origin,
                        "seed": seed, "part": part, "date": panel.dates[k],
                        "target_date": panel.dates[k + h - 1],
                        "prov_code": list(panel.node_codes), "h": h,
                        "y_true": batch["y"][i, j].numpy(),
                        "y_mask": batch["y_mask"][i, j].numpy(),
                        "y_pred": pred[i, j],
                        "naive_pred": prices.iloc[k].to_numpy(),
                    }))
    out = pd.concat(frames, ignore_index=True)
    out.loc[~out["y_mask"].astype(bool), "y_true"] = np.nan
    out.attrs["training"] = stats
    return out
