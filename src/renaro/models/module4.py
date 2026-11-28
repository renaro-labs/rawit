"""MLE-H5-04: Module 4 — perturbation-robust and cross-regime training objective.

Extends Module 2-3 (``Module23``) with three stretch-goal regularizers that use
strictly information available at forecast origin ``t`` (NEVER ``regime_labels.csv``
and NEVER future targets):

1. Graph perturbation sensitivity penalty:
       L_perturb = || f(X, A) - f(X, A_tilde) ||
   where A_tilde is produced from a random per-batch perturbation of
   ``candidate_mask`` (mixed edge dropout + perturbed BPS support).

2. Cross-regime risk (V-REx variance across causal climate groups):
       L_vrex = Var_g( R_g )
   where groups ``g`` are formed exclusively from quantile bins of origin-
   aggregated climate features available at time <= t (default: ``rain_30d_anom``).

3. Soft prior regularization:
       L_prior = lambda_prior * || A * (1 - M_bps) ||_1
   normalized per (batch, destination node), paired with a soft off-diagonal
   candidate mask so non-BPS edges remain learnable while softly anchored to M_bps.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Subset

from renaro.baselines.naive import asof_prices
from renaro.data.datasets import CLIMATE_FEATURES, FEATURES, WindowDataset, WindowSpec
from renaro.data.io import Panel
from renaro.eval.splits import rolling_origin, split_indices
from renaro.graph_perturb import add_edges, drop_edges, rewire_edges
from renaro.models.module1_training import Module1Dataset, _batch_parts, evaluate, predict
from renaro.models.module23 import Module23
from renaro.train_loop import masked_log_mae, seed_everything


def _row_normalized_prior(bps_mask: np.ndarray) -> torch.Tensor:
    m = (np.asarray(bps_mask) > 0).astype(np.float32)
    np.fill_diagonal(m, 0.0)
    row_sum = m.sum(axis=1, keepdims=True)
    # Fallback to self-node climate when a province has zero BPS origins.
    no_origin = (row_sum.squeeze(-1) <= 0)
    if no_origin.any():
        m = m.copy()
        for i in np.flatnonzero(no_origin):
            m[i, i] = 1.0
        row_sum = m.sum(axis=1, keepdims=True)
    return torch.from_numpy(m / np.maximum(row_sum, 1e-6))


def module4_edge_tensors(panel: Panel, prior_mode: str) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return (edge_features [N,N,4], candidate_mask [N,N], bps_binary [N,N]).

    For ``prior_mode == 'soft_bps'`` (default for Module 4), ``candidate_mask``
    allows all off-diagonal pairs so non-BPS edges can be explored while being
    penalized by ``soft_prior_l1_loss`` against ``bps_binary``.
    """
    mask = np.asarray(panel.mask, dtype=np.float32)
    n = mask.shape[0]
    if mask.shape != (n, n):
        raise ValueError("mask harus N x N")
    if prior_mode not in ("soft_bps", "bps", "none"):
        raise ValueError("prior harus 'soft_bps', 'bps', atau 'none'")
    bps_bin = (mask > 0).astype(np.float32)
    np.fill_diagonal(bps_bin, 0.0)
    cand = bps_bin.astype(bool) if prior_mode == "bps" else ~np.eye(n, dtype=bool)
    np.fill_diagonal(cand, False)
    row = mask.sum(axis=1, keepdims=True)
    share = np.divide(mask, np.maximum(row, 1.0))
    edge = np.zeros((n, n, 4), dtype=np.float32)
    edge[:, :, 1] = bps_bin
    edge[:, :, 2] = share.astype(np.float32)
    return torch.from_numpy(edge), torch.from_numpy(cand), torch.from_numpy(bps_bin)


def perturb_candidate_mask(
    candidate_mask: torch.Tensor,
    bps_mask: torch.Tensor,
    *,
    p_min: float = 0.10,
    p_max: float = 0.50,
    mode: str = "mixed",
    rng: np.random.Generator | None = None,
) -> torch.Tensor:
    """Create a random per-batch perturbed candidate mask A_tilde (diagonal=False)."""
    if not (0.0 <= p_min <= p_max <= 0.95):
        raise ValueError(f"Invalid perturbation fraction range: [{p_min}, {p_max}]")
    rng = rng if rng is not None else np.random.default_rng()
    device = candidate_mask.device
    cand_np = candidate_mask.detach().cpu().numpy().astype(np.uint8)
    bps_np = (bps_mask.detach().cpu().numpy() > 0).astype(np.uint8)
    n = cand_np.shape[0]
    np.fill_diagonal(cand_np, 0)
    np.fill_diagonal(bps_np, 0)

    frac = float(rng.uniform(p_min, p_max))
    seed = int(rng.integers(0, 2**31 - 1))
    density = float(cand_np.sum()) / max(n * (n - 1), 1)

    if mode == "drop_only" or (mode == "mixed" and density > 0.85 and rng.random() < 0.5):
        out = drop_edges(cand_np, frac, seed=seed)
    elif mode == "mixed" and density > 0.85:
        # Perturb BPS support with drop/add/rewire so the model also sees
        # sparse/corrupted prior masks directly during training.
        op = str(rng.choice(("drop", "add", "rewire")))
        fn = {"drop": drop_edges, "add": add_edges, "rewire": rewire_edges}[op]
        out = fn(bps_np, frac, seed=seed)
    else:
        op = str(rng.choice(("drop", "add", "rewire")))
        fn = {"drop": drop_edges, "add": add_edges, "rewire": rewire_edges}[op]
        out = fn(cand_np, frac, seed=seed)

    np.fill_diagonal(out, 0)
    return torch.as_tensor(out > 0, dtype=torch.bool, device=device)


def perturbation_sensitivity_loss(
    pred_clean: torch.Tensor,
    pred_perturbed: torch.Tensor,
    mask: torch.Tensor,
    *,
    norm: str = "l1",
) -> torch.Tensor:
    """Masked ||f(X, A) - f(X, A_tilde)|| on log-level predictions."""
    if pred_clean.shape != pred_perturbed.shape or mask.shape != pred_clean.shape:
        raise ValueError("Shape mismatch in perturbation_sensitivity_loss")
    mask = mask.bool()
    if not mask.any():
        return pred_clean.new_zeros(())
    diff = pred_clean[mask].float() - pred_perturbed[mask].float()
    if norm == "l1":
        return diff.abs().mean()
    if norm == "l2":
        return torch.sqrt((diff * diff).mean() + 1e-12)
    raise ValueError(f"norm harus 'l1' atau 'l2', dapat {norm!r}")


def causal_origin_climate_groups(
    c: torch.Tensor,
    origin_weights: torch.Tensor,
    *,
    feature_idx: int = 1,
    n_groups: int = 3,
    lookback: int = 5,
) -> torch.Tensor:
    """Assign each (batch, node) to quantile groups using strictly as-of climate <= t.

    Parameters
    ----------
    c : Tensor [B, T, N, F_clim]
        As-of standardized climate tensor from ``WindowDataset`` (available <= t).
    origin_weights : Tensor [N, N]
        Row-normalized BPS origin weights (self-node fallback if row has no BPS edges).
    feature_idx : int
        Index in ``CLIMATE_FEATURES`` (default 1 = ``rain_30d_anom``).
    n_groups : int
        Number of quantile groups (default 3: dry / normal / wet origin rainfall).
    lookback : int
        Number of most recent timesteps <= t to average (default 5 = 1 pentad).

    Returns
    -------
    Tensor [B, N] of int64 group IDs in ``[0, n_groups - 1]``.
    """
    if n_groups < 2:
        raise ValueError("n_groups harus >= 2")
    steps = max(1, min(int(lookback), c.shape[1]))
    with torch.amp.autocast(device_type=c.device.type, enabled=False):
        c_recent = c[:, -steps:, :, feature_idx].float().mean(dim=1)  # [B, N]
        w = origin_weights.to(device=c.device, dtype=torch.float32)
        origin_signal = torch.einsum("ij,bj->bi", w, c_recent).float().contiguous()  # [B, N]
        flat = origin_signal.reshape(-1)
        q_levels = torch.linspace(
            0.0, 1.0, steps=n_groups + 1, device=c.device, dtype=torch.float32
        )[1:-1]
        edges = torch.quantile(flat, q_levels).contiguous()
        groups = torch.bucketize(origin_signal, edges)
    return groups.clamp(0, n_groups - 1)


def cross_regime_risk_loss(
    pred: torch.Tensor,
    y: torch.Tensor,
    mask: torch.Tensor,
    group_ids: torch.Tensor,
    *,
    n_groups: int = 3,
) -> tuple[torch.Tensor, int]:
    """Variance of masked log-MAE across causal climate groups (V-REx penalty).

    Parameters
    ----------
    pred, y, mask : Tensor [B, H, N]
    group_ids : Tensor [B, N]
        Group assignments derived solely from features available at time <= t.
    """
    if pred.shape != y.shape or mask.shape != y.shape:
        raise ValueError("Shape pred, y, mask harus sama")
    b, h, n = pred.shape
    if group_ids.shape != (b, n):
        raise ValueError(f"group_ids harus [B, N], dapat {tuple(group_ids.shape)}")
    mask_b = mask.bool()
    if not mask_b.any():
        return pred.new_zeros(()), 0

    g_exp = group_ids[:, None, :].expand(b, h, n)
    # Safe log only on valid positive targets; invalid entries are masked out.
    safe_y = torch.where(mask_b, y.float().clamp_min(1e-12), torch.ones_like(y, dtype=torch.float32))
    abs_err = (pred.float() - safe_y.log()).abs()

    risks = []
    for g in range(int(n_groups)):
        gm = mask_b & (g_exp == g)
        if gm.any():
            risks.append(abs_err[gm].mean())
    if len(risks) < 2:
        return pred.new_zeros(()), len(risks)
    stacked = torch.stack(risks)
    return stacked.var(unbiased=False), len(risks)


def soft_prior_l1_loss(
    a: torch.Tensor,
    bps_mask: torch.Tensor,
    a_static: torch.Tensor | None = None,
    *,
    static_weight: float = 0.25,
) -> torch.Tensor:
    """Normalized soft prior penalty: ||A * (1 - M_bps)||_1 per (batch, node)."""
    n = bps_mask.shape[0]
    off_bps = (1.0 - (bps_mask.to(device=a.device, dtype=torch.float32) > 0).float())
    off_bps = off_bps * (~torch.eye(n, dtype=torch.bool, device=a.device)).float()
    adapt_l1 = (a.float().abs() * off_bps[None, :, :, None]).sum(dim=(-1, -2)).mean()
    if a_static is not None and float(static_weight) > 0.0:
        static_l1 = (a_static.float().abs() * off_bps).sum(dim=-1).mean()
        return adapt_l1 + float(static_weight) * static_l1
    return adapt_l1


class Module4(Module23):
    """Module 1-3 backbone with factorized encode/decode for perturbation consistency."""

    def __init__(
        self,
        n_features: int,
        n_climate: int,
        *,
        hidden: int = 64,
        n_lags: int = 6,
        horizons=(5, 10, 20),
        n_nodes: int = 34,
        static_prior: torch.Tensor | None = None,
        no_gate: bool = False,
        no_climate_gate: bool = False,
        no_calendar: bool = False,
        no_climate: bool = False,
    ):
        super().__init__(
            n_features=n_features,
            n_climate=n_climate,
            hidden=hidden,
            n_lags=n_lags,
            horizons=horizons,
            n_nodes=n_nodes,
            static_prior=static_prior,
            no_gate=no_gate,
            no_climate_gate=no_climate_gate,
            no_calendar=no_calendar,
            no_climate=no_climate,
        )
        raw_bps = torch.eye(n_nodes) if static_prior is None else (static_prior.float() > 0).float()
        raw_bps = raw_bps.clone()
        raw_bps.fill_diagonal_(0.0)
        self.register_buffer("bps_mask", raw_bps)
        self.register_buffer("origin_weights", _row_normalized_prior(raw_bps.numpy()))

    def encode(self, x: torch.Tensor, c: torch.Tensor):
        b, t, n, f = x.shape
        x_in = x
        if self.no_calendar:
            x_in = x.clone()
            x_in[..., self.calendar_idx] = 0
        z, hn = self.encoder(x_in.transpose(1, 2).reshape(b * n, t, f))
        h = hn[-1].reshape(b, n, -1)
        z = z.reshape(b, n, t, -1).transpose(1, 2)
        z_lag = self.lagged_states(z)
        climate = []
        for lag in range(8):
            end = t - 5 * lag
            climate.append(
                c[:, end - 5:end].mean(1) if end >= 5 else c.new_zeros(b, n, c.shape[-1])
            )
        e = self.climate_mlp(torch.cat(climate, dim=-1))
        if self.no_climate:
            e = torch.zeros_like(e)
        return x_in, h, z, z_lag, e

    def decode(
        self,
        encoded,
        c: torch.Tensor,
        s: torch.Tensor,
        candidate_mask: torch.Tensor,
        cal_future: torch.Tensor,
        *,
        update_ema: bool = True,
    ):
        x_in, h, z, z_lag, e = encoded
        b, t, n, _ = x_in.shape
        lag_mask = (torch.arange(self.n_lags, device=x_in.device) + 1) * 5 <= t
        a = self.graph(h, z_lag, e, s, candidate_mask, lag_mask)
        k = len(self.horizons)

        if self.forecast_aligned:
            offsets = torch.tensor(self.horizons, device=x_in.device)[:, None] - 1
            delays = 5 * (torch.arange(self.n_lags, device=x_in.device) + 1)
            indices = (t - 1 + offsets - delays).clamp(0, t - 1)
            values = self.value(z[:, indices]) + self.input_value(x_in[:, indices])
            messages = torch.einsum("bijl,bkljd->bkid", a, values)
        else:
            messages = torch.einsum("bijl,bljd->bid", a, self.value(z_lag))
            messages = messages[:, None].expand(-1, k, -1, -1)
        m_adapt = messages.mean(dim=1)

        static = self._static_graph(candidate_mask)
        stable_state = self.value(z_lag[:, 0])
        m_stable = torch.einsum("ij,bjd->bid", static, stable_state)

        c_recent = c[:, -10:].mean(1)
        shock_src = c_recent[..., self.climate_idx]
        if self.no_climate or self.no_climate_gate:
            shock = x_in.new_zeros(b, n, 3)
        else:
            shock = torch.einsum("ij,bjf->bif", static, shock_src)
            shock = torch.stack([shock[..., 0], shock[..., 1], shock[..., 2].abs()], dim=-1)

        p = a.float().clamp_min(1e-12)
        ent = -(p * p.log()).sum(dim=(-1, -2)) / max(math.log(float(n * self.n_lags)), 1.0)
        a_mean = a.float().mean(dim=-1)
        if update_ema and self.training:
            with torch.no_grad():
                self.a_train_mean.mul_(0.99).add_(a_mean.detach().mean(0) * 0.01)
        rel_dist = (a_mean - self.a_train_mean.to(a_mean.device)[None]).abs().sum(-1)
        rel = torch.stack([ent, rel_dist], dim=-1)
        shift = x_in[:, -20:].mean(1).abs().mean(-1, keepdim=True)
        if self.gate_override is not None:
            g = x_in.new_full((b, n, 1), float(self.gate_override))
        elif self.no_gate:
            g = x_in.new_ones(b, n, 1)
        else:
            g = self.gate(shock, rel, shift)
        if update_ema:
            self.last_gate = g
            self.last_adapt = m_adapt
            self.last_stable = m_stable
        z_t = g * m_adapt + (1.0 - g) * m_stable

        cal = cal_future
        if self.no_calendar:
            cal = torch.zeros_like(cal)
        hm = torch.cat([h, z_t], dim=-1)[:, None].expand(-1, k, -1, -1)
        cal = cal[:, :, None, :].expand(-1, -1, n, -1)
        outputs = self.head(torch.cat([hm, cal], dim=-1))
        yhat = outputs.diagonal(dim1=1, dim2=3).transpose(1, 2).contiguous()
        return yhat, a, static

    def forward(self, x, c, s, candidate_mask, cal_future):
        encoded = self.encode(x, c)
        yhat, a, _ = self.decode(encoded, c, s, candidate_mask, cal_future, update_ema=self.training)
        return yhat, a

    def forward_clean_and_perturbed(self, x, c, s, candidate_mask, perturbed_mask, cal_future):
        encoded = self.encode(x, c)
        yhat, a, static = self.decode(
            encoded, c, s, candidate_mask, cal_future, update_ema=self.training
        )
        yhat_tilde, a_tilde, _ = self.decode(
            encoded, c, s, perturbed_mask, cal_future, update_ema=False
        )
        return yhat, a, static, yhat_tilde, a_tilde


def build(panel: Panel, cfg: dict, spec: WindowSpec) -> Module4:
    prior = torch.as_tensor(panel.mask, dtype=torch.float32)
    return Module4(
        n_features=len(FEATURES),
        n_climate=len(CLIMATE_FEATURES),
        hidden=int(cfg.get("hidden", 64)),
        n_lags=int(cfg.get("n_lags", 6)),
        horizons=spec.horizons,
        n_nodes=panel.mask.shape[0],
        static_prior=prior,
        no_gate=bool(cfg.get("no_gate", False)),
        no_climate_gate=bool(cfg.get("no_climate_gate", False)),
        no_calendar=bool(cfg.get("no_calendar", False)),
        no_climate=bool(cfg.get("no_climate", cfg.get("no_climate_gate", False))),
    )


def prepare_module4(
    panel: Panel,
    cfg: dict,
    glob: dict,
    origin: str,
    seed: int,
    eval_parts: tuple[str, ...] = ("val", "test"),
    *,
    smoke: bool = False,
):
    seed_everything(seed)
    spec = WindowSpec(window=int(glob["window"]), horizons=tuple(glob["horizons"]))
    if origin == "HOLDOUT" and "test" in eval_parts:
        raise PermissionError("HOLDOUT test SEALED; refit hanya train/val")
    split = rolling_origin(origin, panel.dates, refit=origin == "HOLDOUT")
    prior_mode = str(cfg.get("prior", "soft_bps"))
    edge, cand, bps_bin = module4_edge_tensors(panel, prior_mode)
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
        ds = Module1Dataset(
            Subset(base, keep), panel, zero_climate=bool(cfg.get("zero_climate", False))
        )
        loaders[part] = DataLoader(
            ds,
            batch_size=int(cfg.get("batch_size", 64)),
            shuffle=part == "train",
            num_workers=0,
        )
        print(f"{part}: {len(keep)} windows", flush=True)
    model = build(panel, cfg, spec)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return model, spec, loaders, device, (edge.to(device), cand.to(device)), bps_bin.to(device)


def fit_module4(
    model: Module4,
    train_loader: DataLoader,
    val_loader: DataLoader,
    *,
    device: torch.device,
    a_prior: tuple[torch.Tensor, torch.Tensor],
    bps_mask: torch.Tensor,
    lr: float = 1e-3,
    epochs: int = 10,
    patience: int = 10,
    grad_clip: float = 5.0,
    amp: bool = True,
    checkpoint: Path | None = None,
    entropy_lambda: float = 0.0,
    lambda_perturb: float = 0.15,
    perturb_norm: str = "l1",
    perturb_p_min: float = 0.10,
    perturb_p_max: float = 0.50,
    perturb_mode: str = "mixed",
    lambda_group_var: float = 5.0,
    n_climate_groups: int = 3,
    group_feature: str = "rain_30d_anom",
    group_lookback: int = 5,
    lambda_prior: float = 0.05,
    prior_static_weight: float = 0.25,
    seed: int = 0,
) -> dict[str, Any]:
    device = torch.device(device)
    edge, cand = a_prior
    edge = edge.to(device)
    cand = cand.to(device)
    bps_mask = bps_mask.to(device)
    model = model.to(device)

    if group_feature not in CLIMATE_FEATURES:
        raise ValueError(f"group_feature harus salah satu {CLIMATE_FEATURES}, dapat {group_feature!r}")
    group_feat_idx = CLIMATE_FEATURES.index(group_feature)

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
    rng = np.random.default_rng(int(seed) + 104729)

    best, best_state, best_epoch, stale = float("inf"), None, 0, 0
    history: list[dict[str, float]] = []

    for epoch in range(1, int(epochs) + 1):
        model.train()
        tot_total = tot_pred = tot_pert = tot_vrex = tot_prior = tot_offbps = 0.0
        count = 0
        for batch in train_loader:
            x, c, y, mask, cal = _batch_parts(batch, device)
            if not mask.any():
                continue
            opt.zero_grad(set_to_none=True)
            cand_tilde = (
                perturb_candidate_mask(
                    cand,
                    bps_mask,
                    p_min=float(perturb_p_min),
                    p_max=float(perturb_p_max),
                    mode=str(perturb_mode),
                    rng=rng,
                )
                if float(lambda_perturb) > 0.0
                else None
            )
            with torch.autocast(device_type=device.type, enabled=use_amp):
                if cand_tilde is not None:
                    pred, a, static, pred_tilde, _ = model.forward_clean_and_perturbed(
                        x, c, edge, cand, cand_tilde, cal
                    )
                else:
                    enc = model.encode(x, c)
                    pred, a, static = model.decode(enc, c, edge, cand, cal, update_ema=True)
                    pred_tilde = None

                with torch.amp.autocast(device_type=device.type, enabled=False):
                    loss_pred = masked_log_mae(pred, y, mask)
                    loss_pert = (
                        perturbation_sensitivity_loss(pred, pred_tilde, mask, norm=str(perturb_norm))
                        if pred_tilde is not None
                        else pred.new_zeros((), dtype=torch.float32)
                    )
                    if float(lambda_group_var) > 0.0:
                        groups = causal_origin_climate_groups(
                            c,
                            model.origin_weights,
                            feature_idx=group_feat_idx,
                            n_groups=int(n_climate_groups),
                            lookback=int(group_lookback),
                        )
                        loss_vrex, _ = cross_regime_risk_loss(
                            pred, y, mask, groups, n_groups=int(n_climate_groups)
                        )
                    else:
                        loss_vrex = pred.new_zeros((), dtype=torch.float32)

                    loss_prior = (
                        soft_prior_l1_loss(
                            a, bps_mask, a_static=static, static_weight=float(prior_static_weight)
                        )
                        if float(lambda_prior) > 0.0
                        else pred.new_zeros((), dtype=torch.float32)
                    )

                    loss = (
                        loss_pred
                        + float(lambda_perturb) * loss_pert
                        + float(lambda_group_var) * loss_vrex
                        + float(lambda_prior) * loss_prior
                    )
                    if float(entropy_lambda) > 0.0:
                        loss = loss + float(entropy_lambda) * model.entropy_regularizer(a)

            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite training loss in Module 4")
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(grad_clip))
            scaler.step(opt)
            scaler.update()

            n_obs = int(mask.sum().item())
            off_bps = float(soft_prior_l1_loss(a.detach(), bps_mask, a_static=None).item())
            tot_total += float(loss.item()) * n_obs
            tot_pred += float(loss_pred.item()) * n_obs
            tot_pert += float(loss_pert.item()) * n_obs
            tot_vrex += float(loss_vrex.item()) * n_obs
            tot_prior += float(loss_prior.item()) * n_obs
            tot_offbps += off_bps * n_obs
            count += n_obs

        if not count:
            raise ValueError("Tidak ada target training")
        val = evaluate(model, val_loader, device, a_prior)
        ep_row = {
            "epoch": epoch,
            "train_total_loss": tot_total / count,
            "train_log_mae": tot_pred / count,
            "loss_perturb": tot_pert / count,
            "loss_vrex": tot_vrex / count,
            "loss_prior": tot_prior / count,
            "off_bps_mass": tot_offbps / count,
            "val_mae_rp": val,
        }
        history.append(ep_row)
        print(
            f"Epoch {epoch:03d} | logMAE={ep_row['train_log_mae']:.5f} "
            f"| pert={ep_row['loss_perturb']:.5f} | vrex={ep_row['loss_vrex']:.6f} "
            f"| prior={ep_row['loss_prior']:.4f} (offBPS={ep_row['off_bps_mass']:.3f}) "
            f"| valMAE={val:.2f}",
            flush=True,
        )
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
        torch.save(
            {
                "model_state_dict": best_state,
                "best_epoch": best_epoch,
                "val_mae_rp": best,
            },
            path,
        )
    allocated = reserved = None
    if device.type == "cuda":
        torch.cuda.synchronize(device)
        allocated = torch.cuda.max_memory_allocated(device) / 1e9
        reserved = torch.cuda.max_memory_reserved(device) / 1e9
    return {
        "best_epoch": best_epoch,
        "best_val_mae_rp": best,
        "history": history,
        "peak_allocated_gb": allocated,
        "peak_reserved_gb": reserved,
        "epochs_run": len(history),
    }


def run_registered_module4(
    panel: Panel,
    cfg: dict,
    origin: str,
    seed: int,
    *,
    checkpoint: Path | None = None,
    smoke: bool = False,
) -> pd.DataFrame:
    glob = cfg["global"]
    model, spec, loaders, device, prior, bps_bin = prepare_module4(
        panel, cfg, glob, origin, seed, ("val", "test"), smoke=smoke
    )
    stats = fit_module4(
        model,
        loaders["train"],
        loaders["val"],
        device=device,
        a_prior=prior,
        bps_mask=bps_bin,
        lr=float(cfg.get("lr", 1e-3)),
        epochs=int(cfg.get("epochs", 10)),
        patience=int(cfg.get("patience", 10)),
        grad_clip=float(cfg.get("grad_clip", 5.0)),
        amp=bool(cfg.get("amp", True)),
        checkpoint=checkpoint,
        entropy_lambda=float(cfg.get("entropy_lambda", 0.0)),
        lambda_perturb=float(cfg.get("lambda_perturb", 0.15)),
        perturb_norm=str(cfg.get("perturb_norm", "l1")),
        perturb_p_min=float(cfg.get("perturb_p_min", 0.10)),
        perturb_p_max=float(cfg.get("perturb_p_max", 0.50)),
        perturb_mode=str(cfg.get("perturb_mode", "mixed")),
        lambda_group_var=float(cfg.get("lambda_group_var", 5.0)),
        n_climate_groups=int(cfg.get("n_climate_groups", 3)),
        group_feature=str(cfg.get("group_feature", "rain_30d_anom")),
        group_lookback=int(cfg.get("group_lookback", 5)),
        lambda_prior=float(cfg.get("lambda_prior", 0.05)),
        prior_static_weight=float(cfg.get("prior_static_weight", 0.25)),
        seed=seed,
    )
    prices = asof_prices(panel)
    frames = []
    for part in ("val", "test"):
        for batch in loaders[part]:
            log_pred, _ = predict(model, batch, device, prior)
            pred = log_pred.float().exp().cpu().numpy()
            for i, k in enumerate(batch["t_index"].tolist()):
                for j, h in enumerate(spec.horizons):
                    frames.append(
                        pd.DataFrame(
                            {
                                "model": cfg.get("model", "module4"),
                                "fold": origin,
                                "seed": seed,
                                "part": part,
                                "date": panel.dates[k],
                                "target_date": panel.dates[k + h - 1],
                                "prov_code": list(panel.node_codes),
                                "h": h,
                                "y_true": batch["y"][i, j].numpy(),
                                "y_mask": batch["y_mask"][i, j].numpy(),
                                "y_pred": pred[i, j],
                                "naive_pred": prices.iloc[k].to_numpy(),
                            }
                        )
                    )
    out = pd.concat(frames, ignore_index=True)
    out.loc[~out["y_mask"].astype(bool), "y_true"] = np.nan
    out.attrs["training"] = stats
    return out


def run(panel: Panel, cfg: dict, origin: str, seed: int) -> pd.DataFrame:
    """Standard RAWIT experiment registry entry point for Module 4 (MLE-H5-04)."""
    return run_registered_module4(panel, cfg, origin, seed)
