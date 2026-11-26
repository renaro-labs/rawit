"""Uji perturbasi edge (MDE-H4-02)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.graph import perturb as P

OUT = P.OUT


def _base(n=12, m=30, seed=5):
    rng = np.random.default_rng(seed)
    a = np.zeros((n, n), dtype=np.uint8)
    off = np.argwhere(~np.eye(n, dtype=bool))
    sel = off[rng.choice(len(off), m, replace=False)]
    a[sel[:, 0], sel[:, 1]] = 1
    return a


@pytest.mark.parametrize("pct", P.PCTS)
def test_edge_counts_per_operation(pct):
    a = _base()
    m, k = int(a.sum()), int(round(pct / 100 * a.sum()))
    d, ad, rw = P.drop(a, pct / 100, 0), P.add(a, pct / 100, 0), P.rewire(a, pct / 100, 0)
    assert d.sum() == m - k and ((d == 1) <= (a == 1)).all()          # hanya menghapus
    assert ad.sum() == m + k and ((a == 1) <= (ad == 1)).all()        # hanya menambah
    assert rw.sum() == m
    assert (rw.sum(axis=1) == a.sum(axis=1)).all()                    # in-degree tiap tujuan i tetap
    assert ((a == 1) & (rw == 0)).sum() == k                          # tepat k edge asal dipindah


@pytest.mark.parametrize("op", P.OPS)
def test_no_diagonal_binary_uint8(op):
    a = _base()
    for pct in P.PCTS:
        x = P.OPERATIONS[op](a, pct / 100, 1)
        assert x.dtype == np.uint8 and set(np.unique(x)) <= {0, 1}
        assert not np.diag(x).any()


@pytest.mark.parametrize("op", P.OPS)
def test_deterministic_per_seed_and_seed_matters(op):
    a = _base()
    f = P.OPERATIONS[op]
    assert np.array_equal(f(a, 0.3, 2), f(a, 0.3, 2))
    assert not np.array_equal(f(a, 0.3, 0), f(a, 0.3, 1))
    assert np.array_equal(a, _base())                                   # input tidak diubah


def test_rejects_diagonal_base():
    a = _base()
    a[0, 0] = 1
    with pytest.raises(ValueError):
        P.drop(a, 0.1, 0)


def test_grid_is_45():
    items = list(P.grid("x", _base()))
    assert len(items) == 45 and len({f for f, *_ in items}) == 45
    assert items[0][0] == "x_drop_p10_s0.npy"


# ---------------------------------------------------------------- output nyata
need = pytest.mark.skipif(not (OUT / "index.csv").exists(), reason="jalankan: python -m renaro.graph.perturb")


@need
def test_index_and_files():
    idx = pd.read_csv(OUT / "index.csv")
    assert {"file", "base", "op", "p", "seed", "n_edges", "jaccard_vs_base"} <= set(idx.columns)
    bps = idx[idx["base"] == "bps"]
    assert len(bps) == 45
    base = np.load("data/processed/graph_priors/bps.npy")
    for r in bps.itertuples():
        A = np.load(OUT / r.file)
        assert A.shape == base.shape and not np.diag(A).any()
        assert int(A.sum()) == r.n_edges
        assert P.jaccard(A, base) == pytest.approx(r.jaccard_vs_base, abs=1e-6)


@need
def test_jaccard_decreases_monotonically_with_p():
    idx = pd.read_csv(OUT / "index.csv")
    _, mono = P.monotone_report(idx)
    assert mono["mean_strict_decreasing"].all(), mono
    assert mono["per_seed_strict_decreasing"].all(), mono


@need
def test_drop_add_identical_to_mle_stopgap_masks():
    """drop/add sama persis dengan masks.npz (scripts/robustness.py, H5); rewire dicek terpisah."""
    z_path = OUT / "masks.npz"
    if not z_path.exists():
        pytest.skip("masks.npz MLE tidak ada")
    z = np.load(z_path)
    idx = pd.read_csv(OUT / "index.csv")
    for r in idx[(idx["base"] == "bps") & (idx["op"] != "rewire")].itertuples():
        assert np.array_equal(np.load(OUT / r.file), z[f"{r.op}_{int(round(r.p * 100))}_s{r.seed}"]), r.file


@need
def test_rewire_moves_exactly_k_edges_on_bps():
    idx = pd.read_csv(OUT / "index.csv")
    base = np.load("data/processed/graph_priors/bps.npy")
    m = int(base.sum())
    for r in idx[(idx["base"] == "bps") & (idx["op"] == "rewire")].itertuples():
        A = np.load(OUT / r.file)
        k = int(round(r.p * m))
        assert ((base == 1) & (A == 0)).sum() == k
        assert r.jaccard_vs_base == pytest.approx((m - k) / (m + k), abs=1e-6)
