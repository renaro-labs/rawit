"""MDE-H4-02 · Set perturbasi edge untuk graph prior (handoff CGS-H5-01).

Tiga operasi terhadap himpunan edge E (|E| = m) matriks biner A[i, j] (j -> i, diagonal 0):
  drop   p : hapus round(p*m) edge acak.
  add    p : tambah round(p*m) non-edge acak (bukan diagonal).
  rewire p : untuk round(p*m) edge j -> i, ganti asal j dengan j' acak sehingga j' -> i
             belum ada; in-degree tiap i tetap, jumlah edge tetap.

Grid: p in {10..50}% x {drop, add, rewire} x seed {0, 1, 2} = 45 matriks per prior.
Output: data/processed/perturbations/{base}_{op}_p{pp}_s{seed}.npy + index.csv.

RNG: np.random.default_rng(seed), urutan undian sama dengan stopgap MLE
`renaro.graph_perturb` (scripts/robustness.py -> masks.npz). drop/add identik dengan
masks.npz; rewire berbeda bila stopgap memindahkan edge kembali ke posisi asli
(di sini asal pengganti j' tidak boleh edge asli, jadi tepat round(p*m) edge berubah).

CLI: python -m renaro.graph.perturb [--base bps] [--base distance]
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

PRIORS = Path("data/processed/graph_priors")
OUT = Path("data/processed/perturbations")
OPS = ("drop", "add", "rewire")
PCTS = (10, 20, 30, 40, 50)
SEEDS = (0, 1, 2)
INDEX_COLUMNS = ("file", "base", "op", "p", "seed", "n_edges", "n_edges_base",
                 "jaccard_vs_base", "sha256")


def _binary(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a)
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError(f"matriks harus persegi, dapat {a.shape}")
    b = (a > 0).astype(np.uint8)
    if np.diag(b).any():
        raise ValueError("diagonal base harus 0")
    return b


def n_target(m: int, p: float) -> int:
    """round(p*m) (pembulatan Python, sama dengan stopgap MLE)."""
    return int(round(p * m))


def drop(a: np.ndarray, p: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = _binary(a).copy()
    on = np.argwhere(a > 0)
    k = n_target(len(on), p)
    if k:
        sel = on[rng.choice(len(on), k, replace=False)]
        a[sel[:, 0], sel[:, 1]] = 0
    return a


def add(a: np.ndarray, p: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = _binary(a).copy()
    m = int(a.sum())
    off = np.argwhere((a == 0) & ~np.eye(len(a), dtype=bool))
    k = min(n_target(m, p), len(off))
    if k:
        sel = off[rng.choice(len(off), k, replace=False)]
        a[sel[:, 0], sel[:, 1]] = 1
    return a


def rewire(a: np.ndarray, p: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = _binary(a)
    a = base.copy()
    on = np.argwhere(a > 0)
    k = n_target(len(on), p)
    if k:
        for i, j in on[rng.choice(len(on), k, replace=False)]:
            # j' bukan edge saat ini DAN bukan edge asli: tanpa syarat kedua, rewire berikutnya
            # bisa "mengembalikan" edge asli yang baru dipindah sehingga < k edge benar-benar berubah
            # (terjadi di stopgap MLE pada p besar).
            cand = np.flatnonzero((a[i] == 0) & (base[i] == 0) & (np.arange(len(a)) != i))
            if not len(cand):
                raise ValueError(f"baris {i} tidak punya asal pengganti")
            a[i, j] = 0
            a[i, rng.choice(cand)] = 1
    return a


OPERATIONS = {"drop": drop, "add": add, "rewire": rewire}


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a) > 0, np.asarray(b) > 0
    union = (a | b).sum()
    return float((a & b).sum() / union) if union else 1.0


def file_name(base: str, op: str, pct: int, seed: int) -> str:
    return f"{base}_{op}_p{pct:02d}_s{seed}.npy"


def grid(base_name: str, base: np.ndarray, ops=OPS, pcts=PCTS, seeds=SEEDS):
    """Yield (file, op, pct, seed, matriks) untuk 3 x 5 x 3 = 45 kombinasi."""
    b = _binary(base)
    for op in ops:
        for pct in pcts:
            for seed in seeds:
                yield file_name(base_name, op, pct, seed), op, pct, seed, OPERATIONS[op](b, pct / 100, seed)


def build(bases: dict[str, np.ndarray], out: Path = OUT) -> pd.DataFrame:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, base in bases.items():
        b = _binary(base)
        for fname, op, pct, seed, A in grid(name, b):
            assert A.dtype == np.uint8 and not np.diag(A).any()
            np.save(out / fname, A)
            rows.append({"file": fname, "base": name, "op": op, "p": pct / 100, "seed": seed,
                         "n_edges": int(A.sum()), "n_edges_base": int(b.sum()),
                         "jaccard_vs_base": round(jaccard(A, b), 6),
                         "sha256": hashlib.sha256(np.ascontiguousarray(A).tobytes()).hexdigest()})
    idx = pd.DataFrame(rows, columns=list(INDEX_COLUMNS))
    idx.to_csv(out / "index.csv", index=False, lineterminator="\n")
    return idx


def monotone_report(idx: pd.DataFrame) -> pd.DataFrame:
    """Rata-rata jaccard per (base, op, p) + cek turun monoton terhadap p (rata-rata & per seed)."""
    mean = idx.groupby(["base", "op", "p"])["jaccard_vs_base"].mean().reset_index()
    rows = []
    for (base, op), g in idx.groupby(["base", "op"]):
        m = g.groupby("p")["jaccard_vs_base"].mean().sort_index()
        per_seed = all(s.sort_values("p")["jaccard_vs_base"].is_monotonic_decreasing
                       and s["jaccard_vs_base"].nunique() == len(s) for _, s in g.groupby("seed"))
        rows.append({"base": base, "op": op,
                     "mean_strict_decreasing": bool((np.diff(m.to_numpy()) < 0).all()),
                     "per_seed_strict_decreasing": per_seed})
    return mean, pd.DataFrame(rows)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="MDE-H4-02 perturbasi edge")
    ap.add_argument("--base", action="append", choices=["bps", "distance", "surplus_deficit"],
                    help="prior dasar (default bps; distance dibinerkan: support k-NN)")
    ap.add_argument("--priors", type=Path, default=PRIORS)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    names = args.base or ["bps"]
    bases = {n: np.load(args.priors / f"{n}.npy", allow_pickle=False) for n in names}
    idx = build(bases, args.out)
    mean, mono = monotone_report(idx)
    for r in mono.itertuples():
        print(f"[{r.base}/{r.op:6s}] jaccard turun monoton: rata-rata={r.mean_strict_decreasing} "
              f"per-seed={r.per_seed_strict_decreasing}")
    piv = mean.pivot_table(index=["base", "op"], columns="p", values="jaccard_vs_base").round(3)
    print(piv.to_string())
    print(f"[out] {len(idx)} matriks -> {args.out} + index.csv")


if __name__ == "__main__":
    main()
