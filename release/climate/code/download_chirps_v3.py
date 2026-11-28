#!/usr/bin/env python3
"""
download_chirps_v3.py
=====================

Download CHIRPS v3.0 DAILY rainfall and clip it to a bounding box
(default: Indonesia, lon 94.0..141.5, lat -11.5..6.5).

What the CHC catalogue looked like when this was written (2026-11-23)
---------------------------------------------------------------------
https://data.chc.ucsb.edu/products/CHIRPS/v3.0/ contains:
    2-monthly/ 3-monthly/ 4-monthly/ 5-monthly/ 6-monthly/ annual/
    daily/ dekads/ diagnostics/ monthly/ pentads/ prelim/
    README-CHIRPSv3.0.txt  recentfiles.txt

daily/ has two branches:
    daily/final/   -> sat/ and rnl/  (+ cogs/, netcdf/, p25/ inside each)
    daily/prelim/  -> sat/ only

Variants:
    final/sat   daily disaggregation with NASA IMERG Late v07, 1998-present
    final/rnl   daily disaggregation with ECMWF ERA5 reanalysis, 1981-present
    prelim/sat  preliminary product, IMERG-based, 2025-present

Daily GeoTIFF naming:
    final/sat    daily/final/sat/YYYY/chirps-v3.0.sat.YYYY.MM.DD.tif
    final/rnl    daily/final/rnl/YYYY/chirps-v3.0.rnl.YYYY.MM.DD.tif
    prelim/sat   daily/prelim/sat/YYYY/chirps-v3.0.prelim.YYYY.MM.DD.tif
Each global file is ~10-14 MiB (LZW, float32, 7200 x 2400, 0.05 deg).

Yearly NetCDF *does* exist, but it is huge:
    daily/final/sat/netcdf/byYear/chirps-v3.0.sat.YYYY.days_p05.nc   ~3.1-3.4 GiB
    daily/final/rnl/netcdf/byYear/chirps-v3.0.rnl.YYYY.days_p05.nc   ~3.6-4.6 GiB
    daily/prelim/sat/netcdf/byYear/chirps-v3.0_prelim.sat.YYYY.days_p05.nc ~2.8 GiB
There is also byMonth/ for final/sat (~200-350 MiB per month).  For a small
date range the daily GeoTIFFs are much cheaper, so "auto" only picks the yearly
NetCDF when xarray + netCDF4/h5netcdf are installed AND the estimated file size
is below --max-netcdf-gb (default 2.0 GiB, i.e. yearly files are skipped).
Use --source netcdf to force the yearly file.

Sources
-------
--source cog (DEFAULT)
    Indonesia-only subset of the tiled CHIRPS v3.0 GeoTIFF COGs.  For every
    date the script reads the TIFF IFD with HTTP Range requests and fetches
    ONLY the 512x512 tiles that overlap the bbox (3 tiles for Indonesia:
    rows 1070..1429, cols 5480..6429, tiles r=2 c=10..12).  A typical day
    transfers ~0.79 MiB instead of the ~17 MiB global COG.  LZW is decoded in
    pure Python; no GDAL/rasterio is needed.
        daily/final/sat/cogs/YYYY/      preferred, when the date exists
        daily/prelim/sat/...            fallback for dates not yet final
    The preliminary branch is discovered by listing.  If prelim COGs do not
    exist (they do not as of 2026-11), the full ~12 MiB prelim .tif is
    downloaded in memory for those dates only.  No global raster is written
    to disk in cog mode.

--source tif / netcdf / auto
    The original full-file download paths, kept unchanged for compatibility.
    These still use the on-disk global cache (and --keep-global).

Output
------
cog mode: one compressed NPZ per calendar month:
    data/raw/chirps_v3/chirps_v3_idn_YYYY-MM.npz
Keys: lat, lon, time (datetime64[D]), precip (time, lat, lon, float32,
mm/day, NaN = missing), variant (one string per day: "final/sat",
"prelim/sat").  The grid is the 360 x 950 Indonesia bbox grid: lat
6.475..-11.475, lon 94.025..141.475, 0.05 deg.  Months are resume-safe:
a complete month is skipped; a partial month only re-fetches missing days.
manifest.csv has: date, variant, url, bytes_transferred, status.

legacy tif/netcdf mode: one file per year:
    chirps_v3_final_sat_2022_idn.npz       (when xarray is absent)
    chirps_v3_final_sat_2022_idn.nc        (xarray + netcdf4/h5netcdf)
The .npz contains lat, lon, time (datetime64[D]) and precip (time, lat, lon,
float32, mm/day, NaN = missing).  A manifest.csv in the output directory
records every date: date, source_url, status, bytes, sha256.

Examples
--------
    # Default: COG range requests, monthly NPZ, Indonesia bbox (2018->latest):
    python scripts/download_chirps_v3.py --start 2018-01-01 --end 2026-11-20

    # COG smoke test into a scratch directory:
    python scripts/download_chirps_v3.py \
        --start 2022-01-01 --end 2022-01-02 \
        --out scripts/_cog_test/out

    # Legacy full-tif path, reanalysis-based variant, keep global tifs:
    python scripts/download_chirps_v3.py --source tif --start 2022-01-01 \
        --end 2022-12-31 --variant final/rnl --keep-global

Notes
-----
* GeoTIFF georeferencing is read from the TIFF tags (33550 ModelPixelScale,
  33922 ModelTiepoint, 34735 GeoKeyDirectory, 42113 GDAL_NODATA).  The CHIRPS
  v3.0 grid is 0.05 deg, lon -180..180, lat 60..-60 (2400 rows, not the 2000
  rows of v2.0).  The known grid is only a fallback if tags are missing.
* Bbox clipping keeps grid-cell centres inside the requested bbox, so the
  resulting extent can be up to half a pixel (0.025 deg) inside the bbox.
* CHIRPS daily values are disaggregated pentads, not independent daily
  observations.  See daily/readme.txt from CHC.
* In cog mode the needed Indonesia tiles are consecutive in the COG, so they
  are fetched in one HTTP range request (3 tiles, ~0.79 MiB/day).  Directory
  listings are cached once per year.  HTTP 429/5xx responses use exponential
  backoff and temporarily raise the shared polite request delay.
* Only files downloaded by the legacy tif/netcdf paths are deleted after
  clipping.  A pre-seeded cache file is left alone.  Use --keep-global to keep
  downloads.  Cog mode never writes a global raster to disk.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.metadata as importlib_metadata
import importlib.util
import io
import json
import math
import os
import random
import re
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import numpy as np

try:
    import requests
except ImportError:  # pragma: no cover
    print("ERROR: requests is required (pip install requests)", file=sys.stderr)
    raise SystemExit(2)


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"

# lon_min, lat_min, lon_max, lat_max
DEFAULT_BBOX = (94.0, -11.5, 141.5, 6.5)
GRID_LON_MIN, GRID_LON_MAX = -180.0, 180.0
GRID_LAT_MIN, GRID_LAT_MAX = -60.0, 60.0   # CHIRPS v3.0 is 60N..60S
CHIRPS_RES = 0.05
CHIRPS_NX, CHIRPS_NY = 7200, 2400

USER_AGENT = "renaro-chirps-v3-downloader/1.0 (+https://data.chc.ucsb.edu/)"

MANIFEST_FIELDS = ["date", "source_url", "status", "bytes", "sha256"]
COG_MANIFEST_FIELDS = ["date", "variant", "url", "bytes_transferred", "status"]

# ---- COG (--source cog) --------------------------------------------------
# The verified grid in scripts/_cog_test/cog_subset_test.py.  CHIRPS stores
# 0.05 as a float32, i.e. 0.05000000074505806; using that exact value
# reproduces the reference NPZ lat/lon bit-for-bit.
COG_ORIGIN_X = -180.0
COG_ORIGIN_Y = 60.0
COG_PIXEL = float(np.float32(CHIRPS_RES))
COG_TILE_SIZE = 512
COG_NX, COG_NY = CHIRPS_NX, CHIRPS_NY
COG_NODATA = np.float32(-9999.0)
COG_HEADER_BYTES = 65536

# final/sat/cogs/YYYY/ -> chirps-v3.0.sat.YYYY.MM.DD.cog
# prelim/sat/cogs/YYYY/ -> (not present as of 2026-11)
# prelim/sat/YYYY/     -> chirps-v3.0.prelim.YYYY.MM.DD.tif
COG_FINAL_DIR = f"{BASE_URL}/final/sat/cogs"
COG_PRELIM_DIR = f"{BASE_URL}/prelim/sat"

# Tile 512x512 float32.  Predictor 1 (none); compression 5 (LZW).
TIFF_TAG_NAMES = {
    256: "ImageWidth", 257: "ImageLength", 258: "BitsPerSample",
    259: "Compression", 262: "PhotometricInterpretation", 277: "SamplesPerPixel",
    284: "PlanarConfiguration", 317: "Predictor", 322: "TileWidth",
    323: "TileLength", 324: "TileOffsets", 325: "TileByteCounts",
    339: "SampleFormat", 33550: "ModelPixelScale", 33922: "ModelTiepoint",
    34735: "GeoKeyDirectory", 34736: "GeoDoubleParams", 34737: "GeoAsciiParams",
    42112: "GDAL_METADATA", 42113: "GDAL_NODATA",
}
TIFF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4,
                  10: 8, 11: 4, 12: 8}
TIFF_TYPE_FMT = {1: "B", 3: "H", 4: "I", 6: "b", 7: "B", 8: "h", 9: "i",
                 11: "f", 12: "d"}
TIFF_COMPRESSION = {1: "none", 5: "LZW", 8: "Deflate", 32946: "Deflate",
                    50000: "ZSTD"}
TIFF_SAMPLEFORMAT = {1: "uint", 2: "int", 3: "IEEE float"}


@dataclass(frozen=True)
class VariantInfo:
    folder: str          # "final" or "prelim"
    sub: str             # "sat" or "rnl"
    min_year: int
    nc_est_gb: float
    label: str


VARIANTS = {
    "final/sat": VariantInfo("final", "sat", 1998, 3.2, "final, IMERG disaggregation"),
    "final/rnl": VariantInfo("final", "rnl", 1981, 4.0, "final, ERA5 disaggregation"),
    "prelim/sat": VariantInfo("prelim", "sat", 2025, 2.9, "preliminary, IMERG disaggregation"),
}

VARIANT_ALIASES = {
    "sat": "final/sat",
    "rnl": "final/rnl",
    "final": "final/sat",
    "prelim": "prelim/sat",
    "final_sat": "final/sat",
    "final-rnl": "final/rnl",
    "prelim-sat": "prelim/sat",
}

LIBRARY_NAMES = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("requests", "requests"),
    ("rasterio", "rasterio"),
    ("tifffile", "tifffile"),
    ("pillow", "Pillow"),
    ("xarray", "xarray"),
    ("netCDF4", "netCDF4"),
    ("h5netcdf", "h5netcdf"),
]


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def log(message: str) -> None:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def die(message: str):
    print(f"ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(2)


def mib(n: float) -> str:
    return f"{n / (1024.0 * 1024.0):.1f} MiB"


def parse_date(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}, expected YYYY-MM-DD")


def date_range(start: dt.date, end: dt.date):
    day = start
    while day <= end:
        yield day
        day += dt.timedelta(days=1)


def normalise_variant(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = VARIANT_ALIASES.get(cleaned, cleaned)
    if cleaned not in VARIANTS:
        die(f"unknown --variant {value!r}; use one of "
            f"{', '.join(VARIANTS)} (aliases: sat, rnl, prelim)")
    return cleaned


def validate_bbox(bbox) -> None:
    lon_min, lat_min, lon_max, lat_max = bbox
    if not all(math.isfinite(v) for v in bbox):
        die("--bbox values must be finite numbers")
    if not (-180.0 <= lon_min < lon_max <= 180.0):
        die("--bbox longitudes must satisfy -180 <= lon_min < lon_max <= 180")
    if not (GRID_LAT_MIN <= lat_min < lat_max <= GRID_LAT_MAX):
        die(f"CHIRPS v3.0 covers lat {GRID_LAT_MIN:.0f}..{GRID_LAT_MAX:.0f}; "
            "--bbox latitudes are outside that range")


@dataclass(frozen=True)
class TargetGrid:
    """The bbox pixel window and cell-centre coordinates of the COG grid."""
    lat: np.ndarray
    lon: np.ndarray
    c0: int
    c1: int
    r0: int
    r1: int

    @property
    def shape(self):
        return (self.r1 - self.r0, self.c1 - self.c0)


def target_grid(bbox) -> TargetGrid:
    """Return exactly the grid used by scripts/_cog_test/cog_subset_test.py.

    First/last pixel whose *centre* falls inside the bbox, using the CHIRPS
    float32 pixel size.  For the default Indonesia bbox this is 360 x 950,
    lat 6.475..-11.475, lon 94.025..141.475.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    c0 = math.ceil((lon_min - COG_ORIGIN_X) / COG_PIXEL - 0.5 - 1e-6)
    c1 = math.floor((lon_max - COG_ORIGIN_X) / COG_PIXEL - 0.5 + 1e-6) + 1
    r0 = math.ceil((COG_ORIGIN_Y - lat_max) / COG_PIXEL - 0.5 - 1e-6)
    r1 = math.floor((COG_ORIGIN_Y - lat_min) / COG_PIXEL - 0.5 + 1e-6) + 1
    if c1 <= c0 or r1 <= r0:
        die("--bbox does not contain any CHIRPS grid-cell centre")
    cols = np.arange(c0, c1, dtype=np.float64)
    rows = np.arange(r0, r1, dtype=np.float64)
    lon = (COG_ORIGIN_X + (cols + 0.5) * COG_PIXEL).astype(np.float32)
    lat = (COG_ORIGIN_Y - (rows + 0.5) * COG_PIXEL).astype(np.float32)
    return TargetGrid(lat=lat, lon=lon, c0=c0, c1=c1, r0=r0, r1=r1)


def month_key(day: dt.date) -> str:
    return day.strftime("%Y-%m")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def library_report() -> str:
    present, missing = [], []
    for dist, label in LIBRARY_NAMES:
        try:
            present.append(f"{label} {importlib_metadata.version(dist)}")
        except importlib_metadata.PackageNotFoundError:
            missing.append(label)
    text = "libraries: " + ", ".join(present)
    if missing:
        text += " | missing: " + ", ".join(missing)
    return text


def netcdf_engine() -> Optional[str]:
    """Return a compression-capable xarray engine, or None.

    NetCDF3 via scipy is deliberately not accepted because it cannot compress.
    """
    try:
        import xarray as xr  # noqa: F401
    except Exception:
        return None
    try:
        engines = xr.backends.list_engines()
    except Exception:
        return None
    for engine in ("netcdf4", "h5netcdf"):
        if engine in engines:
            return engine
    return None


def tif_url(variant: str, day: dt.date) -> str:
    info = VARIANTS[variant]
    ymd = day.strftime("%Y.%m.%d")
    if info.folder == "prelim":
        name = f"chirps-v3.0.prelim.{ymd}.tif"
    else:
        name = f"chirps-v3.0.{info.sub}.{ymd}.tif"
    return f"{BASE_URL}/{info.folder}/{info.sub}/{day.year}/{name}"


def nc_year_url(variant: str, year: int) -> str:
    info = VARIANTS[variant]
    if info.folder == "prelim":
        name = f"chirps-v3.0_prelim.sat.{year}.days_p05.nc"
    else:
        name = f"chirps-v3.0.{info.sub}.{year}.days_p05.nc"
    return f"{BASE_URL}/{info.folder}/{info.sub}/netcdf/byYear/{name}"


def default_bbox(bbox) -> bool:
    return all(abs(a - b) < 1e-9 for a, b in zip(bbox, DEFAULT_BBOX))


def bbox_slug(bbox) -> str:
    if default_bbox(bbox):
        return "idn"
    lon0, lat0, lon1, lat1 = bbox
    return f"lon{lon0:.3f}_{lon1:.3f}_lat{lat0:.3f}_{lat1:.3f}"


# --------------------------------------------------------------------------
# HTTP with polite delay, retries and backoff
# --------------------------------------------------------------------------

class PermanentHTTPError(RuntimeError):
    pass


class DownloadError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, delay: float, timeout: float):
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self._last_request = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    def get(self, url: str):
        if self.delay > 0:
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()
        return self._session.get(url, stream=True, timeout=(20.0, self.timeout))


def download_file(http: HttpClient, url: str, dest: Path,
                  label: str, retries: int) -> "Fetched":
    """Download url to dest, reusing a non-empty cached file.

    The file is written to .part and atomically renamed, so a cache hit means
    a complete earlier download.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        size = dest.stat().st_size
        log(f"{label}: cache hit {dest.name} ({mib(size)})")
        return Fetched(dest, size, sha256_file(dest), downloaded=False)

    tmp = dest.with_name(dest.name + ".part")
    last_error: Optional[BaseException] = None

    for attempt in range(retries + 1):
        tmp.unlink(missing_ok=True)
        response = None
        try:
            response = http.get(url)
            if response.status_code in (404, 410):
                raise PermanentHTTPError(f"HTTP {response.status_code} for {url}")
            if response.status_code != 200:
                raise DownloadError(f"HTTP {response.status_code} for {url}")

            total = int(response.headers.get("Content-Length") or 0)
            digest = hashlib.sha256()
            received = 0
            started = time.monotonic()
            next_report = 10

            log(f"{label}: downloading {url}")
            with tmp.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if total:
                        pct = int(received * 100 / total)
                        if pct >= next_report:
                            log(f"{label}: {pct}% ({mib(received)}/{mib(total)})")
                            next_report = pct - (pct % 10) + 10

            if total and received != total:
                raise DownloadError(
                    f"truncated download: got {received} of {total} bytes"
                )
            if received == 0:
                raise DownloadError("empty response body")

            os.replace(tmp, dest)
            elapsed = max(1e-6, time.monotonic() - started)
            log(f"{label}: saved {dest.name} ({mib(received)} in {elapsed:.1f}s, "
                f"{received / elapsed / (1024 * 1024):.2f} MiB/s)")
            return Fetched(dest, received, digest.hexdigest(), downloaded=True)

        except PermanentHTTPError:
            tmp.unlink(missing_ok=True)
            raise
        except (requests.RequestException, DownloadError, OSError) as exc:
            last_error = exc
            tmp.unlink(missing_ok=True)
            if attempt >= retries:
                break
            wait = min(60.0, 2.0 * (2 ** attempt)) + random.uniform(0.0, 0.5)
            log(f"{label}: attempt {attempt + 1}/{retries + 1} failed ({exc}); "
                f"retry in {wait:.1f}s")
            time.sleep(wait)
        finally:
            if response is not None:
                response.close()

    raise DownloadError(f"failed after {retries + 1} attempts: {last_error}")


@dataclass
class Fetched:
    path: Path
    size: int
    sha256: str
    downloaded: bool


# --------------------------------------------------------------------------
# GeoTIFF decoding (rasterio -> tifffile -> Pillow)
# --------------------------------------------------------------------------

@dataclass
class Grid:
    lon0: float          # georeferenced position of the first raster point
    lat0: float
    dx: float            # degrees per column
    dy: float            # signed degrees per row (negative for north-up)
    pixel_is_point: bool
    nodata: Optional[float]
    backend: str


_TIFF_BACKEND: Optional[str] = None
_TIFF_BACKENDS = ("rasterio", "tifffile", "Pillow")


def detect_tiff_backend() -> str:
    for name, module in (("rasterio", "rasterio"),
                         ("tifffile", "tifffile"),
                         ("Pillow", "PIL")):
        try:
            if importlib.util.find_spec(module) is not None:
                return name
        except (ImportError, ValueError):
            continue
    die("no GeoTIFF decoder available; install rasterio, tifffile or Pillow")


def _parse_nodata(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("ascii", "ignore")
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    text = str(value).strip().strip("\x00")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _geokey_value(keys, key_id: int) -> Optional[int]:
    """Read one GeoKey from a GeoKeyDirectoryTag flat tuple."""
    if not keys or len(keys) < 4:
        return None
    count = int(keys[3])
    for index in range(count):
        base = 4 + 4 * index
        if base + 3 >= len(keys):
            break
        if int(keys[base]) == key_id:
            return int(keys[base + 3])
    return None


def _grid_from_tags(scale, tiepoint, keys, nodata, arr_shape, backend) -> Grid:
    if scale and tiepoint and len(scale) >= 2 and len(tiepoint) >= 6:
        dx = float(scale[0])
        sy = float(scale[1])
        dy = -sy if sy > 0 else sy
        lon0 = float(tiepoint[3])
        lat0 = float(tiepoint[4])
        raster_type = _geokey_value(keys, 1025)  # GTRasterTypeGeoKey
        pixel_is_point = raster_type == 2
        if dx == 0 or dy == 0:
            raise RuntimeError("degenerate GeoTIFF pixel scale")
        return Grid(lon0, lat0, dx, dy, pixel_is_point,
                    _parse_nodata(nodata), backend)

    # Fallback: known CHIRPS v3.0 global grid.  Only valid for the exact shape.
    ny, nx = arr_shape
    if (nx, ny) != (CHIRPS_NX, CHIRPS_NY):
        raise RuntimeError(
            f"GeoTIFF is missing georeferencing tags and shape {nx}x{ny} "
            f"does not match the CHIRPS v3.0 grid {CHIRPS_NX}x{CHIRPS_NY}"
        )
    log("WARNING: GeoTIFF has no georeferencing tags; using known CHIRPS v3.0 "
        "grid (-180..180, 60..-60, 0.05 deg)")
    return Grid(-180.0, 60.0, CHIRPS_RES, -CHIRPS_RES, False,
                _parse_nodata(nodata), backend + "+chirps-grid")


def _decode_rasterio(path: Path):
    import rasterio

    with rasterio.open(path) as ds:
        arr = ds.read(1, masked=False)
        transform = ds.transform
        tags = ds.tags()
        nodata = ds.nodata
        if nodata is None:
            nodata = tags.get("GDAL_NODATA") or tags.get("_FillValue")
        xml = tags.get("TIFFTAG_GDAL_METADATA", "")
        if nodata is None and xml:
            match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
            if match:
                nodata = match.group(1)

        grid = Grid(
            lon0=float(transform.c),
            lat0=float(transform.f),
            dx=float(transform.a),
            dy=float(transform.e),
            pixel_is_point=False,  # GDAL's transform already follows its convention
            nodata=_parse_nodata(nodata),
            backend="rasterio",
        )
        if grid.dx == 0 or grid.dy == 0:
            raise RuntimeError("degenerate rasterio transform")
        return np.asarray(arr), grid


def _decode_tifffile(path: Path):
    import tifffile

    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        arr = page.asarray()

        def tag_value(name):
            tag = page.tags.get(name)
            return tag.value if tag is not None else None

        scale = tag_value("ModelPixelScaleTag")
        tiepoint = tag_value("ModelTiepointTag")
        keys = tag_value("GeoKeyDirectoryTag")
        nodata = tag_value("GDAL_NODATA")
        xml = tag_value("GDAL_METADATA")
        if nodata is None and isinstance(xml, str):
            match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
            if match:
                nodata = match.group(1)

    return np.asarray(arr), _grid_from_tags(
        scale, tiepoint, keys, nodata, np.asarray(arr).shape, "tifffile"
    )


def _decode_pillow(path: Path):
    from PIL import Image

    with Image.open(path) as image:
        arr = np.asarray(image)
        tags = image.tag_v2
        scale = tags.get(33550)
        tiepoint = tags.get(33922)
        keys = tags.get(34735)
        nodata = tags.get(42113)
        xml = tags.get(42112)
        if nodata is None and isinstance(xml, str):
            match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
            if match:
                nodata = match.group(1)

    return np.asarray(arr), _grid_from_tags(
        scale, tiepoint, keys, nodata, np.asarray(arr).shape, "Pillow"
    )


def decode_tiff(path: Path):
    """Return (array, Grid), trying the available backends in order."""
    global _TIFF_BACKEND
    order = ((_TIFF_BACKEND,) if _TIFF_BACKEND else ()) + tuple(
        b for b in _TIFF_BACKENDS if b != _TIFF_BACKEND
    )
    errors = []
    for backend in order:
        try:
            if backend == "rasterio":
                arr, grid = _decode_rasterio(path)
            elif backend == "tifffile":
                arr, grid = _decode_tifffile(path)
            else:
                arr, grid = _decode_pillow(path)
            arr = np.asarray(arr)
            if arr.ndim == 3 and arr.shape[0] == 1:
                arr = arr[0]
            if arr.ndim != 2:
                raise RuntimeError(f"expected a 2-D raster, got shape {arr.shape}")
            _TIFF_BACKEND = backend
            return arr, grid
        except Exception as exc:  # try the next backend
            errors.append(f"{backend}: {exc}")
    raise RuntimeError("could not decode GeoTIFF (" + "; ".join(errors) + ")")


def clip_array(arr, grid: Grid, bbox, verbose: bool = False):
    """Clip a decoded global CHIRPS raster to the bbox grid."""
    arr = np.asarray(arr)
    ny, nx = arr.shape

    cols = np.arange(nx, dtype=np.float64)
    rows = np.arange(ny, dtype=np.float64)
    if grid.pixel_is_point:
        lon = grid.lon0 + cols * grid.dx
        lat = grid.lat0 + rows * grid.dy
    else:
        lon = grid.lon0 + (cols + 0.5) * grid.dx
        lat = grid.lat0 + (rows + 0.5) * grid.dy

    # Normalise to north-up / east-up regardless of storage order.
    if lat.size > 1 and lat[0] < lat[-1]:
        arr = arr[::-1, :]
        lat = lat[::-1]
    if lon.size > 1 and lon[0] > lon[-1]:
        arr = arr[:, ::-1]
        lon = lon[::-1]

    if verbose:
        log(f"  grid: {nx}x{ny}, dx={grid.dx:.6f}, lat[0]={lat[0]:.3f}, "
            f"lat[-1]={lat[-1]:.3f}, nodata={grid.nodata}, "
            f"pixel={'point' if grid.pixel_is_point else 'area'}, "
            f"backend={grid.backend}")

    lon_min, lat_min, lon_max, lat_max = bbox
    ix = np.flatnonzero((lon >= lon_min) & (lon <= lon_max))
    iy = np.flatnonzero((lat >= lat_min) & (lat <= lat_max))
    if ix.size == 0 or iy.size == 0:
        raise RuntimeError("bbox does not overlap the GeoTIFF grid")

    sub = np.asarray(arr[np.ix_(iy, ix)], dtype=np.float32)
    mask = ~np.isfinite(sub)
    if grid.nodata is not None:
        mask |= (sub == np.float32(grid.nodata))
    # CHIRPS uses -9999 for missing; also catch it when the tag is absent.
    mask |= (sub <= -1000.0)
    if mask.any():
        sub = sub.copy()
        sub[mask] = np.nan

    lat_out = np.ascontiguousarray(lat[iy], dtype=np.float32)
    lon_out = np.ascontiguousarray(lon[ix], dtype=np.float32)
    return sub, lat_out, lon_out, grid


def clip_geotiff(path: Path, bbox, verbose: bool = False):
    """Decode a global CHIRPS GeoTIFF and return precip/lat/lon for the bbox."""
    arr, grid = decode_tiff(path)
    return clip_array(arr, grid, bbox, verbose=verbose)


# ---- in-memory decoding for the preliminary .tif fallback -----------------

def _decode_rasterio_bytes(blob: bytes):
    from rasterio.io import MemoryFile

    with MemoryFile(blob) as mem:
        with mem.open() as ds:
            arr = ds.read(1, masked=False)
            transform = ds.transform
            tags = ds.tags()
            nodata = ds.nodata
            if nodata is None:
                nodata = tags.get("GDAL_NODATA") or tags.get("_FillValue")
            xml = tags.get("TIFFTAG_GDAL_METADATA", "")
            if nodata is None and xml:
                match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
                if match:
                    nodata = match.group(1)
            grid = Grid(
                lon0=float(transform.c),
                lat0=float(transform.f),
                dx=float(transform.a),
                dy=float(transform.e),
                pixel_is_point=False,
                nodata=_parse_nodata(nodata),
                backend="rasterio-memory",
            )
    if grid.dx == 0 or grid.dy == 0:
        raise RuntimeError("degenerate rasterio transform")
    return np.asarray(arr), grid


def _decode_tifffile_bytes(blob: bytes):
    import tifffile

    with tifffile.TiffFile(io.BytesIO(blob)) as tif:
        page = tif.pages[0]
        arr = page.asarray()

        def tag_value(name):
            tag = page.tags.get(name)
            return tag.value if tag is not None else None

        scale = tag_value("ModelPixelScaleTag")
        tiepoint = tag_value("ModelTiepointTag")
        keys = tag_value("GeoKeyDirectoryTag")
        nodata = tag_value("GDAL_NODATA")
        xml = tag_value("GDAL_METADATA")
        if nodata is None and isinstance(xml, str):
            match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
            if match:
                nodata = match.group(1)

    return np.asarray(arr), _grid_from_tags(
        scale, tiepoint, keys, nodata, np.asarray(arr).shape, "tifffile-memory"
    )


def _decode_pillow_bytes(blob: bytes):
    from PIL import Image

    with Image.open(io.BytesIO(blob)) as image:
        arr = np.asarray(image)
        tags = image.tag_v2
        scale = tags.get(33550)
        tiepoint = tags.get(33922)
        keys = tags.get(34735)
        nodata = tags.get(42113)
        xml = tags.get(42112)
        if nodata is None and isinstance(xml, str):
            match = re.search(r'name="_FillValue"[^>]*>([^<]+)<', xml)
            if match:
                nodata = match.group(1)

    return np.asarray(arr), _grid_from_tags(
        scale, tiepoint, keys, nodata, np.asarray(arr).shape, "Pillow-memory"
    )


def decode_tiff_bytes(blob: bytes):
    """Decode an in-memory GeoTIFF, trying rasterio -> tifffile -> Pillow."""
    global _TIFF_BACKEND
    order = ((_TIFF_BACKEND,) if _TIFF_BACKEND else ()) + tuple(
        b for b in _TIFF_BACKENDS if b != _TIFF_BACKEND
    )
    errors = []
    for backend in order:
        try:
            if backend == "rasterio":
                arr, grid = _decode_rasterio_bytes(blob)
            elif backend == "tifffile":
                arr, grid = _decode_tifffile_bytes(blob)
            else:
                arr, grid = _decode_pillow_bytes(blob)
            arr = np.asarray(arr)
            if arr.ndim == 3 and arr.shape[0] == 1:
                arr = arr[0]
            if arr.ndim != 2:
                raise RuntimeError(f"expected a 2-D raster, got shape {arr.shape}")
            _TIFF_BACKEND = backend
            return arr, grid
        except Exception as exc:  # try the next backend
            errors.append(f"{backend}: {exc}")
    raise RuntimeError("could not decode in-memory GeoTIFF ("
                       + "; ".join(errors) + ")")


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.rows: dict[tuple[str, str], dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    date = (row.get("date") or "").strip()
                    url = (row.get("source_url") or row.get("url") or "").strip()
                    if not date:
                        continue
                    try:
                        size = int(float(row.get("bytes")
                                         or row.get("bytes_transferred") or 0))
                    except ValueError:
                        size = 0
                    self.rows[(date, url)] = {
                        "date": date,
                        "source_url": url,
                        "status": (row.get("status") or "").strip(),
                        "bytes": size,
                        "sha256": (row.get("sha256") or "").strip(),
                    }
        except Exception as exc:
            log(f"WARNING: could not read manifest {self.path}: {exc}; "
                "starting a new in-memory manifest")

    def record(self, day: dt.date, url: str, status: str,
               size: int = 0, sha256: str = "") -> None:
        key = (day.isoformat(), url)
        previous = self.rows.get(key)
        # Never downgrade a successful provenance record to "skipped".
        if previous and previous["status"] == "ok" and status == "skipped":
            return
        self.rows[key] = {
            "date": day.isoformat(),
            "source_url": url,
            "status": status,
            "bytes": int(size or 0),
            "sha256": sha256 or "",
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        ordered = sorted(self.rows.values(),
                         key=lambda r: (r["date"], r["source_url"]))
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(ordered)
        os.replace(tmp, self.path)


# --------------------------------------------------------------------------
# Yearly output files
# --------------------------------------------------------------------------

@dataclass
class YearData:
    dates: list[dt.date]
    lat: np.ndarray
    lon: np.ndarray
    cube: np.ndarray


def read_year_file(path: Path, fmt: str, engine: Optional[str]) -> YearData:
    if fmt == "npz":
        with np.load(path, allow_pickle=False) as npz:
            lat = np.asarray(npz["lat"], dtype=np.float32)
            lon = np.asarray(npz["lon"], dtype=np.float32)
            cube = np.asarray(npz["precip"], dtype=np.float32)
            times = np.asarray(npz["time"])
        dates = [dt.date.fromisoformat(str(t)[:10]) for t in times]
        return YearData(dates, lat, lon, cube)

    import xarray as xr

    with xr.open_dataset(path, engine=engine) as ds:
        if "precip" in ds.data_vars:
            var = "precip"
        else:
            candidates = [v for v in ds.data_vars
                          if {"time", "lat", "lon"}.issubset(ds[v].dims)]
            if not candidates:
                raise RuntimeError(f"no time/lat/lon precipitation variable in {path}")
            var = candidates[0]
        cube = np.asarray(ds[var].values, dtype=np.float32)
        lat = np.asarray(ds["lat"].values, dtype=np.float32)
        lon = np.asarray(ds["lon"].values, dtype=np.float32)
        dates = [dt.date.fromisoformat(str(t)[:10]) for t in ds["time"].values]
    return YearData(dates, lat, lon, cube)


def write_year_file(path: Path, data: YearData, fmt: str,
                    engine: Optional[str], variant: str, bbox) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        if fmt == "npz":
            meta = {
                "title": "CHIRPS v3.0 daily precipitation, bbox subset",
                "source": "CHIRPS v3.0, Climate Hazards Center, UC Santa Barbara",
                "variant": variant,
                "bbox": [float(v) for v in bbox],
                "units": "mm/day",
                "note": "NaN = missing/nodata (original nodata -9999)",
            }
            with tmp.open("wb") as fh:
                np.savez_compressed(
                    fh,
                    lat=np.ascontiguousarray(data.lat, dtype=np.float32),
                    lon=np.ascontiguousarray(data.lon, dtype=np.float32),
                    time=np.array([d.isoformat() for d in data.dates],
                                  dtype="datetime64[D]"),
                    precip=np.ascontiguousarray(data.cube, dtype=np.float32),
                    meta=np.array(json.dumps(meta)),
                )
        else:
            import xarray as xr

            ds = xr.Dataset(
                data_vars={
                    "precip": (("time", "lat", "lon"),
                               np.ascontiguousarray(data.cube, dtype=np.float32)),
                },
                coords={
                    "time": np.array([np.datetime64(d.isoformat())
                                      for d in data.dates]),
                    "lat": np.ascontiguousarray(data.lat, dtype=np.float32),
                    "lon": np.ascontiguousarray(data.lon, dtype=np.float32),
                },
                attrs={
                    "title": "CHIRPS v3.0 daily precipitation, bbox subset",
                    "source": "CHIRPS v3.0, Climate Hazards Center, UC Santa Barbara",
                    "variant": variant,
                    "units": "mm/day",
                    "geospatial_lon_min": float(bbox[0]),
                    "geospatial_lat_min": float(bbox[1]),
                    "geospatial_lon_max": float(bbox[2]),
                    "geospatial_lat_max": float(bbox[3]),
                    "history": (f"{dt.datetime.now().isoformat(timespec='seconds')} "
                                "created by download_chirps_v3.py"),
                    "comment": "CHIRPS daily values are disaggregated pentads; "
                               "NaN = missing/nodata",
                },
            )
            ds["precip"].attrs.update({
                "units": "mm/day",
                "long_name": "CHIRPS v3.0 daily precipitation",
                "coordinates": "time lat lon",
            })
            ds["lat"].attrs.update({"units": "degrees_north", "axis": "Y"})
            ds["lon"].attrs.update({"units": "degrees_east", "axis": "X"})
            encoding = {"precip": {"zlib": True, "complevel": 4, "shuffle": True}}
            ds.to_netcdf(tmp, engine=engine, encoding=encoding)
            ds.close()
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def merge_year_data(existing: Optional[YearData], new_dates, new_cube,
                    lat, lon) -> YearData:
    if existing is None:
        return YearData(list(new_dates), lat, lon, new_cube)

    if existing.lat.shape != lat.shape or not np.allclose(existing.lat, lat, atol=1e-6):
        raise RuntimeError("existing output has a different latitude grid; "
                           "use a different --out directory or --overwrite")
    if existing.lon.shape != lon.shape or not np.allclose(existing.lon, lon, atol=1e-6):
        raise RuntimeError("existing output has a different longitude grid; "
                           "use a different --out directory or --overwrite")

    by_date = {d: existing.cube[index] for index, d in enumerate(existing.dates)}
    for day, cube in zip(new_dates, new_cube):
        by_date[day] = cube
    dates = sorted(by_date)
    stack = np.stack([by_date[d] for d in dates]).astype(np.float32, copy=False)
    return YearData(dates, existing.lat, existing.lon, stack)


def cube_stats(cube: np.ndarray):
    finite = np.isfinite(cube)
    valid = int(finite.sum())
    total = int(cube.size)
    if valid == 0:
        return valid, total - valid, None, None
    values = cube[finite]
    return valid, total - valid, float(values.min()), float(values.max())


# --------------------------------------------------------------------------
# Downloader
# --------------------------------------------------------------------------

class ChirpsDownloader:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.variant = self._normalise_variant(args.variant)
        self.info = VARIANTS[self.variant]
        self.bbox = tuple(float(v) for v in args.bbox)
        self._validate_bbox()
        self.out = Path(args.out).expanduser()
        self.cache = (Path(args.cache_dir).expanduser() if args.cache_dir
                      else self.out / "_cache")
        self.http = HttpClient(args.delay, args.timeout)
        self.manifest = Manifest(self.out / "manifest.csv")
        self.failures = 0

        self.engine = netcdf_engine()
        self.fmt = self._resolve_format()
        self.source = self._resolve_source()
        self.backend = (detect_tiff_backend() if self.source == "tif" else None)
        self._grid_logged = False

        self.out.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)

    # -- configuration --------------------------------------------------
    def _normalise_variant(self, value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = VARIANT_ALIASES.get(cleaned, cleaned)
        if cleaned not in VARIANTS:
            die(f"unknown --variant {value!r}; use one of "
                f"{', '.join(VARIANTS)} (aliases: sat, rnl, prelim)")
        return cleaned

    def _validate_bbox(self) -> None:
        lon_min, lat_min, lon_max, lat_max = self.bbox
        if not all(math.isfinite(v) for v in self.bbox):
            die("--bbox values must be finite numbers")
        if not (-180.0 <= lon_min < lon_max <= 180.0):
            die("--bbox longitudes must satisfy -180 <= lon_min < lon_max <= 180")
        if not (GRID_LAT_MIN <= lat_min < lat_max <= GRID_LAT_MAX):
            die(f"CHIRPS v3.0 covers lat {GRID_LAT_MIN:.0f}..{GRID_LAT_MAX:.0f}; "
                "--bbox latitudes are outside that range")

    def _resolve_format(self) -> str:
        if self.args.fmt != "auto":
            chosen = self.args.fmt
        else:
            chosen = "netcdf" if self.engine else "npz"
        if chosen == "netcdf" and not self.engine:
            die("--fmt netcdf requires xarray plus netCDF4 or h5netcdf "
                "(a compression-capable engine). Install them, or use --fmt npz.")
        return chosen

    def _resolve_source(self) -> str:
        if self.args.source == "tif":
            return "tif"
        if self.args.source == "netcdf":
            if not self.engine:
                die("--source netcdf requires xarray plus netCDF4 or h5netcdf")
            return "netcdf"

        # auto: yearly NetCDF is available, but typically 3-5 GiB/year.
        if not self.engine:
            return "tif"
        limit = self.args.max_netcdf_gb
        if limit and limit > 0 and self.info.nc_est_gb > limit:
            return "tif"
        return "netcdf"

    def _source_reason(self) -> str:
        if self.args.source == "tif":
            return "forced by --source tif"
        if self.args.source == "netcdf":
            return "forced by --source netcdf"
        if not self.engine:
            return ("yearly NetCDF exists (~"
                    f"{self.info.nc_est_gb:.1f} GiB/year) but xarray/netCDF4/"
                    "h5netcdf are not installed")
        limit = self.args.max_netcdf_gb
        if limit and limit > 0 and self.info.nc_est_gb > limit:
            return (f"yearly NetCDF is ~{self.info.nc_est_gb:.1f} GiB, above "
                    f"--max-netcdf-gb {limit:g}")
        return f"yearly NetCDF below --max-netcdf-gb {limit:g}"

    # -- paths ----------------------------------------------------------
    def year_path(self, year: int) -> Path:
        slug = self.variant.replace("/", "_")
        name = (f"chirps_v3_{slug}_{year}_{bbox_slug(self.bbox)}."
                f"{'nc' if self.fmt == 'netcdf' else 'npz'}")
        return self.out / name

    def _cache_path(self, url: str) -> Path:
        return self.cache / url.rsplit("/", 1)[-1]

    # -- run ------------------------------------------------------------
    def run(self, dates: list[dt.date]) -> int:
        years = sorted({d.year for d in dates})
        log(f"variant: {self.variant} ({self.info.label}), "
            f"available from {self.info.min_year}")
        log(f"range: {dates[0]} .. {dates[-1]} ({len(dates)} day(s), "
            f"{len(years)} year file(s))")
        log(f"bbox: lon {self.bbox[0]} .. {self.bbox[2]}, "
            f"lat {self.bbox[1]} .. {self.bbox[3]}")
        log(f"out: {self.out}")
        log(f"cache: {self.cache}")
        log(f"source: {self.source} ({self._source_reason()})")
        log(f"format: {self.fmt}" + (f" (engine {self.engine})"
                                     if self.fmt == "netcdf" else ""))
        if self.backend:
            log(f"GeoTIFF decoder: {self.backend}")
        log(library_report())

        try:
            for year in years:
                requested = [d for d in dates if d.year == year]
                try:
                    if self.source == "netcdf":
                        self.failures += self._process_netcdf_year(year, requested)
                    else:
                        self.failures += self._process_tif_year(year, requested)
                except Exception as exc:
                    log(f"{year}: FAILED: {exc}")
                    self.failures += len(requested)
                    for day in requested:
                        url = (nc_year_url(self.variant, year)
                               if self.source == "netcdf"
                               else tif_url(self.variant, day))
                        self.manifest.record(day, url, "failed")
        except KeyboardInterrupt:
            log("interrupted by user")
            self.failures += 1
        finally:
            self.manifest.save()

        log(f"done: {self.failures} failed date(s); manifest: "
            f"{self.out / 'manifest.csv'}")
        return 1 if self.failures else 0

    # -- daily GeoTIFF path --------------------------------------------
    def _process_tif_year(self, year: int, dates: list[dt.date]) -> int:
        path = self.year_path(year)
        existing = None
        if path.exists() and not self.args.overwrite:
            existing = read_year_file(path, self.fmt, self.engine)
        have = set(existing.dates) if existing else set()
        missing = [d for d in dates if d not in have]

        if not missing:
            log(f"{year}: all {len(dates)} requested day(s) already in "
                f"{path.name}; skipping")
            for day in dates:
                self.manifest.record(day, tif_url(self.variant, day), "skipped")
            return 0

        log(f"{year}: {len(have)} day(s) already stored, "
            f"{len(missing)} to download")

        failures = 0
        new_dates: list[dt.date] = []
        new_cubes: list[np.ndarray] = []
        lat = lon = None

        for day in missing:
            url = tif_url(self.variant, day)
            label = day.isoformat()
            cache_path = self._cache_path(url)
            fetched: Optional[Fetched] = None
            try:
                fetched = download_file(self.http, url, cache_path, label,
                                        self.args.retries)
                subset, lat_day, lon_day, grid = clip_geotiff(
                    cache_path, self.bbox, verbose=not self._grid_logged
                )
                self._grid_logged = True
                valid, n_nan, vmin, vmax = cube_stats(subset)
                if lat is None:
                    lat, lon = lat_day, lon_day
                else:
                    if (lat.shape != lat_day.shape
                            or not np.allclose(lat, lat_day, atol=1e-6)
                            or not np.allclose(lon, lon_day, atol=1e-6)):
                        raise RuntimeError(
                            "grid changed between files; refusing to mix them"
                        )
                new_dates.append(day)
                new_cubes.append(subset)
                if vmin is None:
                    value_text = "all nodata"
                else:
                    value_text = f"{vmin:.2f}..{vmax:.2f} mm"
                log(f"{label}: ok {subset.shape[1]}x{subset.shape[0]} cells, "
                    f"valid={valid}, NaN={n_nan}, {value_text}")
                self.manifest.record(day, url, "ok",
                                     fetched.size, fetched.sha256)
            except PermanentHTTPError as exc:
                log(f"{label}: not available ({exc})")
                self.manifest.record(day, url, "failed")
                failures += 1
            except Exception as exc:
                log(f"{label}: FAILED: {exc}")
                self.manifest.record(day, url, "failed")
                failures += 1
            finally:
                # Delete only what this run downloaded, and only after clipping.
                if (fetched is not None and fetched.downloaded
                        and not self.args.keep_global):
                    try:
                        cache_path.unlink()
                    except OSError as exc:
                        log(f"WARNING: could not delete {cache_path}: {exc}")

        if not new_dates:
            if existing is None:
                log(f"{year}: no data written (all requested days failed)")
            return failures

        data = merge_year_data(existing, new_dates,
                               np.stack(new_cubes), lat, lon)
        write_year_file(path, data, self.fmt, self.engine,
                        self.variant, self.bbox)
        size = path.stat().st_size
        log(f"{year}: wrote {path.name} ({len(data.dates)} day(s), {mib(size)})")
        return failures

    # -- yearly NetCDF path --------------------------------------------
    def _process_netcdf_year(self, year: int, dates: list[dt.date]) -> int:
        import xarray as xr

        path = self.year_path(year)
        existing = None
        if path.exists() and not self.args.overwrite:
            existing = read_year_file(path, self.fmt, self.engine)
        have = set(existing.dates) if existing else set()
        missing = [d for d in dates if d not in have]
        url = nc_year_url(self.variant, year)

        if not missing:
            log(f"{year}: all {len(dates)} requested day(s) already in "
                f"{path.name}; skipping")
            for day in dates:
                self.manifest.record(day, url, "skipped")
            return 0

        log(f"{year}: yearly NetCDF is ~{self.info.nc_est_gb:.1f} GiB; "
            "downloading the whole file (use --source tif for small ranges)")
        cache_path = self._cache_path(url)
        fetched: Optional[Fetched] = None
        failures = 0
        new_dates: list[dt.date] = []
        new_cubes: list[np.ndarray] = []
        lat = lon = None

        try:
            fetched = download_file(self.http, url, cache_path, str(year),
                                    self.args.retries)
            with xr.open_dataset(cache_path, engine=self.engine) as ds:
                lat_name = "lat" if "lat" in ds.coords else "latitude"
                lon_name = "lon" if "lon" in ds.coords else "longitude"
                lat_all = np.asarray(ds[lat_name].values, dtype=np.float64)
                lon_all = np.asarray(ds[lon_name].values, dtype=np.float64)

                candidates = [v for v in ds.data_vars
                              if {lat_name, lon_name}.issubset(ds[v].dims)
                              and "time" in ds[v].dims]
                if not candidates:
                    raise RuntimeError("no time/lat/lon precipitation variable "
                                       f"in {cache_path.name}")
                preferred = [v for v in candidates
                             if v.lower() in ("precip", "precipitation", "pr")]
                var = preferred[0] if preferred else candidates[0]

                lat_min, lat_max = self.bbox[1], self.bbox[3]
                lon_min, lon_max = self.bbox[0], self.bbox[2]
                iy = np.flatnonzero((lat_all >= lat_min) & (lat_all <= lat_max))
                ix = np.flatnonzero((lon_all >= lon_min) & (lon_all <= lon_max))
                if iy.size == 0 or ix.size == 0:
                    raise RuntimeError("bbox does not overlap the NetCDF grid")

                time_index = {str(t)[:10]: i
                              for i, t in enumerate(ds["time"].values)}
                fill = ds[var].attrs.get("_FillValue",
                                         ds[var].attrs.get("missing_value"))
                fill = _parse_nodata(fill)

                for day in missing:
                    index = time_index.get(day.isoformat())
                    if index is None:
                        log(f"{day.isoformat()}: not present in {cache_path.name}")
                        self.manifest.record(day, url, "failed")
                        failures += 1
                        continue
                    subset = ds[var].isel(time=index, lat=iy, lon=ix).values
                    subset = np.asarray(subset, dtype=np.float32)
                    mask = ~np.isfinite(subset)
                    if fill is not None:
                        mask |= (subset == np.float32(fill))
                    mask |= (subset <= -1000.0)
                    if mask.any():
                        subset = subset.copy()
                        subset[mask] = np.nan

                    lat_day = np.asarray(lat_all[iy], dtype=np.float32)
                    lon_day = np.asarray(lon_all[ix], dtype=np.float32)
                    if lat is None:
                        lat, lon = lat_day, lon_day
                    new_dates.append(day)
                    new_cubes.append(subset)
                    valid, n_nan, vmin, vmax = cube_stats(subset)
                    log(f"{day.isoformat()}: ok {subset.shape[1]}x"
                        f"{subset.shape[0]} cells, valid={valid}, "
                        f"NaN={n_nan}, range={vmin:.2f}..{vmax:.2f} mm")
                    self.manifest.record(
                        day, url, "ok",
                        fetched.size if len(new_dates) == 1 else 0,
                        fetched.sha256 if len(new_dates) == 1 else "",
                    )
        except PermanentHTTPError as exc:
            log(f"{year}: not available ({exc})")
            for day in missing:
                self.manifest.record(day, url, "failed")
            failures += len(missing)
        except Exception as exc:
            log(f"{year}: FAILED: {exc}")
            for day in missing:
                self.manifest.record(day, url, "failed")
            failures += len(missing)
        finally:
            if (fetched is not None and fetched.downloaded
                    and not self.args.keep_global):
                try:
                    cache_path.unlink()
                except OSError as exc:
                    log(f"WARNING: could not delete {cache_path}: {exc}")

        if not new_dates:
            if existing is None:
                log(f"{year}: no data written")
            return failures

        data = merge_year_data(existing, new_dates,
                               np.stack(new_cubes), lat, lon)
        write_year_file(path, data, self.fmt, self.engine,
                        self.variant, self.bbox)
        log(f"{year}: wrote {path.name} ({len(data.dates)} day(s), "
            f"{mib(path.stat().st_size)})")
        return failures


# --------------------------------------------------------------------------
# COG mode (--source cog, the default)
#
# Verified against scripts/_cog_test/cog_subset_test.py:
#   * classic TIFF IFD parsed with struct from a 64 KiB header range
#   * 512x512 tiles, LZW, float32, -9999 nodata
#   * origin (-180, 60), pixel size float32(0.05)
#   * only the tiles covering the bbox are fetched (3 tiles for Indonesia)
# --------------------------------------------------------------------------

class RetryableHTTPError(DownloadError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class VariantNotFound(RuntimeError):
    pass


class RateLimiter:
    """Global, thread-safe spacing between HTTP requests (politeness)."""

    def __init__(self, delay: float):
        self.base_delay = max(0.0, delay)
        self.delay = self.base_delay
        self._lock = threading.Lock()
        self._next = 0.0
        self._successes = 0

    def wait(self) -> None:
        if self.delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self.delay
            wait_for = slot - now
        if wait_for > 0:
            time.sleep(wait_for)

    def penalize(self) -> float:
        """Slow down after HTTP 429; returns the new delay."""
        with self._lock:
            self._successes = 0
            target = max(1.0, self.delay * 2.0)
            self.delay = min(target, max(self.base_delay, 2.0))
            self._next = max(self._next, time.monotonic() + self.delay)
            return self.delay

    def note_success(self) -> None:
        """Slowly return to the requested delay after a 429 penalty."""
        with self._lock:
            if self.delay <= self.base_delay:
                return
            self._successes += 1
            if self._successes >= 50:
                self._successes = 0
                self.delay = max(self.base_delay, self.delay - 0.5)


class CogHttp:
    """HTTP range client with retries, timeouts and politeness.

    One requests.Session per thread (thread-local) so a ThreadPoolExecutor can
    fetch several days concurrently.  The rate limiter is shared by all
    threads, so the server never sees requests closer than --delay.
    """

    def __init__(self, delay: float, timeout: float, retries: int):
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.limiter = RateLimiter(delay)
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            self._local.session = session
        return session

    def _once(self, method: str, url: str, headers=None, stream: bool = False,
              allow=(200,)):
        self.limiter.wait()
        try:
            response = self._session().request(
                method, url, headers=headers, stream=stream,
                timeout=(20.0, self.timeout), allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise RetryableHTTPError(f"{method} {url}: {exc}") from exc

        status = response.status_code
        if status in (404, 410, 416):
            response.close()
            raise PermanentHTTPError(f"HTTP {status} for {url}")
        if status == 429:
            response.close()
            slow = self.limiter.penalize()
            raise RetryableHTTPError(
                f"HTTP 429 for {url} (slowing to {slow:.1f}s/request)",
                status=429,
            )
        if status in (408, 425) or 500 <= status < 600:
            response.close()
            raise RetryableHTTPError(f"HTTP {status} for {url}", status=status)
        if status not in allow:
            response.close()
            raise PermanentHTTPError(f"HTTP {status} for {url}")
        self.limiter.note_success()
        return response

    @staticmethod
    def _backoff_seconds(attempt: int, error: BaseException) -> float:
        status = getattr(error, "status", None)
        if status == 429:
            base = 10.0
        elif isinstance(status, int) and status >= 500:
            base = 2.0
        else:
            base = 1.0
        return min(120.0, base * (2 ** attempt)) + random.uniform(0.0, 0.5)

    def _retry(self, method: str, url: str, parser, headers=None,
               stream: bool = False, allow=(200,)):
        last: Optional[BaseException] = None
        for attempt in range(self.retries + 1):
            try:
                response = self._once(method, url, headers=headers,
                                      stream=stream, allow=allow)
                try:
                    return parser(response)
                finally:
                    response.close()
            except PermanentHTTPError:
                raise
            except (RetryableHTTPError, requests.RequestException, OSError) as exc:
                last = exc
                if attempt >= self.retries:
                    break
                wait = self._backoff_seconds(attempt, exc)
                log(f"retry {attempt + 1}/{self.retries} in {wait:.1f}s: {exc}")
                time.sleep(wait)
        raise DownloadError(f"{method} {url} failed after "
                            f"{self.retries + 1} attempt(s): {last}")

    def head_size(self, url: str) -> tuple[int, int]:
        """Return (file_size, bytes_received)."""
        def parse(response):
            length = response.headers.get("Content-Length")
            if length is None:
                raise RetryableHTTPError("HEAD without Content-Length")
            return int(length)

        try:
            return self._retry("HEAD", url, parse), 0
        except (PermanentHTTPError, DownloadError):
            # Some servers reject HEAD; ask for one byte and read Content-Range.
            def parse_range(response):
                content_range = response.headers.get("Content-Range", "")
                if "/" not in content_range:
                    raise RetryableHTTPError("no Content-Range for 1-byte probe")
                return int(content_range.rsplit("/", 1)[1]), len(response.content)

            return self._retry("GET", url, parse_range,
                               headers={"Range": "bytes=0-0"}, stream=False,
                               allow=(206,))

    def fetch_range(self, url: str, start: int, end: int) -> tuple[bytes, int]:
        """Fetch an inclusive byte range; returns (payload, bytes_received)."""
        headers = {"Range": f"bytes={start}-{end}"}
        last: Optional[BaseException] = None
        for attempt in range(self.retries + 1):
            response = None
            try:
                response = self._once("GET", url, headers=headers, stream=True,
                                      allow=(200, 206))
                if response.status_code == 200:
                    raise PermanentHTTPError(
                        f"server ignored Range for {url}; refusing to fetch "
                        "the whole file"
                    )
                payload = response.content
                expected = end - start + 1
                if len(payload) != expected:
                    raise RetryableHTTPError(
                        f"short range {start}-{end}: got {len(payload)} of "
                        f"{expected} bytes"
                    )
                return payload, len(payload)
            except PermanentHTTPError:
                raise
            except (RetryableHTTPError, requests.RequestException) as exc:
                last = exc
                if attempt >= self.retries:
                    break
                wait = self._backoff_seconds(attempt, exc)
                log(f"retry range {start}-{end} in {wait:.1f}s: {exc}")
                time.sleep(wait)
            finally:
                if response is not None:
                    response.close()
        raise DownloadError(f"range request {start}-{end} failed after "
                            f"{self.retries + 1} attempt(s): {last}")

    def get_text(self, url: str) -> tuple[str, int]:
        def parse(response):
            body = response.content
            return body.decode("utf-8", "replace"), len(body)

        return self._retry("GET", url, parse, stream=False, allow=(200,))

    def get_bytes(self, url: str) -> tuple[bytes, int]:
        def parse(response):
            body = response.content
            declared = response.headers.get("Content-Length")
            encoded = response.headers.get("Content-Encoding", "identity")
            if (declared and encoded in (None, "identity")
                    and len(body) != int(declared)):
                raise RetryableHTTPError(
                    f"truncated body: got {len(body)} of {declared} bytes"
                )
            if not body:
                raise RetryableHTTPError("empty response body")
            return body, len(body)

        return self._retry("GET", url, parse, stream=False, allow=(200,))


class CogRangeReader:
    """Byte-range reader for one COG, with per-file transfer accounting."""

    def __init__(self, http: CogHttp, url: str):
        self.http = http
        self.url = url
        self.size, self.head_bytes = http.head_size(url)
        if self.size <= 0:
            raise RuntimeError(f"empty remote file: {url}")
        end = min(COG_HEADER_BYTES, self.size) - 1
        self.initial, self.initial_bytes = http.fetch_range(url, 0, end)
        self.bytes = self.head_bytes + self.initial_bytes
        self.requests = 2
        self.tile_bytes = 0
        self.tile_requests = 0

    def fetch(self, start: int, end: int) -> bytes:
        if not (0 <= start <= end < self.size):
            raise RuntimeError(f"range {start}-{end} outside file size {self.size}")
        payload, received = self.http.fetch_range(self.url, start, end)
        self.bytes += received
        self.requests += 1
        self.tile_bytes += received
        self.tile_requests += 1
        return payload

    def read(self, offset: int, length: int) -> bytes:
        if offset + length <= len(self.initial):
            return self.initial[offset:offset + length]
        return self.fetch(offset, offset + length - 1)


@dataclass
class CogMetadata:
    width: int
    height: int
    tile_width: int
    tile_height: int
    compression: int
    predictor: int
    sample_format: int
    bits: int
    samples: int
    offsets: tuple
    counts: tuple
    scale: tuple
    tiepoint: tuple
    nodata: Optional[float]
    x0: float
    y0: float
    tiles_x: int
    tiles_y: int
    byte_order: str

    @property
    def sx(self) -> float:
        return float(self.scale[0])

    @property
    def sy(self) -> float:
        return float(self.scale[1])


def _parse_cog_ifd0(reader: CogRangeReader):
    buf = reader.initial
    if buf[:2] == b"II":
        byte_order = "<"
    elif buf[:2] == b"MM":
        byte_order = ">"
    else:
        raise RuntimeError("not a TIFF: bad byte-order mark")
    if len(buf) < 8:
        raise RuntimeError("truncated TIFF header")
    magic = struct.unpack_from(byte_order + "H", buf, 2)[0]
    if magic != 42:
        raise RuntimeError(f"not classic TIFF (magic={magic}); "
                           "BigTIFF is not supported")
    ifd = struct.unpack_from(byte_order + "I", buf, 4)[0]
    if ifd + 2 > len(buf):
        raise RuntimeError("TIFF IFD lies outside the initial 64 KiB range")
    count = struct.unpack_from(byte_order + "H", buf, ifd)[0]
    tags = {}
    for index in range(count):
        base = ifd + 2 + 12 * index
        if base + 12 > len(buf):
            raise RuntimeError("truncated TIFF IFD")
        tag, typ, cnt, raw = struct.unpack_from(byte_order + "HHI4s", buf, base)
        tags[tag] = (typ, cnt, raw)
    return byte_order, tags


def _cog_tag_bytes(reader: CogRangeReader, byte_order: str, tags: dict,
                   tag: int) -> bytes:
    if tag not in tags:
        raise RuntimeError(f"missing TIFF tag {tag} ({TIFF_TAG_NAMES.get(tag)})")
    typ, cnt, raw = tags[tag]
    if typ not in TIFF_TYPE_SIZE:
        raise RuntimeError(f"unsupported TIFF field type {typ} for tag {tag}")
    size = TIFF_TYPE_SIZE[typ] * cnt
    if size <= 4:
        return raw[:size]
    offset = struct.unpack(byte_order + "I", raw)[0]
    return reader.read(offset, size)


def _cog_tag_values(reader: CogRangeReader, byte_order: str, tags: dict,
                    tag: int):
    typ, cnt, _ = tags[tag]
    blob = _cog_tag_bytes(reader, byte_order, tags, tag)
    if typ == 2:
        return blob.split(b"\x00")[0].decode("latin1")
    if typ in (5, 10):
        numbers = struct.unpack(byte_order + ("I" if typ == 5 else "i")
                                * (2 * cnt), blob)
        return tuple(numbers[2 * i] / numbers[2 * i + 1] for i in range(cnt))
    fmt = TIFF_TYPE_FMT[typ]
    return struct.unpack(byte_order + fmt * cnt, blob)


def _read_cog_metadata(reader: CogRangeReader) -> CogMetadata:
    byte_order, tags = _parse_cog_ifd0(reader)

    def values(tag):
        return _cog_tag_values(reader, byte_order, tags, tag)

    width = int(values(256)[0])
    height = int(values(257)[0])
    bits = int(values(258)[0])
    compression = int(values(259)[0])
    samples = int(values(277)[0])
    predictor = int(values(317)[0]) if 317 in tags else 1
    tile_width = int(values(322)[0])
    tile_height = int(values(323)[0])
    offsets = tuple(int(v) for v in values(324))
    counts = tuple(int(v) for v in values(325))
    sample_format = int(values(339)[0])
    scale = tuple(float(v) for v in values(33550))
    tiepoint = tuple(float(v) for v in values(33922))
    nodata = _parse_nodata(values(42113)) if 42113 in tags else None

    if width != COG_NX or height != COG_NY:
        raise RuntimeError(f"unexpected COG shape {width}x{height}, "
                           f"expected {COG_NX}x{COG_NY}")
    if tile_width != COG_TILE_SIZE or tile_height != COG_TILE_SIZE:
        raise RuntimeError(f"unexpected tile shape {tile_width}x{tile_height}, "
                           f"expected {COG_TILE_SIZE}x{COG_TILE_SIZE}")
    if bits != 32 or samples != 1 or sample_format != 3:
        raise RuntimeError(
            f"unexpected sample layout bits={bits} spp={samples} "
            f"format={sample_format} ({TIFF_SAMPLEFORMAT.get(sample_format, '?')}); "
            "expected float32"
        )
    if compression not in (1, 5, 8, 32946):
        raise RuntimeError(
            f"unsupported compression {compression} "
            f"({TIFF_COMPRESSION.get(compression, '?')})"
        )
    if predictor == 3:
        raise RuntimeError("floating-point TIFF predictor (3) is not supported")
    if len(scale) < 2 or len(tiepoint) < 6:
        raise RuntimeError("COG has no usable ModelPixelScale/ModelTiepoint")
    if len(offsets) != len(counts):
        raise RuntimeError("TileOffsets and TileByteCounts differ in length")

    x0 = tiepoint[3] - tiepoint[0] * scale[0]
    y0 = tiepoint[4] + tiepoint[1] * scale[1]
    if abs(x0 - COG_ORIGIN_X) > 1e-9 or abs(y0 - COG_ORIGIN_Y) > 1e-9:
        raise RuntimeError(f"unexpected COG origin ({x0}, {y0}); "
                           f"expected ({COG_ORIGIN_X}, {COG_ORIGIN_Y})")
    if abs(scale[0] - COG_PIXEL) > 1e-12 or abs(scale[1] - COG_PIXEL) > 1e-12:
        raise RuntimeError(f"unexpected COG pixel size ({scale[0]}, {scale[1]}); "
                           f"expected {COG_PIXEL!r}")

    tiles_x = math.ceil(width / tile_width)
    tiles_y = math.ceil(height / tile_height)
    if len(offsets) != tiles_x * tiles_y:
        raise RuntimeError(f"COG has {len(offsets)} tile offsets, expected "
                           f"{tiles_x * tiles_y} ({tiles_x}x{tiles_y})")
    return CogMetadata(
        width=width, height=height, tile_width=tile_width,
        tile_height=tile_height, compression=compression,
        predictor=predictor, sample_format=sample_format, bits=bits,
        samples=samples, offsets=offsets, counts=counts, scale=scale,
        tiepoint=tiepoint, nodata=nodata, x0=x0, y0=y0,
        tiles_x=tiles_x, tiles_y=tiles_y, byte_order=byte_order,
    )


def _lzw_decode(blob: bytes, expected_size: Optional[int] = None) -> bytes:
    """TIFF LZW (MSB-first, early change).  Predictor 1 for CHIRPS COGs."""
    CLEAR, EOI = 256, 257
    out = bytearray()
    table = [bytes((i,)) for i in range(256)] + [None, None]
    width = 9
    bitpos = 0
    nbits = len(blob) * 8
    prev = None
    data = blob + b"\x00\x00\x00"

    while bitpos + width <= nbits:
        pos = bitpos >> 3
        chunk = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
        code = (chunk >> (24 - (bitpos & 7) - width)) & ((1 << width) - 1)
        bitpos += width

        if code == CLEAR:
            table = [bytes((i,)) for i in range(256)] + [None, None]
            width = 9
            prev = None
            continue
        if code == EOI:
            break
        if code < len(table) and table[code] is not None:
            entry = table[code]
        elif code == len(table) and prev is not None:
            entry = prev + prev[:1]
        else:
            raise ValueError(f"bad LZW code {code} at bit {bitpos - width}")
        out += entry
        if prev is not None and len(table) < 4096:
            table.append(prev + entry[:1])
            # TIFF "early change": widen one code before the table is full.
            if len(table) == (1 << width) - 1 and width < 12:
                width += 1
        prev = entry

    if expected_size is not None and len(out) != expected_size:
        raise ValueError(f"LZW output {len(out)} bytes != expected "
                         f"{expected_size}")
    return bytes(out)


def _decode_cog_tile(blob: bytes, meta: CogMetadata) -> np.ndarray:
    expected = meta.tile_width * meta.tile_height * 4
    if meta.compression == 5:
        raw = _lzw_decode(blob, expected_size=expected)
    elif meta.compression == 1:
        raw = blob
    elif meta.compression in (8, 32946):
        import zlib
        raw = zlib.decompress(blob)
    else:  # checked in metadata, defensive
        raise NotImplementedError(f"compression {meta.compression}")

    if len(raw) != expected:
        raise ValueError(f"tile payload {len(raw)} != {expected}")
    dtype = np.dtype("float32" if meta.sample_format == 3 else "int32")
    array = np.frombuffer(raw, dtype=dtype.newbyteorder(meta.byte_order))
    array = array.reshape(meta.tile_height, meta.tile_width)
    if meta.predictor == 2:
        array = np.cumsum(array, axis=1, dtype=array.dtype)
    return array.astype(np.float32, copy=False)


def read_cog_subset(http: CogHttp, url: str, target: TargetGrid):
    """Fetch and decode only the COG tiles covering the target bbox grid.

    Returns (precip float32 [360, 950] with NaN nodata, stats dict).
    """
    reader = CogRangeReader(http, url)
    meta = _read_cog_metadata(reader)

    if not (0 <= target.c0 < target.c1 <= meta.width
            and 0 <= target.r0 < target.r1 <= meta.height):
        raise RuntimeError("bbox window lies outside the COG")

    tile_c0 = target.c0 // meta.tile_width
    tile_c1 = (target.c1 - 1) // meta.tile_width
    tile_r0 = target.r0 // meta.tile_height
    tile_r1 = (target.r1 - 1) // meta.tile_height
    needed = [(row, col)
              for row in range(tile_r0, tile_r1 + 1)
              for col in range(tile_c0, tile_c1 + 1)]

    mosaic = np.full(
        ((tile_r1 - tile_r0 + 1) * meta.tile_height,
         (tile_c1 - tile_c0 + 1) * meta.tile_width),
        np.float32(np.nan), dtype=np.float32,
    )

    # Coalesce adjacent tiles into one range request.  For Indonesia the
    # three needed tiles are consecutive in the COG, so this is 1 request
    # instead of 3 (small inter-tile gaps are the only extra bytes).  A run
    # never includes a tile that is not needed.
    specs = []
    for row, col in needed:
        index = row * meta.tiles_x + col
        count = meta.counts[index]
        if count > 0:
            specs.append((index, meta.offsets[index], count, row, col))
    specs.sort()

    runs: list[list[tuple]] = []
    for spec in specs:
        _, offset, count, _, _ = spec
        if runs:
            _, prev_offset, prev_count, _, _ = runs[-1][-1]
            prev_end = prev_offset + prev_count
            if spec[0] == runs[-1][-1][0] + 1 and 0 <= offset - prev_end <= 4096:
                runs[-1].append(spec)
                continue
        runs.append([spec])

    for run in runs:
        span_start = run[0][1]
        span_end = run[-1][1] + run[-1][2] - 1
        blob = reader.fetch(span_start, span_end)
        for _, offset, count, row, col in run:
            relative = offset - span_start
            tile = _decode_cog_tile(blob[relative:relative + count], meta)
            row0 = (row - tile_r0) * meta.tile_height
            col0 = (col - tile_c0) * meta.tile_width
            mosaic[row0:row0 + meta.tile_height,
                   col0:col0 + meta.tile_width] = tile

    crop = mosaic[
        target.r0 - tile_r0 * meta.tile_height:target.r1 - tile_r0 * meta.tile_height,
        target.c0 - tile_c0 * meta.tile_width:target.c1 - tile_c0 * meta.tile_width,
    ]
    precip = crop.astype(np.float32, copy=True)
    nodata = COG_NODATA if meta.nodata is None else np.float32(meta.nodata)
    precip[precip == nodata] = np.nan
    precip[~np.isfinite(precip)] = np.nan

    stats = {
        "bytes": reader.bytes,
        "tile_bytes": reader.tile_bytes,
        "requests": reader.requests,
        "tile_requests": reader.tile_requests,
        "range_requests": len(runs),
        "tiles": len(needed),
        "file_size": reader.size,
    }
    return precip, stats


@dataclass(frozen=True)
class DaySource:
    variant: str
    url: str
    kind: str  # "cog" or "tif"


class ListingCache:
    """Fetch each CHC directory listing at most once per URL (per year)."""

    def __init__(self, http: CogHttp):
        self.http = http
        self._lock = threading.Lock()
        self._text: dict[str, Optional[str]] = {}
        self._files: dict[tuple[str, str], dict[str, str]] = {}
        self.bytes = 0
        self.requests = 0

    @staticmethod
    def _parse(text: str, extension: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for href in re.findall(r'href="([^"?][^"]*)"', text):
            if not href.lower().endswith(extension):
                continue
            match = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", href)
            if match:
                found["-".join(match.groups())] = href
        return found

    def files(self, url: str, extension: str, optional: bool = False) -> dict[str, str]:
        key = (url, extension)
        with self._lock:  # listings are rare; serialising them is harmless
            if key in self._files:
                return self._files[key]
            if url not in self._text:
                try:
                    text, size = self.http.get_text(url)
                    self._text[url] = text
                    self.bytes += size
                    self.requests += 1
                except PermanentHTTPError as exc:
                    if not optional:
                        raise
                    log(f"listing unavailable ({exc}); assuming none")
                    self._text[url] = None
                except DownloadError:
                    raise
            text = self._text[url]
            parsed = {} if text is None else self._parse(text, extension)
            self._files[key] = parsed
            return parsed

    def _year_files(self, base: str, year: int, extension: str,
                    optional: bool = True) -> dict[str, str]:
        return self.files(f"{base}/{year}/", extension, optional=optional)

    def resolve_final(self, day: dt.date) -> Optional[DaySource]:
        files = self._year_files(COG_FINAL_DIR, day.year, ".cog")
        href = files.get(day.isoformat())
        if href is None:
            return None
        url = urljoin(f"{COG_FINAL_DIR}/{day.year}/", href)
        return DaySource("final/sat", url, "cog")

    def resolve_prelim(self, day: dt.date) -> DaySource:
        year = day.year
        iso = day.isoformat()
        # Preferred layout: daily/prelim/sat/cogs/YYYY/*.cog
        cogs = self._year_files(f"{COG_PRELIM_DIR}/cogs", year, ".cog")
        href = cogs.get(iso)
        if href is not None:
            url = urljoin(f"{COG_PRELIM_DIR}/cogs/{year}/", href)
            return DaySource("prelim/sat", url, "cog")
        # Some archives keep .cog files beside the .tif files.
        year_files = self._year_files(COG_PRELIM_DIR, year, ".cog")
        href = year_files.get(iso)
        if href is not None:
            url = urljoin(f"{COG_PRELIM_DIR}/{year}/", href)
            return DaySource("prelim/sat", url, "cog")
        # No prelim COGs: use the full preliminary tif for this date only.
        tifs = self._year_files(COG_PRELIM_DIR, year, ".tif")
        href = tifs.get(iso)
        if href is not None:
            url = urljoin(f"{COG_PRELIM_DIR}/{year}/", href)
            return DaySource("prelim/sat", url, "tif")
        raise VariantNotFound(f"{iso}: no final COG, no prelim COG and no "
                              "prelim tif in the CHC listings")

    def resolve_day(self, day: dt.date) -> DaySource:
        final = self.resolve_final(day)
        if final is not None:
            return final
        return self.resolve_prelim(day)


class CogManifest:
    """manifest.csv for cog mode: date,variant,url,bytes_transferred,status."""

    def __init__(self, path: Path):
        self.path = path
        self.rows: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    date = (row.get("date") or "").strip()
                    if not date:
                        continue
                    url = (row.get("url") or row.get("source_url") or "").strip()
                    size_text = (row.get("bytes_transferred")
                                 or row.get("bytes") or "0")
                    try:
                        size = int(float(size_text))
                    except ValueError:
                        size = 0
                    self.rows[date] = {
                        "date": date,
                        "variant": (row.get("variant") or "").strip(),
                        "url": url,
                        "bytes_transferred": size,
                        "status": (row.get("status") or "").strip(),
                    }
        except Exception as exc:
            log(f"WARNING: could not read manifest {self.path}: {exc}; "
                "starting a new in-memory manifest")

    def record(self, day: dt.date, variant: str, url: str, status: str,
               bytes_transferred: int = 0) -> None:
        key = day.isoformat()
        previous = self.rows.get(key)
        # Never downgrade a successful provenance record.
        if previous and previous["status"] == "ok" and status != "ok":
            return
        self.rows[key] = {
            "date": key,
            "variant": variant or "",
            "url": url or "",
            "bytes_transferred": int(bytes_transferred or 0),
            "status": status,
        }

    def variant_for(self, day: dt.date) -> str:
        row = self.rows.get(day.isoformat())
        return row["variant"] if row else ""

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        ordered = sorted(self.rows.values(), key=lambda row: row["date"])
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COG_MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(ordered)
        os.replace(tmp, self.path)


@dataclass
class MonthData:
    dates: list[dt.date]
    cube: np.ndarray
    variants: list[str]


def read_month_file(path: Path, target: TargetGrid) -> MonthData:
    with np.load(path, allow_pickle=False) as npz:
        missing = [key for key in ("lat", "lon", "time", "precip")
                   if key not in npz.files]
        if missing:
            raise RuntimeError(f"{path.name} lacks key(s) {', '.join(missing)}")
        lat = np.asarray(npz["lat"], dtype=np.float32)
        lon = np.asarray(npz["lon"], dtype=np.float32)
        cube = np.asarray(npz["precip"], dtype=np.float32)
        times = np.asarray(npz["time"])
        if "variant" in npz.files:
            variants = [str(value) for value in npz["variant"]]
        else:
            variants = [""] * len(times)
    if (lat.shape != target.lat.shape
            or not np.allclose(lat, target.lat, rtol=0, atol=1e-6)):
        raise RuntimeError(f"{path.name} has a different latitude grid")
    if (lon.shape != target.lon.shape
            or not np.allclose(lon, target.lon, rtol=0, atol=1e-6)):
        raise RuntimeError(f"{path.name} has a different longitude grid")
    dates = [dt.date.fromisoformat(str(value)[:10]) for value in times]
    if cube.shape != (len(dates),) + target.shape:
        raise RuntimeError(f"{path.name} precip shape {cube.shape} does not match "
                           f"{len(dates)} days x {target.shape}")
    if len(variants) != len(dates):
        variants = [""] * len(dates)
    return MonthData(dates, cube, variants)


def write_month_file(path: Path, target: TargetGrid, data: MonthData) -> None:
    order = np.argsort(np.array([day.toordinal() for day in data.dates]))
    dates = [data.dates[i] for i in order]
    cube = np.ascontiguousarray(data.cube[order], dtype=np.float32)
    variants = np.array([data.variants[i] for i in order], dtype="U16")
    if cube.shape != (len(dates),) + target.shape:
        raise RuntimeError(f"refusing to write {path.name}: precip shape "
                           f"{cube.shape} does not match {len(dates)} x "
                           f"{target.shape}")
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("wb") as handle:
            np.savez_compressed(
                handle,
                lat=np.ascontiguousarray(target.lat, dtype=np.float32),
                lon=np.ascontiguousarray(target.lon, dtype=np.float32),
                time=np.array([day.isoformat() for day in dates],
                              dtype="datetime64[D]"),
                precip=cube,
                variant=variants,
            )
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def merge_month_data(existing: Optional[MonthData], results, target: TargetGrid,
                     manifest: CogManifest) -> MonthData:
    by_date: dict[dt.date, tuple[np.ndarray, str]] = {}
    if existing is not None:
        for index, day in enumerate(existing.dates):
            variant = existing.variants[index] or manifest.variant_for(day)
            by_date[day] = (existing.cube[index], variant)
    for result in results:
        by_date[result.day] = (result.precip, result.variant)
    dates = sorted(by_date)
    cube = np.stack([by_date[day][0] for day in dates]).astype(np.float32, copy=False)
    variants = [by_date[day][1] for day in dates]
    return MonthData(dates, cube, variants)


@dataclass
class DayResult:
    day: dt.date
    variant: str
    url: str
    status: str
    bytes_transferred: int = 0
    seconds: float = 0.0
    precip: Optional[np.ndarray] = None
    detail: str = ""
    error: str = ""


class CogDownloader:
    """Monthly, resume-safe, parallel COG subset downloader."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.bbox = tuple(float(value) for value in args.bbox)
        validate_bbox(self.bbox)
        self.out = Path(args.out).expanduser()
        self.workers = max(1, int(args.workers))
        self.http = CogHttp(args.delay, args.timeout, args.retries)
        self.listings = ListingCache(self.http)
        self.grid = target_grid(self.bbox)
        self.manifest = CogManifest(self.out / "manifest.csv")
        self.failures = 0
        self.total_bytes = 0
        self.total_tasks = 0
        self.task_seconds = 0.0

        if args.keep_global:
            log("note: --keep-global has no effect in cog mode; no global "
                "raster is written to disk")
        if args.cache_dir:
            log("note: --cache-dir has no effect in cog mode")
        if args.fmt == "netcdf":
            log("note: cog mode always writes monthly NPZ; --fmt netcdf ignored")

        self.out.mkdir(parents=True, exist_ok=True)

    def month_path(self, day: dt.date) -> Path:
        slug = bbox_slug(self.bbox)
        return self.out / f"chirps_v3_{slug}_{month_key(day)}.npz"

    def run(self, dates: list[dt.date]) -> int:
        dates = sorted(set(dates))
        if not dates:
            die("no dates requested")
        wall_start = time.perf_counter()
        log("CHIRPS v3.0 COG subset mode (Indonesia bbox by default)")
        log("variant: auto per date (final/sat COG first, then prelim/sat "
            "COG or full prelim tif fallback)")
        log(f"range: {dates[0]} .. {dates[-1]} ({len(dates)} day(s))")
        log(f"bbox: lon {self.bbox[0]} .. {self.bbox[2]}, "
            f"lat {self.bbox[1]} .. {self.bbox[3]}")
        log(f"grid: {self.grid.shape[0]} x {self.grid.shape[1]} cells, "
            f"lat {self.grid.lat[0]:.4f}..{self.grid.lat[-1]:.4f}, "
            f"lon {self.grid.lon[0]:.4f}..{self.grid.lon[-1]:.4f}")
        log(f"out: {self.out}")
        log(f"workers: {self.workers}, delay: {self.args.delay:g}s/request, "
            f"timeout: {self.args.timeout:g}s, retries: {self.args.retries}")
        log(library_report())

        months: dict[str, list[dt.date]] = {}
        for day in dates:
            months.setdefault(month_key(day), []).append(day)

        try:
            for key in sorted(months):
                self._process_month(key, months[key])
        except KeyboardInterrupt:
            log("interrupted by user")
            self.failures += 1
        finally:
            self.manifest.save()

        wall = time.perf_counter() - wall_start
        completed = max(1, self.total_tasks)
        log(f"summary: {len(dates) - self.failures}/{len(dates)} day(s) ok, "
            f"{self.failures} failed")
        log(f"summary: {self.total_bytes:,} B retrieved for day data "
            f"({mib(self.total_bytes)}), {wall / max(1, len(dates)):.2f} s/day "
            f"wall over {len(dates)} requested day(s)")
        log(f"summary: directory listings {self.listings.bytes:,} B in "
            f"{self.listings.requests} request(s)")
        log(f"summary: {wall:.1f}s wall total, "
            f"{self.task_seconds / completed:.2f}s average per fetched day")
        log(f"manifest: {self.manifest.path}")
        return 1 if self.failures else 0

    def _process_month(self, key: str, target_dates: list[dt.date]) -> None:
        path = self.month_path(target_dates[0])
        existing: Optional[MonthData] = None
        if path.exists() and not self.args.overwrite:
            try:
                existing = read_month_file(path, self.grid)
                log(f"{key}: found {path.name} with {len(existing.dates)} day(s)")
            except Exception as exc:
                log(f"WARNING: {path.name} is not usable ({exc}); rebuilding "
                    "the requested days")
                existing = None

        have = set(existing.dates) if existing else set()
        missing = [day for day in target_dates if day not in have]
        if not missing:
            log(f"{key}: complete ({len(target_dates)} requested day(s) already "
                f"in {path.name}); skipping")
            self._backfill_skipped(target_dates)
            self.manifest.save()
            return

        if existing is not None:
            log(f"{key}: partial month, {len(have)} day(s) stored, "
                f"fetching {len(missing)} missing day(s)")
        else:
            log(f"{key}: fetching {len(missing)} day(s)")

        results: list[DayResult] = []
        with ThreadPoolExecutor(max_workers=min(self.workers, len(missing))) as pool:
            futures = {pool.submit(self._process_day, day): day
                       for day in missing}
            for future in as_completed(futures):
                result = future.result()
                if result.status == "ok":
                    results.append(result)
                    self.total_bytes += result.bytes_transferred
                    self.task_seconds += result.seconds
                    self.total_tasks += 1
                else:
                    self.failures += 1
                self.manifest.record(
                    result.day, result.variant, result.url, result.status,
                    result.bytes_transferred if result.status == "ok" else 0,
                )

        if results:
            data = merge_month_data(existing, results, self.grid, self.manifest)
            write_month_file(path, self.grid, data)
            log(f"{key}: wrote {path.name} ({len(data.dates)} day(s), "
                f"{mib(path.stat().st_size)})")
        elif existing is None:
            log(f"{key}: no data written (all requested days failed)")

        self.manifest.save()

    def _backfill_skipped(self, dates: list[dt.date]) -> None:
        for day in dates:
            if day.isoformat() in self.manifest.rows:
                continue
            try:
                source = self.listings.resolve_day(day)
                self.manifest.record(day, source.variant, source.url,
                                     "skipped", 0)
            except Exception:
                self.manifest.record(day, "", "", "skipped", 0)

    def _process_day(self, day: dt.date) -> DayResult:
        started = time.perf_counter()
        try:
            source = self.listings.resolve_day(day)
        except Exception as exc:
            seconds = time.perf_counter() - started
            log(f"{day}: FAILED (variant discovery): {exc}")
            return DayResult(day, "", "", "failed", 0, seconds, error=str(exc))

        try:
            precip, transferred, detail = self._fetch(source)
            self._validate_day(precip)
            seconds = time.perf_counter() - started
            valid = int(np.isfinite(precip).sum())
            missing = int(np.isnan(precip).sum())
            log(f"{day}: ok {source.variant} [{source.kind}] {detail}, "
                f"{transferred:,} B, {seconds:.2f}s, valid={valid}, NaN={missing}")
            return DayResult(day, source.variant, source.url, "ok",
                             transferred, seconds, precip, detail)
        except PermanentHTTPError as exc:
            # A listing can be stale.  If the final COG vanished between the
            # listing and the range request, try the prelim branch once.
            if source.kind == "cog" and source.variant == "final/sat":
                log(f"{day}: final COG unavailable ({exc}); trying prelim")
                try:
                    fallback = self.listings.resolve_prelim(day)
                    precip, transferred, detail = self._fetch(fallback)
                    self._validate_day(precip)
                    seconds = time.perf_counter() - started
                    log(f"{day}: ok {fallback.variant} [{fallback.kind}] "
                        f"{detail}, {transferred:,} B, {seconds:.2f}s (prelim fallback)")
                    return DayResult(day, fallback.variant, fallback.url, "ok",
                                     transferred, seconds, precip, detail)
                except Exception as fallback_exc:
                    exc = fallback_exc
            seconds = time.perf_counter() - started
            log(f"{day}: FAILED: {exc}")
            return DayResult(day, source.variant, source.url, "failed", 0,
                             seconds, error=str(exc))
        except Exception as exc:
            seconds = time.perf_counter() - started
            log(f"{day}: FAILED: {exc}")
            return DayResult(day, source.variant, source.url, "failed", 0,
                             seconds, error=str(exc))

    def _fetch(self, source: DaySource):
        if source.kind == "cog":
            precip, stats = read_cog_subset(self.http, source.url, self.grid)
            detail = (f"{stats['tiles']} tile(s) in "
                      f"{stats['range_requests']} range(s), "
                      f"{stats['tile_bytes']:,} B tiles, "
                      f"full file {stats['file_size']:,} B")
            return precip, stats["bytes"], detail

        blob, transferred = self.http.get_bytes(source.url)
        arr, grid = decode_tiff_bytes(blob)
        precip, lat_day, lon_day, _ = clip_array(arr, grid, self.bbox)
        if lat_day.shape != self.grid.lat.shape or lon_day.shape != self.grid.lon.shape:
            raise RuntimeError("prelim tif produced a different grid shape")
        if (not np.allclose(lat_day, self.grid.lat, rtol=0, atol=1e-6)
                or not np.allclose(lon_day, self.grid.lon, rtol=0, atol=1e-6)):
            raise RuntimeError("prelim tif produced different cell centres")
        detail = f"{mib(len(blob))} in-memory tif"
        return precip, transferred, detail

    def _validate_day(self, precip: np.ndarray) -> None:
        if precip.shape != self.grid.shape:
            raise RuntimeError(f"unexpected precip shape {precip.shape}, "
                               f"expected {self.grid.shape}")
        if precip.dtype != np.float32:
            raise RuntimeError(f"unexpected precip dtype {precip.dtype}")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download CHIRPS v3.0 daily rainfall and clip it to a bbox "
                    "(default Indonesia).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start", required=True, type=parse_date,
                        help="first date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=parse_date,
                        help="last date, inclusive, YYYY-MM-DD")
    parser.add_argument("--variant", default="final/sat",
                        help="final/sat, final/rnl or prelim/sat "
                             "(aliases: sat, rnl, prelim)")
    parser.add_argument("--out", default="data/raw/chirps_v3",
                        help="output directory")
    parser.add_argument("--bbox", nargs=4, type=float,
                        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
                        default=list(DEFAULT_BBOX),
                        help="bounding box: lon_min lat_min lon_max lat_max")
    parser.add_argument("--source", choices=["cog", "auto", "tif", "netcdf"],
                        default="cog",
                        help="cog = HTTP Range/tile subset (default, Indonesia); "
                             "tif/netcdf = legacy full-file paths; auto respects "
                             "--max-netcdf-gb")
    parser.add_argument("--max-netcdf-gb", type=float, default=2.0,
                        help="legacy auto mode only: skip yearly NetCDF above "
                             "this estimated size; 0 = no limit")
    parser.add_argument("--fmt", choices=["auto", "npz", "netcdf"],
                        default="auto",
                        help="legacy output format; cog mode always writes "
                             "monthly NPZ files")
    parser.add_argument("--cache-dir", default=None,
                        help="legacy mode: where global downloads are kept "
                             "(default: <out>/_cache); unused by cog")
    parser.add_argument("--keep-global", action="store_true",
                        help="legacy mode: keep downloaded global files; "
                             "cog mode never writes a global raster")
    parser.add_argument("--overwrite", action="store_true",
                        help="rebuild existing output files from scratch")
    parser.add_argument("--workers", type=int, default=4,
                        help="cog mode: parallel days (thread pool)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="polite delay between HTTP requests, seconds")
    parser.add_argument("--retries", type=int, default=4,
                        help="retries per request (exponential backoff)")
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="HTTP read timeout, seconds")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.start > args.end:
        parser.error("--start must be on or before --end")
    if args.retries < 0:
        parser.error("--retries must be >= 0")
    if args.delay < 0:
        parser.error("--delay must be >= 0")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.workers < 1:
        parser.error("--workers must be >= 1")

    variant = normalise_variant(args.variant)
    info = VARIANTS[variant]
    min_year = 1998 if args.source == "cog" else info.min_year
    if args.start.year < min_year:
        parser.error(f"{args.variant} starts in {min_year}; "
                     f"requested start is {args.start}")
    if args.source == "cog" and variant == "final/rnl":
        parser.error("cog mode supports final/sat (default) and prelim/sat "
                     "fallback; use --source tif for final/rnl")
    if args.end > dt.date.today():
        log(f"WARNING: --end {args.end} is in the future; missing days will fail")

    dates = list(date_range(args.start, args.end))
    if args.source == "cog":
        return CogDownloader(args).run(dates)
    return ChirpsDownloader(args).run(dates)


if __name__ == "__main__":
    sys.exit(main())
