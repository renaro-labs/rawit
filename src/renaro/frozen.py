"""MLE-H5-03 · Gate 2: latih, simpan, dan jalankan model beku.

Satu modul untuk dua jalur yang harus konsisten:

* ``train_frozen`` (dipakai ``scripts/run_gate2.py``): melatih satu model wajib
  untuk satu origin (``O1``/``O2``/``O3`` atau refit ``HOLDOUT``) dan satu seed
  dengan konfigurasi ``configs/models/gate2/<model>.yaml``, lalu mengembalikan
  prediksi validasi/uji (jalur loader standar) dan checkpoint ``ckpt.pt``.
* ``predict_frozen`` (dipakai ``scripts/predict.py``): memuat checkpoint dan
  memprediksi decision date di jendela ``[start, end]`` dari panel gabungan
  konteks + periode baru. **Tidak ada pelatihan apa pun.** Array input dibangun
  ulang secara independen dari ``WindowDataset``; uji kering (O3) membuktikan
  keduanya identik.

Holdout tetap tersegel: ``combine_panels`` hanya mau membaca data
``>= holdout_start`` bila kunci ``HOLDOUT_UNSEALED`` ada (CGS-H6-01).
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import yaml
from torch.utils.data import Subset

from renaro.baselines.naive import asof_prices, predict_naive_last, predict_seasonal_naive, price_matrix
from renaro.contract import (
    HOLDOUT_START,
    HORIZONS,
    ORIGINS,
    PROJECT_ROOT,
    PROV_CODES,
    content_hash,
    has_unseal_key,
    parse_range,
)
from renaro.data.datasets import CLIMATE_FEATURES, FEATURES, WindowDataset, WindowSpec, make_loader
from renaro.data.io import TARGET_EXCLUSION_FLAGS, Panel, _read, validate_dataset
from renaro.eval.splits import rolling_origin, split_indices

CONFIG_DIR = PROJECT_ROOT / "configs" / "models" / "gate2"

#: Model wajib Gate 2 (8) + pendamping yang ikut dibekukan.
MODELS: dict[str, str] = {
    "seasonal_naive": "naive",
    "naive_last": "naive",
    "lgbm_a": "lgbm",
    "lgbm_c": "lgbm",
    "gwn": "wavenet",
    "mtgnn": "wavenet",
    "latent_regime": "graph",
    "lag_graph": "graph",
    "module1": "graph",
    "module23": "graph",
}
REQUIRED = ("seasonal_naive", "lgbm_c", "gwn", "mtgnn", "latent_regime",
            "lag_graph", "module1", "module23")
NEURAL = ("gwn", "mtgnn", "latent_regime", "lag_graph", "module1", "module23")
CKPT_FORMAT = "rawit-gate2-ckpt/1"


# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
def config_path(model: str) -> Path:
    if model not in MODELS:
        raise ValueError(f"Model Gate 2 tidak dikenal: {model}")
    return CONFIG_DIR / f"{model}.yaml"


def load_config(model: str) -> dict:
    cfg = yaml.safe_load(config_path(model).read_text(encoding="utf-8")) or {}
    if cfg.get("model") != model:
        raise ValueError(f"{config_path(model)}: field model != {model}")
    if cfg.get("family") != MODELS[model]:
        raise ValueError(f"{config_path(model)}: family != {MODELS[model]}")
    return cfg


def load_global() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "configs" / "global.yaml").read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parts_for(origin: str) -> tuple[str, ...]:
    return ("val",) if origin == "HOLDOUT" else ("val", "test")


# ---------------------------------------------------------------------------
# Pembangun model (dipakai saat latih DAN saat memuat checkpoint)
# ---------------------------------------------------------------------------
def build_model(model: str, cfg: dict, panel: Panel, spec: WindowSpec):
    if model == "module1":
        from renaro.contract import N_LAG_BINS
        from renaro.models.module1 import ClimateConditionedLagGraph
        return ClimateConditionedLagGraph(
            n_features=len(FEATURES), n_climate=len(CLIMATE_FEATURES),
            n_edge_features=4, n_calendar_future=4,
            hidden=int(cfg.get("hidden", 64)), n_lags=int(cfg.get("n_lags", N_LAG_BINS)),
            horizons=spec.horizons, null_option=True,
            forecast_aligned=bool(cfg.get("forecast_aligned", False)),
            n_nodes=panel.mask.shape[0] if cfg.get("edge_lag_bias", True) else None,
        )
    if model == "lag_graph":
        from renaro.baselines.lag_graph import build
        return build(panel, cfg, spec)
    if model == "latent_regime":
        from renaro.baselines.latent_regime import build
        return build(panel, cfg, spec)
    if model == "module23":
        from renaro.models.module23 import build
        return build(panel, cfg, spec)
    if model == "gwn":
        from renaro.baselines.gwn import GraphWaveNetLite
        return GraphWaveNetLite(
            len(FEATURES), hidden=int(cfg["hidden"]), n_layers=int(cfg["n_layers"]),
            horizons=spec.horizons, dropout=float(cfg["dropout"]),
            use_prior=bool(cfg["use_prior"]), n_nodes=len(PROV_CODES),
            embedding_dim=int(cfg["embedding_dim"]),
        )
    if model == "mtgnn":
        from renaro.baselines.mtgnn import MTGNNLite
        return MTGNNLite(
            len(FEATURES), hidden=int(cfg["hidden"]), n_layers=int(cfg["n_layers"]),
            horizons=spec.horizons, dropout=float(cfg["dropout"]), n_nodes=len(PROV_CODES),
            embedding_dim=int(cfg["embedding_dim"]), top_k=int(cfg["top_k"]),
        )
    raise ValueError(f"Bukan model neural: {model}")


def wavenet_prior(model: str, cfg: dict, panel: Panel, device) -> torch.Tensor | None:
    if model == "gwn" and bool(cfg.get("use_prior", True)):
        return torch.as_tensor(panel.mask, dtype=torch.float32, device=device)
    return None


def _device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Latih (jalur loader standar)
# ---------------------------------------------------------------------------
def _frame(model: str, origin: str, seed: int, part: str, panel: Panel, k: int, h: int,
           y: np.ndarray, mask: np.ndarray, pred: np.ndarray, naive: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "model": model, "fold": origin, "seed": seed, "part": part,
        "date": panel.dates[k], "target_date": panel.dates[k + h - 1],
        "prov_code": list(panel.node_codes), "h": h,
        "y_true": y, "y_mask": mask, "y_pred": pred, "naive_pred": naive,
    })


def _finish(frames: list[pd.DataFrame]) -> pd.DataFrame:
    out = pd.concat(frames, ignore_index=True)
    out["y_mask"] = out["y_mask"].astype(bool)
    out.loc[~out["y_mask"], "y_true"] = np.nan
    return out


def _normalizer_of(loader) -> dict:
    ds = loader.dataset
    while not isinstance(ds, WindowDataset):
        ds = ds.base if hasattr(ds, "base") else ds.dataset
    return {"mean": [float(v) for v in ds.normalizer.mean],
            "std": [float(v) for v in ds.normalizer.std]}


def _train_graph(model: str, panel: Panel, cfg: dict, glob: dict, origin: str, seed: int):
    from renaro.models.module1_training import fit, predict, prepare

    eval_parts = parts_for(origin)
    net, spec, loaders, device, prior = prepare(
        panel, cfg, glob, origin, seed, eval_parts,
        model_factory=lambda p, c, s: build_model(model, c, p, s),
    )
    stats = fit(net, loaders["train"], loaders["val"], device=device, a_prior=prior,
                lr=float(cfg["lr"]), epochs=int(cfg["epochs"]), patience=int(cfg["patience"]),
                grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]),
                entropy_lambda=float(cfg.get("entropy_lambda", 0.0)))
    prices = asof_prices(panel)
    frames = []
    for part in eval_parts:
        for batch in loaders[part]:
            log_pred, _ = predict(net, batch, device, prior)
            pred = log_pred.float().exp().cpu().numpy()
            for i, k in enumerate(batch["t_index"].tolist()):
                for j, h in enumerate(spec.horizons):
                    frames.append(_frame(model, origin, seed, part, panel, k, h,
                                         batch["y"][i, j].numpy(), batch["y_mask"][i, j].numpy(),
                                         pred[i, j], prices.iloc[k].to_numpy()))
    state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    return _finish(frames), state, _normalizer_of(loaders["train"]), stats


def _train_wavenet(model: str, panel: Panel, cfg: dict, glob: dict, origin: str, seed: int):
    from renaro.train_loop import fit, seed_everything

    seed_everything(seed)
    spec = WindowSpec(window=int(glob["window"]), horizons=tuple(glob["horizons"]))
    split = rolling_origin(origin, panel.dates, refit=origin == "HOLDOUT")
    eval_parts = parts_for(origin)
    loaders = {}
    for part in ("train", *eval_parts):
        ds = WindowDataset(panel, origin, part, spec)
        official = set(split_indices(split, panel.dates, part, horizon=max(spec.horizons)))
        keep = [i for i, k in enumerate(ds.decision_indices) if k in official]
        if not keep:
            raise ValueError(f"{origin}/{part}: tidak ada window resmi")
        print(f"{part}: {len(keep)} windows", flush=True)
        loaders[part] = make_loader(Subset(ds, keep), batch_size=int(cfg["batch_size"]),
                                    shuffle=part == "train")
    net = build_model(model, cfg, panel, spec)
    logs = [item["y"][item["y_mask"]].log() for item in loaders["train"].dataset]
    with torch.no_grad():
        net.output_head[-1].bias.fill_(torch.cat(logs).median().item())
    device = _device()
    prior = wavenet_prior(model, cfg, panel, device)
    stats = fit(net, loaders["train"], loaders["val"], device=device, a_prior=prior,
                lr=float(cfg["lr"]), epochs=int(cfg["epochs"]), patience=int(cfg["patience"]),
                grad_clip=float(cfg["grad_clip"]), amp=bool(cfg["amp"]))
    prices = asof_prices(panel)
    frames = []
    net.eval()
    with torch.no_grad():
        for part in eval_parts:
            for batch in loaders[part]:
                pred = net(batch["X"].to(device), prior).float().exp().cpu().numpy()
                for i, k in enumerate(batch["t_index"].tolist()):
                    for j, h in enumerate(spec.horizons):
                        frames.append(_frame(model, origin, seed, part, panel, k, h,
                                             batch["y"][i, j].numpy(),
                                             batch["y_mask"][i, j].numpy(),
                                             pred[i, j], prices.iloc[k].to_numpy()))
    state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    return _finish(frames), state, _normalizer_of(loaders["train"]), stats


def _train_lgbm(model: str, panel: Panel, cfg: dict, origin: str, seed: int):
    from renaro.baselines.lgbm import fit_lgbm_direct, get_feature_columns, make_supervised, predict_level
    from renaro.features.tabular import build_tabular_features

    from renaro.baselines.lgbm import EARLY_STOPPING, LGBM_PARAMS

    for key, value in LGBM_PARAMS.items():
        if cfg.get(key) != value:
            raise ValueError(f"{model}: {key}={cfg.get(key)!r} berbeda dari LGBM_PARAMS ({value!r})")
    if cfg.get("early_stopping_rounds") != EARLY_STOPPING:
        raise ValueError(f"{model}: early_stopping_rounds berbeda dari kode ({EARLY_STOPPING})")
    variant = str(cfg["feature_variant"])
    split = rolling_origin(origin, panel.dates, refit=origin == "HOLDOUT")
    features = build_tabular_features(panel, variant=variant)
    eval_parts = parts_for(origin)
    idx = {part: split_indices(split, panel.dates, part, horizon=max(HORIZONS))
           for part in ("train", *eval_parts)}
    prices = asof_prices(panel)
    naive_lookup = (prices.rename_axis(index="date", columns="prov_code").stack(future_stack=True)
                    .rename("naive_pred").reset_index())
    boosters, best_it, columns, frames = {}, {}, None, []
    for h in HORIZONS:
        train = make_supervised(panel, features, idx["train"], h)
        val = make_supervised(panel, features, idx["val"], h)
        reg, val_pred = fit_lgbm_direct(train, val, horizon=h, seed=seed, feature_variant=variant)
        cols = get_feature_columns(train)
        if columns is None:
            columns = cols
        elif cols != columns:
            raise ValueError("Kolom fitur berbeda antar horizon")
        parts = {"val": val_pred}
        if "test" in eval_parts:
            test = make_supervised(panel, features, idx["test"], h)
            tp = test[["date", "prov_code", "target_date", "y_true", "y_mask"]].copy()
            tp["y_pred"] = predict_level(reg, test, cols)
            parts["test"] = tp
        for part, pred in parts.items():
            pred = pred.copy()
            pred["model"], pred["fold"], pred["seed"], pred["part"], pred["h"] = model, origin, seed, part, h
            frames.append(pred)
        best = int(reg.best_iteration_)
        boosters[str(h)] = reg.booster_.model_to_string(num_iteration=best)
        best_it[str(h)] = best
        print(f"{model} h={h} best_iteration={best}", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out["prov_code"] = out["prov_code"].astype(str)
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    out = out.merge(naive_lookup.assign(date=lambda d: pd.to_datetime(d["date"]).astype("datetime64[ns]"),
                                        prov_code=lambda d: d["prov_code"].astype(str)),
                    on=["date", "prov_code"], how="left", validate="many_to_one")
    out["y_mask"] = out["y_mask"].astype(bool)
    out.loc[~out["y_mask"], "y_true"] = np.nan
    payload = {"variant": variant, "feature_columns": list(columns), "boosters": boosters,
               "best_iteration": best_it}
    return out, payload


def _naive_preds(model: str, panel: Panel, origin: str, seed: int, decisions: dict[str, np.ndarray],
                 lag_days: int) -> pd.DataFrame:
    raw = price_matrix(panel)
    last = raw.shift(1).ffill()
    include = panel.nodes["include"].to_numpy(dtype=bool)
    frames = []
    for part, indices in decisions.items():
        for h in HORIZONS:
            for k in indices:
                k = int(k)
                if model == "naive_last":
                    pred = predict_naive_last(panel, k, h, last)
                else:
                    pred = predict_seasonal_naive(panel, k, h, lag_days=lag_days, prices=raw)
                y, m = panel.target_at(k, h)
                m = m & include
                frames.append(_frame(model, origin, seed, part, panel, k, h,
                                     np.where(m, y, np.nan), m, np.asarray(pred, dtype=float),
                                     last.iloc[k].to_numpy()))
    return _finish(frames)


def train_frozen(model: str, panel: Panel, origin: str, seed: int, *, cfg: dict | None = None,
                 glob: dict | None = None) -> tuple[pd.DataFrame, dict, dict]:
    """Latih satu run. Kembalikan (preds, ckpt_dict, training_stats)."""
    if origin not in ORIGINS:
        raise ValueError(f"Origin tidak dikenal: {origin}")
    cfg = copy.deepcopy(cfg if cfg is not None else load_config(model))
    glob = glob if glob is not None else load_global()
    family = MODELS[model]
    ckpt: dict[str, Any] = {
        "format": CKPT_FORMAT, "model": model, "family": family, "origin": origin, "seed": int(seed),
        "config": cfg, "split_hash": panel.split_hash,
        "window": int(glob["window"]), "horizons": [int(h) for h in glob["horizons"]],
        "train_range": ORIGINS[origin]["train"],
    }
    stats: dict = {}
    if family == "graph":
        preds, state, norm, stats = _train_graph(model, panel, cfg, glob, origin, seed)
        ckpt.update(state_dict=state, normalizer=norm)
    elif family == "wavenet":
        preds, state, norm, stats = _train_wavenet(model, panel, cfg, glob, origin, seed)
        ckpt.update(state_dict=state, normalizer=norm)
    elif family == "lgbm":
        preds, payload = _train_lgbm(model, panel, cfg, origin, seed)
        ckpt.update(lgbm=payload)
        stats = {"best_iteration": payload["best_iteration"]}
    elif family == "naive":
        split = rolling_origin(origin, panel.dates, refit=origin == "HOLDOUT")
        dec = {part: split_indices(split, panel.dates, part, horizon=max(HORIZONS))
               for part in parts_for(origin)}
        preds = _naive_preds(model, panel, origin, seed, dec, int(cfg.get("lag_days", 364)))
        ckpt.update(naive={"name": model, "lag_days": int(cfg.get("lag_days", 364))})
    else:  # pragma: no cover
        raise ValueError(family)
    preds["date"] = pd.to_datetime(preds["date"]).astype("datetime64[ns]")
    preds["target_date"] = pd.to_datetime(preds["target_date"]).astype("datetime64[ns]")
    if preds["date"].ge(pd.Timestamp(HOLDOUT_START)).any() or \
            preds["target_date"].ge(pd.Timestamp(HOLDOUT_START)).any():
        raise PermissionError("Prediksi latih memasuki HOLDOUT")
    return preds, ckpt, stats


def save_ckpt(ckpt: dict, path: Path) -> str:
    torch.save(ckpt, path)
    return sha256_file(path)


def load_ckpt(path: Path, expected_sha256: str | None = None) -> dict:
    path = Path(path)
    if expected_sha256 is not None:
        got = sha256_file(path)
        if got != expected_sha256:
            raise ValueError(f"SHA-256 checkpoint tidak cocok: {path} ({got} != {expected_sha256})")
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    if ckpt.get("format") != CKPT_FORMAT:
        raise ValueError(f"Format checkpoint tidak dikenal: {path}")
    return ckpt


# ---------------------------------------------------------------------------
# Panel gabungan (konteks dataset_v1 + periode baru)
# ---------------------------------------------------------------------------
def combine_panels(context_dir: Path, new_dir: Path, cutoff: pd.Timestamp) -> Panel:
    """Panel: baris < cutoff dari konteks; baris >= cutoff dari ``new_dir``.

    ``new_dir`` boleh memuat prefix < cutoff (mis. panel holdout_v1 penuh);
    prefix itu wajib identik dengan konteks. Membaca tanggal >= holdout_start
    butuh kunci HOLDOUT_UNSEALED (CGS-H6-01).
    """
    from renaro.data.io import load_panel

    cutoff = pd.Timestamp(cutoff)
    context = load_panel(Path(context_dir))
    new_dir = Path(new_dir)
    validate_dataset(new_dir)
    n_panel, n_target, n_nodes, n_mask = _read(new_dir)
    for frame in (n_panel, n_target):
        frame["date"] = pd.to_datetime(frame["date"])
    reads_holdout = bool((n_panel["date"] >= pd.Timestamp(HOLDOUT_START)).any()
                         or (n_target["date"] >= pd.Timestamp(HOLDOUT_START)).any())
    if reads_holdout and not has_unseal_key():
        raise PermissionError("Holdout terkunci: HOLDOUT_UNSEALED tidak ada di RENARO_SEALED_DIR")
    if not np.array_equal(np.asarray(n_mask), np.asarray(context.mask)):
        raise ValueError("bps_mask periode baru berbeda dari konteks")
    if n_nodes["prov_code"].astype(str).tolist() != context.nodes["prov_code"].astype(str).tolist() or \
            n_nodes["include"].astype(str).tolist() != context.nodes["include"].astype(str).tolist():
        raise ValueError("nodes.csv periode baru berbeda dari konteks")
    if list(n_panel.columns) != list(context.panel.columns) or \
            list(n_target.columns) != list(context.target.columns):
        raise ValueError("Kolom panel/target periode baru berbeda dari konteks")

    frames = {}
    for name, ctx, new in (("panel", context.panel, n_panel), ("target", context.target, n_target)):
        before = ctx[ctx["date"] < cutoff]
        prefix = new[new["date"] < cutoff]
        if len(prefix):
            # Prefix periode baru harus sama persis dengan konteks pada tanggal yang sama.
            common = before[before["date"].isin(prefix["date"].unique())]
            a = content_hash(common.reset_index(drop=True), ("date", "prov_code"))
            b = content_hash(prefix[prefix["date"].isin(common["date"].unique())]
                             .reset_index(drop=True)[list(common.columns)], ("date", "prov_code"))
            if a != b:
                raise ValueError(f"Prefix {name} periode baru tidak identik dengan konteks")
        after = new[new["date"] >= cutoff]
        both = pd.concat([before, after[list(before.columns)]], ignore_index=True)
        both = both.sort_values(["date", "prov_code"]).reset_index(drop=True)
        if both.duplicated(["date", "prov_code"]).any():
            raise ValueError(f"Duplikat (date, prov_code) di {name} gabungan")
        frames[name] = both
    dates = pd.DatetimeIndex(sorted(frames["panel"]["date"].unique()))
    if not dates.equals(pd.DatetimeIndex(sorted(frames["target"]["date"].unique()))):
        raise ValueError("Tanggal panel dan target gabungan tidak sama")
    return Panel(panel=frames["panel"], target=frames["target"], nodes=context.nodes,
                 mask=context.mask, dates=dates, node_codes=list(PROV_CODES),
                 split_hash=context.split_hash,
                 meta={"context": str(context_dir), "new": str(new_dir), "cutoff": str(cutoff.date()),
                       "reads_holdout": reads_holdout})


# ---------------------------------------------------------------------------
# Inferensi (array dibangun ulang tanpa WindowDataset)
# ---------------------------------------------------------------------------
class _Arrays:
    """Replika independen dari array WindowDataset + kalender Module1Dataset."""

    def __init__(self, panel: Panel, train_range: str, normalizer: dict | None):
        codes = list(PROV_CODES)
        dates = panel.dates
        t, n = len(dates), len(codes)
        grid = pd.MultiIndex.from_product([dates, codes], names=["date", "prov_code"])
        df = panel.panel.copy()
        tg = panel.target.copy()
        for frame in (df, tg):
            frame["date"] = pd.to_datetime(frame["date"])
            frame["prov_code"] = frame["prov_code"].astype(str)
        df = df.set_index(["date", "prov_code"]).reindex(grid)
        tg = tg.set_index(["date", "prov_code"]).reindex(grid)
        if df[list(FEATURES)].index.size != t * n:
            raise ValueError("Grid panel tidak lengkap")
        raw = df.loc[:, FEATURES].astype(float).to_numpy().reshape(t, n, len(FEATURES))
        p = FEATURES.index("price")
        raw[1:, :, p] = raw[:-1, :, p].copy()
        raw[0, :, p] = np.nan
        b, e = parse_range(train_range)
        sel = (dates >= pd.Timestamp(b)) & (dates <= pd.Timestamp(e))
        x64 = np.asarray(raw[sel], dtype=np.float64)
        finite = np.isfinite(x64)
        counts = finite.sum(axis=(0, 1))
        sums = np.where(finite, x64, 0).sum(axis=(0, 1))
        mean = np.divide(sums, counts, out=np.zeros(x64.shape[2]), where=counts > 0)
        diff = np.where(finite, x64 - mean, 0)
        var = np.divide((diff * diff).sum(axis=(0, 1)), counts, out=np.zeros(x64.shape[2]),
                        where=counts > 0)
        std = np.where((counts > 0) & (var > 1e-12), np.sqrt(var), 1.0)
        if normalizer is not None:
            if not (np.array_equal(mean, np.asarray(normalizer["mean"], dtype=np.float64))
                    and np.array_equal(std, np.asarray(normalizer["std"], dtype=np.float64))):
                raise ValueError("Normalizer konteks berbeda dari checkpoint (konteks latih tidak sama)")
        z = (np.asarray(raw, dtype=np.float64) - mean) / std
        self.x = np.where(np.isfinite(z), z, 0.0).astype(np.float32)
        self.clim_idx = [FEATURES.index(f) for f in CLIMATE_FEATURES]
        self.climate = self.x[:, :, self.clim_idx].copy()
        raw_y = tg["price"].astype(float).to_numpy().reshape(t, n)
        observed = tg["is_observed"].fillna(False).to_numpy(dtype=bool).reshape(t, n)
        for col in TARGET_EXCLUSION_FLAGS:
            if col in tg:
                observed = observed & ~tg[col].fillna(False).to_numpy(dtype=bool).reshape(t, n)
        self.y = np.where(observed, raw_y, 0.0).astype(np.float32)
        self.observed = observed
        self.include = panel.nodes["include"].to_numpy(dtype=bool, copy=True)
        cal = panel.panel[["date", "is_ramadan", "days_to_lebaran", "dow", "month"]].copy()
        cal["date"] = pd.to_datetime(cal["date"]).astype("datetime64[ns]")
        self.cal = cal.drop_duplicates("date").set_index("date")
        self.dates = dates

    def calendar(self, k: int, horizons: tuple[int, ...]) -> np.ndarray:
        idx = k + np.asarray(horizons, dtype=int) - 1
        rows = self.cal.reindex(pd.DatetimeIndex(self.dates[idx]))
        if rows[["dow", "month"]].isna().any().any():
            raise ValueError("kalender target tidak lengkap")
        return np.column_stack([
            rows["is_ramadan"].fillna(False).astype(float).to_numpy(),
            rows["days_to_lebaran"].fillna(0).astype(float).to_numpy() / 366.0,
            rows["dow"].astype(float).to_numpy() / 6.0,
            (rows["month"].astype(float).to_numpy() - 1.0) / 11.0,
        ]).astype(np.float32)


def decision_indices(dates: pd.DatetimeIndex, start, end, window: int, horizons) -> np.ndarray:
    """Decision k: start <= d_k <= end dan semua d_{k+h} <= end (aturan bagian uji)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    max_h = max(horizons)
    out = []
    for k in range(window - 1, len(dates) - max_h):
        if not (start <= dates[k] <= end):
            continue
        avail = dates[k + np.asarray(horizons)]
        if np.all((avail >= start) & (avail <= end)):
            out.append(k)
    if not out:
        raise ValueError(f"Tidak ada decision date di {start.date()}..{end.date()}")
    return np.asarray(out, dtype=np.int64)


def predict_frozen(ckpt: dict, panel: Panel, start, end, *, fold: str, part: str = "holdout",
                   device: torch.device | None = None) -> pd.DataFrame:
    """Prediksi model beku pada decision date di [start, end]. Tanpa pelatihan."""
    model, family, seed = ckpt["model"], ckpt["family"], int(ckpt["seed"])
    cfg = ckpt["config"]
    horizons = tuple(int(h) for h in ckpt["horizons"])
    window = int(ckpt["window"])
    if panel.split_hash != ckpt["split_hash"]:
        raise ValueError("split_hash konteks berbeda dari checkpoint")
    ks = decision_indices(panel.dates, start, end, window, horizons)
    prices = asof_prices(panel)
    if family == "naive":
        dec = {part: ks}
        out = _naive_preds(model, panel, fold, seed, dec, int(ckpt["naive"]["lag_days"]))
        return out
    if family == "lgbm":
        return _predict_lgbm(ckpt, panel, ks, fold=fold, part=part, prices=prices)
    device = device or _device()
    arrays = _Arrays(panel, ckpt["train_range"], ckpt["normalizer"])
    spec = WindowSpec(window=window, horizons=horizons)
    net = build_model(model, cfg, panel, spec)
    net.load_state_dict(ckpt["state_dict"])
    net = net.to(device).eval()
    bs = int(cfg["batch_size"])
    frames = []
    if family == "graph":
        from renaro.models.module1_training import _edge_tensors
        edge, cand = _edge_tensors(panel, str(cfg.get("prior", "bps")))
        edge, cand = edge.to(device), cand.to(device)
        zero_climate = bool(cfg.get("zero_climate", False))
    else:
        prior = wavenet_prior(model, cfg, panel, device)
    with torch.no_grad():
        for s in range(0, len(ks), bs):
            chunk = ks[s:s + bs]
            xs, cs, ys, ms, cals = [], [], [], [], []
            for k in chunk:
                k = int(k)
                lo = k - window + 1
                tgt = k + np.asarray(horizons) - 1
                x = arrays.x[lo:k + 1].copy()
                c = arrays.climate[lo:k + 1].copy()
                if family == "graph" and zero_climate:
                    x[..., arrays.clim_idx] = 0
                    c = np.zeros_like(c)
                xs.append(x)
                cs.append(c)
                ys.append(arrays.y[tgt])
                ms.append(arrays.observed[tgt] & arrays.include[None, :])
                if family == "graph":
                    cals.append(arrays.calendar(k, horizons))
            X = torch.from_numpy(np.stack(xs)).to(device)
            if family == "graph":
                C = torch.from_numpy(np.stack(cs)).to(device)
                CAL = torch.from_numpy(np.stack(cals)).to(device)
                log_pred, _ = net(X, C, edge, cand, CAL)
            else:
                log_pred = net(X, prior)
            pred = log_pred.float().exp().cpu().numpy()
            for i, k in enumerate(chunk):
                for j, h in enumerate(horizons):
                    frames.append(_frame(model, fold, seed, part, panel, int(k), h,
                                         ys[i][j], ms[i][j], pred[i, j], prices.iloc[int(k)].to_numpy()))
    return _finish(frames)


def _predict_lgbm(ckpt: dict, panel: Panel, ks: np.ndarray, *, fold: str, part: str,
                  prices: pd.DataFrame) -> pd.DataFrame:
    import lightgbm as lgb

    from renaro.baselines.lgbm import make_supervised, predict_level
    from renaro.features.tabular import build_tabular_features

    payload = ckpt["lgbm"]
    features = build_tabular_features(panel, variant=payload["variant"])
    cols = list(payload["feature_columns"])
    naive_lookup = (prices.rename_axis(index="date", columns="prov_code").stack(future_stack=True)
                    .rename("naive_pred").reset_index())
    naive_lookup["date"] = pd.to_datetime(naive_lookup["date"]).astype("datetime64[ns]")
    naive_lookup["prov_code"] = naive_lookup["prov_code"].astype(str)
    frames = []
    for h in (int(x) for x in ckpt["horizons"]):
        booster = lgb.Booster(model_str=payload["boosters"][str(h)])
        frame = make_supervised(panel, features, ks, h)
        if get_cols(frame) != cols:
            raise ValueError("Kolom fitur inferensi berbeda dari checkpoint")
        pred = frame[["date", "prov_code", "target_date", "y_true", "y_mask"]].copy()
        pred["y_pred"] = predict_level(booster, frame, cols)
        pred["model"], pred["fold"], pred["seed"], pred["part"], pred["h"] = (
            ckpt["model"], fold, int(ckpt["seed"]), part, h)
        frames.append(pred)
    out = pd.concat(frames, ignore_index=True)
    out["prov_code"] = out["prov_code"].astype(str)
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    out = out.merge(naive_lookup, on=["date", "prov_code"], how="left", validate="many_to_one")
    out["y_mask"] = out["y_mask"].astype(bool)
    out.loc[~out["y_mask"], "y_true"] = np.nan
    return out


def get_cols(frame: pd.DataFrame) -> list[str]:
    from renaro.baselines.lgbm import get_feature_columns
    return get_feature_columns(frame)


PRED_COLUMNS = ["model", "fold", "seed", "part", "date", "target_date", "prov_code", "h",
                "y_true", "y_mask", "y_pred", "naive_pred"]


def tidy(preds: pd.DataFrame) -> pd.DataFrame:
    out = preds[PRED_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    out["target_date"] = pd.to_datetime(out["target_date"]).astype("datetime64[ns]")
    out["prov_code"] = out["prov_code"].astype(str)
    out["h"] = out["h"].astype(int)
    out["seed"] = out["seed"].astype(int)
    out["y_mask"] = out["y_mask"].astype(bool)
    for c in ("y_true", "y_pred", "naive_pred"):
        out[c] = out[c].astype(float)
    return out.sort_values(["part", "h", "date", "prov_code"]).reset_index(drop=True)


def metrics(preds: pd.DataFrame) -> dict:
    out = {}
    for (part, h), g in preds.groupby(["part", "h"]):
        v = g[g["y_mask"].astype(bool) & np.isfinite(g["y_true"]) & np.isfinite(g["y_pred"])]
        out[f"{part}_h{int(h)}_mae"] = float((v["y_true"] - v["y_pred"]).abs().mean())
        out[f"{part}_h{int(h)}_n"] = int(len(v))
        out[f"{part}_h{int(h)}_n_mask"] = int(g["y_mask"].astype(bool).sum())
    return out
