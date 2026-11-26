"""MDE-H4-01 · Varian graph prior (34 provinsi, konvensi kontrak A[i, j] = j -> i).

Varian (semua diagonal 0, urutan baris/kolom = PROV_CODES = dataset_v1/nodes.csv):
  bps.npy              salinan dataset_v1/bps_mask.npy (uint8, BPS Poldis 2022)
  distance_km.npy      jarak haversine antar centroid berbobot produksi (float32, simetris)
  distance.npy         w = exp(-(d/sigma)^2), sigma = median jarak; hanya k tetangga
                       terdekat per tujuan i (baris) yang dipertahankan (float32, berarah)
  surplus_deficit.npy  j -> i bila j surplus, i defisit, j salah satu k surplus terdekat i (uint8)
  none.npy             1 di luar diagonal (kandidat penuh; graph dipelajari) (uint8)
  meta.json            jumlah edge, densitas, parameter, sumber, hash

CLI: python -m renaro.graph.priors
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import N_NODES, NODE_INDEX, PROV_CODES, PROVINCES, sha256_file

OUT = Path("data/processed/graph_priors")
BPS_MASK = Path("data/processed/dataset_v1/bps_mask.npy")
NODES = Path("data/processed/dataset_v1/nodes.csv")
KAB = Path("data/raw/bps/kab_area_weights.csv")           # CGS-H1-03: kab -> prov, produksi 2024, luas
ADM2 = Path("data/raw/boundaries/adm2_to_adm1.csv")      # titik representatif ADM2 (geoBoundaries)
PROD_PROV = Path("data/raw/bps/produksi_prov.csv")       # produksi provinsi 2017-2024
POPULATION = Path("data/ref/population_sp2020.csv")      # BPS SP2020
FIGURE = Path("reports/figures/graph_priors.png")

K = 5
EARTH_RADIUS_KM = 6371.0088
#: Pangsa produksi untuk surplus/defisit: tahun 2017 = satu-satunya tahun yang sudah tersedia
#: sebelum train mulai (2018-01-02; aturan produksi y dipakai mulai y+1). Sensitivitas
#: dengan rata-rata 2017-2024 dicatat di meta.json.
PROD_YEARS = (2017,)
PROD_YEARS_SENS = tuple(range(2017, 2025))
PROV_NAME = dict(PROVINCES)


# -------------------------------------------------------------------- geometri
def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Jarak great-circle (km). Input derajat; broadcasting numpy."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def spherical_mean(lat: np.ndarray, lon: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    """Rata-rata berbobot di bola (vektor satuan), aman untuk provinsi lebar."""
    la, lo = np.radians(lat), np.radians(lon)
    v = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=1)
    m = (v * (w / w.sum())[:, None]).sum(axis=0)
    return float(np.degrees(np.arctan2(m[2], np.hypot(m[0], m[1])))), float(np.degrees(np.arctan2(m[1], m[0])))


def province_centroids(kab: pd.DataFrame, adm2: pd.DataFrame) -> pd.DataFrame:
    """Centroid berbobot produksi kab 2024 per provinsi; fallback (produksi 0) = berbobot luas."""
    k = kab.merge(adm2[["adm2_shapeID", "rep_lat", "rep_lon"]], left_on="shapeID",
                  right_on="adm2_shapeID", how="left", validate="many_to_one")
    if k["rep_lat"].isna().any():
        raise ValueError(f"kab tanpa koordinat: {k.loc[k.rep_lat.isna(), 'kab_name'].tolist()}")
    rows = []
    for code in PROV_CODES:
        g = k[k["prov_code"].astype(str) == code]
        if g.empty:
            raise ValueError(f"provinsi {code} tanpa kab")
        prod = g["produksi_ton"].fillna(0).to_numpy(float)
        if prod.sum() > 0:
            lat, lon = spherical_mean(g.rep_lat.to_numpy(), g.rep_lon.to_numpy(), prod)
            method = "production_weighted_kab_2024"
        else:
            lat, lon = spherical_mean(g.rep_lat.to_numpy(), g.rep_lon.to_numpy(), g.area_km2.to_numpy(float))
            method = "area_weighted_fallback"
        rows.append({"prov_code": code, "prov_name": PROV_NAME[code], "lat": lat, "lon": lon,
                     "n_kab": len(g), "produksi_kab_2024_ton": float(prod.sum()), "method": method})
    return pd.DataFrame(rows)


def distance_matrix(cent: pd.DataFrame) -> np.ndarray:
    lat, lon = cent["lat"].to_numpy(), cent["lon"].to_numpy()
    d = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    np.fill_diagonal(d, 0.0)
    return d


# ---------------------------------------------------------------------- prior
def off_diag(d: np.ndarray) -> np.ndarray:
    return d[~np.eye(len(d), dtype=bool)]


def nearest(d_row: np.ndarray, i: int, k: int, candidates: np.ndarray | None = None) -> np.ndarray:
    """Indeks k terdekat dari i (tanpa i sendiri), ties diputus oleh indeks node (stabil)."""
    idx = np.arange(len(d_row)) if candidates is None else np.asarray(candidates)
    idx = idx[idx != i]
    order = np.lexsort((idx, d_row[idx]))
    return idx[order][:k]


def distance_prior(dist_km: np.ndarray, sigma: float | None = None, k: int = K) -> tuple[np.ndarray, float]:
    """A[i, j] = exp(-(d_ij/sigma)^2) untuk k asal j terdekat dari tujuan i; lainnya 0."""
    sigma = float(np.median(off_diag(dist_km))) if sigma is None else float(sigma)
    if sigma <= 0:
        raise ValueError("sigma harus > 0")
    w = np.exp(-((dist_km / sigma) ** 2))
    A = np.zeros_like(dist_km, dtype=np.float32)
    for i in range(len(dist_km)):
        js = nearest(dist_km[i], i, k)
        A[i, js] = w[i, js]
    np.fill_diagonal(A, 0)
    return A, sigma


def shares(prod: pd.DataFrame, pop: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    p = prod[prod["year"].isin(years)].copy()
    p["prov_code"] = p["prov_code"].astype(str)
    mean = p.groupby("prov_code")["produksi_ton"].mean().reindex(list(PROV_CODES))
    if mean.isna().any():
        raise ValueError(f"produksi kosong untuk {mean[mean.isna()].index.tolist()} tahun {years}")
    pp = pop.assign(prov_code=pop["prov_code"].astype(str)).set_index("prov_code")["population"].reindex(list(PROV_CODES))
    if pp.isna().any():
        raise ValueError(f"populasi kosong untuk {pp[pp.isna()].index.tolist()}")
    out = pd.DataFrame({"prod_ton": mean, "population": pp})
    out["prod_share"] = out["prod_ton"] / out["prod_ton"].sum()
    out["pop_share"] = out["population"] / out["population"].sum()
    out["surplus"] = out["prod_share"] > out["pop_share"]
    return out.reset_index()


def surplus_deficit_prior(is_surplus: np.ndarray, dist_km: np.ndarray, k: int = K) -> np.ndarray:
    """A[i, j] = 1 bila j surplus, i defisit, dan j termasuk k surplus terdekat dari i."""
    A = np.zeros(dist_km.shape, dtype=np.uint8)
    sur = np.flatnonzero(is_surplus)
    for i in np.flatnonzero(~is_surplus):
        A[i, nearest(dist_km[i], i, k, sur)] = 1
    return A


def full_prior(n: int = N_NODES) -> np.ndarray:
    A = np.ones((n, n), dtype=np.uint8)
    np.fill_diagonal(A, 0)
    return A


def validate(name: str, A: np.ndarray, *, binary: bool, symmetric: bool = False) -> None:
    assert A.shape == (N_NODES, N_NODES), f"{name}: shape {A.shape}"
    assert np.all(np.diag(A) == 0), f"{name}: diagonal harus 0"
    assert np.isfinite(A).all() and (A >= 0).all(), f"{name}: nilai tidak valid"
    if binary:
        assert set(np.unique(A)).issubset({0, 1}), f"{name}: harus biner"
    if symmetric:
        assert np.allclose(A, A.T), f"{name}: harus simetris"


def stats(A: np.ndarray) -> dict:
    n = int((A != 0).sum())
    return {"n_edges": n, "density": round(n / (N_NODES * (N_NODES - 1)), 4),
            "in_degree_min": int((A != 0).sum(1).min()), "in_degree_max": int((A != 0).sum(1).max()),
            "out_degree_max": int((A != 0).sum(0).max()),
            "n_isolated_rows": int(((A != 0).sum(1) == 0).sum()),
            "dtype": str(A.dtype), "symmetric": bool(np.allclose(A, A.T))}


def _sha(A: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(A).tobytes()).hexdigest()


# ---------------------------------------------------------------------- figur
def plot(path: Path, priors: dict[str, np.ndarray], cent: pd.DataFrame, sd: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lat, lon = cent["lat"].to_numpy(), cent["lon"].to_numpy()
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    names = ["bps", "distance", "surplus_deficit", "none"]
    titles = {"bps": "BPS Poldis 2022 (biner)", "distance": f"Jarak: exp(-(d/σ)²), k={K}",
              "surplus_deficit": f"Surplus → defisit, k={K}", "none": "None (penuh, dipelajari)"}
    sur = sd["surplus"].to_numpy()
    for ax, name in zip(axes.flat, names):
        A = priors[name]
        wmax = A.max() if A.max() > 0 else 1
        for i, j in zip(*np.nonzero(A)):
            alpha = 0.05 if name == "none" else 0.25 + 0.6 * float(A[i, j]) / wmax
            ax.annotate("", xy=(lon[i], lat[i]), xytext=(lon[j], lat[j]),
                        arrowprops=dict(arrowstyle="-|>", lw=0.6, color="#2b6cb0", alpha=alpha,
                                        shrinkA=3, shrinkB=3))
        colors = np.where(sur, "#c05621", "#4a5568") if name == "surplus_deficit" else "#4a5568"
        ax.scatter(lon, lat, s=18, c=colors, zorder=3)
        for code, x, y in zip(cent.prov_code, lon, lat):
            ax.text(x, y + 0.35, code, fontsize=6, ha="center", color="#1a202c")
        s = stats(A)
        ax.set_title(f"{titles[name]} — {s['n_edges']} edge, densitas {s['density']:.1%}", fontsize=10)
        ax.set_xlim(94, 142)
        ax.set_ylim(-11.5, 6.5)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
    axes.flat[2].scatter([], [], c="#c05621", s=18, label="surplus")
    axes.flat[2].scatter([], [], c="#4a5568", s=18, label="defisit")
    axes.flat[2].legend(fontsize=7, loc="lower left")
    fig.suptitle("Graph prior (panah j → i = A[i, j]); titik = centroid berbobot produksi provinsi", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------- main
def build(bps_mask: Path = BPS_MASK, nodes: Path = NODES, kab: Path = KAB, adm2: Path = ADM2,
          prod_prov: Path = PROD_PROV, population: Path = POPULATION, k: int = K):
    nd = pd.read_csv(nodes, dtype={"prov_code": str})
    if nd["prov_code"].tolist() != list(PROV_CODES):
        raise ValueError("urutan nodes.csv berbeda dari PROV_CODES")
    cent = province_centroids(pd.read_csv(kab, dtype={"prov_code": str}), pd.read_csv(adm2))
    dist_km = distance_matrix(cent)
    prod = pd.read_csv(prod_prov, dtype={"prov_code": str})
    pop = pd.read_csv(population, dtype={"prov_code": str})
    sd = shares(prod, pop, PROD_YEARS)
    sd_sens = shares(prod, pop, PROD_YEARS_SENS)
    dist_w, sigma = distance_prior(dist_km, k=k)
    priors = {
        "bps": np.load(bps_mask, allow_pickle=False),
        "distance": dist_w,
        "distance_km": dist_km.astype(np.float32),
        "surplus_deficit": surplus_deficit_prior(sd["surplus"].to_numpy(), dist_km, k),
        "none": full_prior(),
    }
    validate("bps", priors["bps"], binary=True)
    validate("distance", priors["distance"], binary=False)
    validate("distance_km", priors["distance_km"], binary=False, symmetric=True)
    validate("surplus_deficit", priors["surplus_deficit"], binary=True)
    validate("none", priors["none"], binary=True, symmetric=True)
    return priors, cent, sd, sd_sens, sigma


def write(out: Path, priors, cent, sd, sd_sens, sigma, k, figure: Path | None, sources: dict) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, A in priors.items():
        np.save(out / f"{name}.npy", A)
    cent.to_csv(out / "centroids.csv", index=False, lineterminator="\n", float_format="%.6f")
    sd.to_csv(out / "surplus_deficit_shares.csv", index=False, lineterminator="\n", float_format="%.6f")
    flips = sd.loc[sd["surplus"] != sd_sens["surplus"], "prov_code"].tolist()
    meta = {
        "convention": "A[i, j] = pengaruh/aliran dari asal j ke tujuan i (baris = tujuan, kolom = asal)",
        "node_order": list(PROV_CODES),
        "node_order_source": "renaro.contract.PROV_CODES = data/processed/dataset_v1/nodes.csv",
        "diagonal": 0,
        "variants": {
            "bps": {**stats(priors["bps"]), "params": {},
                    "source": "data/processed/dataset_v1/bps_mask.npy (BPS Poldis 2022, MDE-H2-03)"},
            "distance": {**stats(priors["distance"]),
                         "params": {"sigma_km": round(sigma, 3), "sigma_rule": "median jarak off-diagonal",
                                    "k": k, "k_rule": "k asal terdekat per tujuan i (baris)",
                                    "weight": "exp(-(d/sigma)^2)",
                                    "w_min": round(float(priors["distance"][priors["distance"] > 0].min()), 6),
                                    "w_max": round(float(priors["distance"].max()), 6)},
                         "source": "haversine antar centroid berbobot produksi (centroids.csv)"},
            "distance_km": {**stats(priors["distance_km"]),
                            "params": {"earth_radius_km": EARTH_RADIUS_KM,
                                       "min_km": round(float(off_diag(priors["distance_km"]).min()), 1),
                                       "median_km": round(sigma, 1),
                                       "max_km": round(float(priors["distance_km"].max()), 1)},
                            "source": "haversine mentah, simetris"},
            "surplus_deficit": {**stats(priors["surplus_deficit"]),
                                "params": {"k": k, "surplus_rule": "pangsa produksi > pangsa populasi",
                                           "production_years": list(PROD_YEARS),
                                           "n_surplus": int(sd["surplus"].sum()),
                                           "surplus": sd.loc[sd["surplus"], "prov_code"].tolist(),
                                           "sensitivity_years": [PROD_YEARS_SENS[0], PROD_YEARS_SENS[-1]],
                                           "sensitivity_status_flips": flips},
                                "source": "BPS produksi cabai besar provinsi (produksi_prov.csv) + BPS SP2020"},
            "none": {**stats(priors["none"]), "params": {}, "source": "kandidat penuh (graph dipelajari)"},
        },
        "centroid": {"method": "rata-rata sferis titik representatif ADM2 berbobot produksi kab 2024; "
                               "fallback berbobot luas bila produksi provinsi 0",
                     "n_fallback": int((cent["method"] != "production_weighted_kab_2024").sum())},
        "sources": sources,
        "sha256_arrays": {name: _sha(A) for name, A in priors.items()},
        "notes": [
            "Pangsa produksi memakai 2017 (tersedia mulai 2018, sebelum train 2018-01-02).",
            "Populasi SP2020 (rilis Jan 2021) dipakai sebagai proksi pangsa populasi statis; pangsa antarprovinsi berubah lambat.",
            "Centroid memakai produksi kab 2024 (satu-satunya tabel kab tervalidasi, CGS-H1-03); hanya memengaruhi posisi, bukan status surplus.",
            "Edge prior bukan arus pasokan terukur.",
        ],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8", newline="\n")
    if figure:
        plot(Path(figure), priors, cent, sd)
    return meta


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="MDE-H4-01 graph priors")
    ap.add_argument("--bps-mask", type=Path, default=BPS_MASK)
    ap.add_argument("--nodes", type=Path, default=NODES)
    ap.add_argument("--kab", type=Path, default=KAB)
    ap.add_argument("--adm2", type=Path, default=ADM2)
    ap.add_argument("--prod-prov", type=Path, default=PROD_PROV)
    ap.add_argument("--population", type=Path, default=POPULATION)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--figure", type=Path, default=FIGURE)
    ap.add_argument("--k", type=int, default=K)
    args = ap.parse_args(argv)

    priors, cent, sd, sd_sens, sigma = build(args.bps_mask, args.nodes, args.kab, args.adm2,
                                             args.prod_prov, args.population, args.k)
    srcs = {name: f"{Path(p).as_posix()}:{sha256_file(p)}" for name, p in
            {"bps_mask": args.bps_mask, "nodes": args.nodes, "kab_area_weights": args.kab,
             "adm2_to_adm1": args.adm2, "produksi_prov": args.prod_prov,
             "population_sp2020": args.population}.items()}
    meta = write(args.out, priors, cent, sd, sd_sens, sigma, args.k, args.figure, srcs)
    for name, v in meta["variants"].items():
        print(f"[{name:15s}] edge={v['n_edges']:5d} densitas={v['density']:.2%} {v['params'] if v['params'] else ''}")
    print(f"[out] {args.out}  figur={args.figure}")


if __name__ == "__main__":
    main()
