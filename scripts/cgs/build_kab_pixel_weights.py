#!/usr/bin/env python3
"""Build the kab/kota -> CHIRPS pixel weight matrix from idn_adm2.gpkg.

The H1 package already contains per-kab area summaries (`n_cells`, `area_weight`)
but not the pixel indices.  This script recovers them by rasterising the ADM2
polygons on the 0.05-degree CHIRPS grid:

  W[kab, pixel] = 1 for cells whose centre falls inside the polygon,
                  normalised to 1 per kab.
  Small kabs with no cell centre inside use the 9 nearest cell centres
  (area_method='nearest_9', matching the H1 package).

Output: data/interim/w_kab_pixel.npz with row order = kab_area_weights.csv.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from shapely import contains_xy, from_wkb

ROOT = Path(__file__).resolve().parents[2]
BOUNDARIES = ROOT / "data/raw/boundaries/idn_adm2.gpkg"
GRID = ROOT / "data/raw/boundaries/chirps_grid_province34.npz"
AREA = ROOT / "data/raw/bps/kab_area_weights.csv"
OUT = ROOT / "data/interim/w_kab_pixel.npz"
MIN_CELLS = 5  # match H1-03: kabs with <5 cell centres use the nearest-9 fallback


def gpkg_geometry(blob: bytes):
    """Strip the GeoPackage geometry header and parse the WKB payload."""
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob")
    flags = blob[3]
    envelope = (flags >> 1) & 0x07
    envelope_bytes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[envelope]
    return from_wkb(blob[8 + envelope_bytes:])


def main() -> None:
    grid = np.load(GRID, allow_pickle=True)
    lat = np.asarray(grid["lat"], dtype=np.float64)
    lon = np.asarray(grid["lon"], dtype=np.float64)
    nrow, ncol = len(lat), len(lon)

    area = pd.read_csv(AREA, dtype={"kab_code": str, "prov_code": str})
    kab_codes = area["kab_code"].tolist()
    kab_index = {code: i for i, code in enumerate(kab_codes)}

    connection = sqlite3.connect(BOUNDARIES)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT kab_code, kab_name, prov_code, geom, n_cells, area_method FROM adm2"
    ).fetchall()
    connection.close()

    shapes = {}
    for row in rows:
        shapes[str(row["kab_code"])] = gpkg_geometry(row["geom"])

    missing = [code for code in kab_codes if code not in shapes]
    if missing:
        raise SystemExit(f"missing geometries for {len(missing)} kab: {missing[:5]}")

    indptr = [0]
    indices: list[int] = []
    data: list[float] = []
    counts: list[int] = []
    methods: list[str] = []

    for code in kab_codes:
        geom = shapes[code]
        minx, miny, maxx, maxy = geom.bounds
        lon_idx = np.where((lon >= minx - 0.03) & (lon <= maxx + 0.03))[0]
        lat_idx = np.where((lat >= miny - 0.03) & (lat <= maxy + 0.03))[0]
        cells: list[int] = []

        if len(lon_idx) and len(lat_idx):
            xx, yy = np.meshgrid(lon[lon_idx], lat[lat_idx])
            mask = contains_xy(geom, xx, yy)
            if mask.any():
                rr, cc = np.where(mask)
                cells = (lat_idx[rr] * ncol + lon_idx[cc]).tolist()

        if len(cells) >= MIN_CELLS:
            method = "cells"
            weights = np.full(len(cells), 1.0 / len(cells), dtype=np.float64)
        else:
            point = geom.representative_point()
            # nearest 9 cell centres in degree space (small kabs only)
            d2 = (lon[None, :] - point.x) ** 2 + (lat[:, None] - point.y) ** 2
            flat = np.argpartition(d2.ravel(), 9)[:9]
            cells = flat.tolist()
            method = "nearest_9"
            weights = np.full(9, 1.0 / 9.0, dtype=np.float64)

        indices.extend(cells)
        data.extend(weights.tolist())
        counts.append(len(cells))
        methods.append(method)
        indptr.append(len(indices))

    matrix = sparse.csr_matrix(
        (np.asarray(data, dtype=np.float64), np.asarray(indices, dtype=np.int64), np.asarray(indptr, dtype=np.int64)),
        shape=(len(kab_codes), nrow * ncol),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT,
        data=matrix.data.astype(np.float32),
        indices=matrix.indices.astype(np.int32),
        indptr=matrix.indptr.astype(np.int64),
        shape=np.array(matrix.shape, dtype=np.int64),
        kab_code=np.array(kab_codes, dtype="U8"),
        kab_name=area["kab_name"].to_numpy(dtype="U64"),
        prov_code=area["prov_code"].astype(str).to_numpy(dtype="U2"),
        lat=lat.astype(np.float32),
        lon=lon.astype(np.float32),
        counts=np.asarray(counts, dtype=np.int32),
        area_method=np.array(methods, dtype="U10"),
    )

    total_cells = int(np.sum(counts))
    print(f"kab rows: {matrix.shape[0]}, pixels: {matrix.shape[1]}, nonzeros: {matrix.nnz}")
    print(f"total cell assignments: {total_cells} (H1 package: {int(area.n_cells.sum())})")
    diff = np.abs(np.asarray(counts) - area.n_cells.to_numpy())
    print(f"kab with count mismatch: {int((diff > 0).sum())}, max diff: {int(diff.max())}")
    print(f"nearest_9 rows: {methods.count('nearest_9')} (H1 package: {(area.area_method == 'nearest_9').sum()})")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
