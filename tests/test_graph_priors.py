"""Uji graph prior (MDE-H4-01)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.contract import N_NODES, NODE_INDEX, PROV_CODES
from renaro.graph import priors as G

OUT = G.OUT


def test_haversine_known_distances():
    one_deg = G.EARTH_RADIUS_KM * np.pi / 180
    assert G.haversine_km(0, 0, 0, 1) == pytest.approx(one_deg, rel=1e-9)
    assert G.haversine_km(0, 100, 90, 100) == pytest.approx(90 * one_deg, rel=1e-9)
    # Jakarta (Monas) - Surabaya (Tugu Pahlawan): ~663 km great-circle
    d = G.haversine_km(-6.1754, 106.8272, -7.2458, 112.7378)
    assert 655 < d < 670
    assert G.haversine_km(1, 2, 3, 4) == pytest.approx(G.haversine_km(3, 4, 1, 2))


def test_spherical_mean_weights():
    lat, lon = G.spherical_mean(np.array([0.0, 0.0]), np.array([100.0, 102.0]), np.array([1.0, 1.0]))
    assert lat == pytest.approx(0, abs=1e-9) and lon == pytest.approx(101, abs=1e-9)
    lat, lon = G.spherical_mean(np.array([0.0, 0.0]), np.array([100.0, 102.0]), np.array([1.0, 0.0]))
    assert lon == pytest.approx(100, abs=1e-9)


def _line_dist(n=8):
    x = np.arange(n, dtype=float) * 100
    return np.abs(x[:, None] - x[None, :])


def test_distance_prior_k_per_row_and_weights():
    d = _line_dist()
    A, sigma = G.distance_prior(d, k=3)
    assert sigma == pytest.approx(np.median(G.off_diag(d)))
    assert ((A > 0).sum(axis=1) == 3).all() and np.all(np.diag(A) == 0)
    assert A[0, 1] == pytest.approx(np.exp(-(100 / sigma) ** 2))
    assert A[0, 4] == 0                                   # bukan 3 terdekat dari 0
    assert set(np.flatnonzero(A[4])) == {3, 5, 2}       # ties 2 vs 6 diputus indeks terkecil


def test_surplus_deficit_rule():
    d = _line_dist(6)
    sur = np.array([True, False, False, True, False, False])
    A = G.surplus_deficit_prior(sur, d, k=1)
    assert (A[sur] == 0).all()                              # tujuan surplus tidak menerima edge
    assert (A[:, ~sur] == 0).all()                          # asal harus surplus
    assert A[1, 0] == 1 and A[2, 3] == 1 and A[5, 3] == 1   # surplus terdekat
    assert ((A.sum(axis=1)[~sur]) == 1).all()


def test_full_prior():
    A = G.full_prior()
    assert A.sum() == N_NODES * (N_NODES - 1) and np.all(np.diag(A) == 0)


# ----------------------------------------------------------------- output nyata
need = pytest.mark.skipif(not (OUT / "meta.json").exists(), reason="jalankan: python -m renaro.graph.priors")
NAMES = ("bps", "distance", "distance_km", "surplus_deficit", "none")


@need
@pytest.mark.parametrize("name", NAMES)
def test_shape_and_zero_diagonal(name):
    A = np.load(OUT / f"{name}.npy")
    assert A.shape == (N_NODES, N_NODES)
    assert np.all(np.diag(A) == 0)
    assert np.isfinite(A).all() and (A >= 0).all()


@need
def test_convention_and_node_order_match_dataset_v1():
    nodes = pd.read_csv("data/processed/dataset_v1/nodes.csv", dtype={"prov_code": str})
    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    assert meta["node_order"] == nodes["prov_code"].tolist() == list(PROV_CODES)
    bps = np.load(OUT / "bps.npy")
    assert (bps == np.load("data/processed/dataset_v1/bps_mask.npy")).all()
    # edge known (MDE-H2-03): Aceh 11 -> Sumatera Barat 13 => A[13, 11] = 1, arah balik 0
    assert bps[NODE_INDEX["13"], NODE_INDEX["11"]] == 1 and bps[NODE_INDEX["11"], NODE_INDEX["13"]] == 0
    cent = pd.read_csv(OUT / "centroids.csv", dtype={"prov_code": str})
    assert cent["prov_code"].tolist() == list(PROV_CODES)


@need
def test_real_priors_consistent_with_meta():
    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    dkm = np.load(OUT / "distance_km.npy")
    assert np.allclose(dkm, dkm.T)
    dist = np.load(OUT / "distance.npy")
    k = meta["variants"]["distance"]["params"]["k"]
    assert ((dist > 0).sum(axis=1) == k).all()
    for i in range(N_NODES):                              # baris i = k asal terdekat i
        kept = np.flatnonzero(dist[i] > 0)
        others = np.setdiff1d(np.setdiff1d(np.arange(N_NODES), kept), [i])
        assert dkm[i, kept].max() <= dkm[i, others].min() + 1e-6
    sd = np.load(OUT / "surplus_deficit.npy")
    shares = pd.read_csv(OUT / "surplus_deficit_shares.csv", dtype={"prov_code": str})
    sur = shares["surplus"].to_numpy(bool)
    assert (sd[sur] == 0).all() and (sd[:, ~sur] == 0).all()
    assert ((sd.sum(axis=1)[~sur]) == min(k, sur.sum())).all()
    for name in NAMES:
        A = np.load(OUT / f"{name}.npy")
        assert meta["variants"][name]["n_edges"] == int((A != 0).sum())
        assert meta["sha256_arrays"][name] == G._sha(A)


@need
def test_population_reference_sums_to_sp2020_total():
    pop = pd.read_csv(G.POPULATION, dtype={"prov_code": str})
    assert pop["prov_code"].tolist() == sorted(PROV_CODES, key=int)
    assert pop["population"].sum() == 270_203_917          # total nasional SP2020 (BPS)
