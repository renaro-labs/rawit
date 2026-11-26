"""Directed graph-prior perturbations for CGS-H5-01."""
from __future__ import annotations

import numpy as np


def _offdiag(n: int) -> np.ndarray:
    return ~np.eye(n, dtype=bool)


def drop_edges(a: np.ndarray, frac: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = (np.asarray(a) > 0).astype(np.uint8)
    on = np.argwhere(a > 0)
    k = int(round(frac * len(on)))
    if k:
        sel = on[rng.choice(len(on), k, replace=False)]
        a[sel[:, 0], sel[:, 1]] = 0
    return a


def add_edges(a: np.ndarray, frac: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = (np.asarray(a) > 0).astype(np.uint8)
    n_on = int(a.sum())
    off = np.argwhere((a == 0) & _offdiag(len(a)))
    k = min(int(round(frac * n_on)), len(off))
    if k:
        sel = off[rng.choice(len(off), k, replace=False)]
        a[sel[:, 0], sel[:, 1]] = 1
    return a


def rewire_edges(a: np.ndarray, frac: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = (np.asarray(a) > 0).astype(np.uint8)
    on = np.argwhere(a > 0)
    k = int(round(frac * len(on)))
    if k:
        for i, j in on[rng.choice(len(on), k, replace=False)]:
            candidates = np.flatnonzero((a[i] == 0) & (np.arange(len(a)) != i))
            if len(candidates):
                a[i, j] = 0
                a[i, rng.choice(candidates)] = 1
    return a


PERTURBATIONS = {"drop": drop_edges, "add": add_edges, "rewire": rewire_edges}


def perturbation_grid(a, kinds=("drop", "add", "rewire"),
                      fracs=(0.10, 0.20, 0.30, 0.40, 0.50), seeds=(0, 1, 2)):
    """Yield clean, no-prior, and 3 ops x 5 fractions x 3 perturbation seeds."""
    base = (np.asarray(a) > 0).astype(np.uint8)
    yield "clean", base.copy(), "clean", 0.0, -1
    yield "none", np.zeros_like(base), "none", 0.0, -1
    for op in kinds:
        for frac in fracs:
            for seed in seeds:
                yield (f"{op}_{int(frac * 100)}_s{seed}",
                       PERTURBATIONS[op](base, frac, seed), op, frac, seed)
