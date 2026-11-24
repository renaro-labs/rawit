"""Plot the climatological seasonal rain cycle for Java (CGS H2 supporting figure).

Reads the province-level daily rainfall produced by CGS-H2-01 and writes a
single figure used in the H2 data report. Deterministic: same input -> same
figure.

Usage (from the repo root, ``$env:PYTHONPATH = "src"``):

    python scripts/cgs/plot_rain_seasonal.py
    python scripts/cgs/plot_rain_seasonal.py --provinces 31,32,33,34,35 --out reports/qa/fig_rain_seasonal.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

JAVA = ("31", "32", "33", "34", "35")
DEFAULT_IN = Path("data/interim/rain_prov_daily.parquet")
DEFAULT_OUT = Path("reports/qa/fig_rain_seasonal.png")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Seasonal rain cycle figure (Java)")
    ap.add_argument("--input", type=Path, default=DEFAULT_IN, help="rain_prov_daily parquet")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output PNG")
    ap.add_argument("--provinces", default=",".join(JAVA), help="comma-separated prov_code")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    codes = [c.strip() for c in args.provinces.split(",") if c.strip()]

    frame = pd.read_parquet(args.input)
    frame["date"] = pd.to_datetime(frame["date"])
    java = frame[frame["prov_code"].astype(str).isin(codes)].copy()
    if java.empty:
        raise SystemExit(f"Tidak ada baris untuk prov_code {codes} di {args.input}")
    java["month"] = java["date"].dt.month

    monthly = java.groupby("month")["rain_mm"].mean()
    if len(monthly) != 12:
        raise SystemExit(f"Data bulan tidak lengkap: {sorted(monthly.index)}")

    fig, ax = plt.subplots(figsize=(8, 4))
    monthly.plot(ax=ax, marker="o", color="#2563eb", linewidth=2)
    ax.axvspan(5.5, 9.5, color="#f59e0b", alpha=0.15)
    ax.set(
        xlabel="Bulan",
        ylabel="Curah hujan (mm/hari)",
        title="Siklus Musiman Hujan di Pulau Jawa",
    )
    ax.set_xticks(range(1, 13))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"Grafik disimpan ke: {args.out}")


if __name__ == "__main__":
    main()
