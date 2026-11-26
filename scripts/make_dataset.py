"""MDE-H5-01 · Pipeline satu perintah: data mentah -> dataset v1 -> cek reproduksi.

    python scripts/make_dataset.py --config configs/data/v1.yaml [--skip-download]

Urutan tahap (lihat `pipeline.stages` di configs/data/v1.yaml):
  download  -> pihps -> sp2kp -> coverage -> calendar -> cleaning -> bps_mask
  -> climate (langkah CGS: bobot piksel, hujan, pentad, available_at) -> build -> tests -> compare

* Idempoten: tiap tahap menulis data/interim/.stamps/<tahap>.json berisi sha256 input,
  kode, parameter, dan output. Tahap dilewati bila stamp cocok dan output masih ada dengan
  hash yang sama. Paksa ulang: --force (semua) atau --force-stage <nama>.
* Tidak pernah menimpa dataset beku: build menulis ke `pipeline.repro_dir`
  (default data/processed/_repro/dataset_v1) lalu membandingkan content_hash dengan
  data/processed/dataset_v1/VERSION (ter-track git) -> "REPRODUCED OK" atau diff.
* Laporan QA hasil rerun ditulis ke data/interim/.qa/ (bukan reports/qa) agar
  laporan resmi yang sudah ditandatangani tidak berubah.
* Tidak menyentuh holdout: parser menolak file >= 2026-06-01; folder _sealed tidak dibaca.

Pakai di Windows tanpa make. Python dipanggil dengan interpreter yang sama (sys.executable).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("configs/data/v1.yaml")
STAMPS = Path("data/interim/.stamps")
QA = Path("data/interim/.qa")

DEFAULT_PIPELINE = {
    "start": "2017-07-01",
    "end": "2026-05-31",
    "frozen_dir": "data/processed/dataset_v1",
    "repro_dir": "data/processed/_repro/dataset_v1",
    "bps_pdf": "data/raw/bps/BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf",
    "tests": ["tests/test_prices_clean.py", "tests/test_calendar.py", "tests/test_bps_mask.py",
              "tests/test_build_dataset.py", "tests/test_no_leakage.py"],
}


# --------------------------------------------------------------------- hashing
class HashCache:
    """sha256 file dengan cache (ukuran, mtime) agar CHIRPS 2,5 GB tidak dihitung ulang tiap run."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.db = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.db = {}

    def sha(self, p: Path) -> str:
        st = p.stat()
        key = p.as_posix()
        hit = self.db.get(key)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            return hit[2]
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while block := f.read(1 << 20):
                h.update(block)
        self.db[key] = [st.st_size, st.st_mtime_ns, h.hexdigest()]
        return h.hexdigest()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.db, indent=0, sort_keys=True), encoding="utf-8", newline="\n")


def expand(patterns: list[str]) -> list[Path]:
    """Pola glob -> daftar file terurut. Folder _sealed selalu dikecualikan."""
    out: list[Path] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True)) if any(c in pat for c in "*?[") else [pat]
        out += [Path(h) for h in hits if "_sealed" not in Path(h).parts and Path(h).is_file()]
    return out


# ---------------------------------------------------------------------- tahap
@dataclass
class Stage:
    name: str
    cmds: list[list[str]]
    inputs: list[str]                       # pola file input (harus ada)
    outputs: list[str]                      # file output
    code: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    always: bool = False                    # tanpa stamp (download, tests, compare)
    description: str = ""


def py(*args: str) -> list[str]:
    return [sys.executable, *args]


def stages(cfg: dict, pcfg: dict, config_path: Path) -> list[Stage]:
    start, end = pcfg["start"], pcfg["end"]
    repro = pcfg["repro_dir"]
    pdf = pcfg["bps_pdf"]
    contract = "src/renaro/contract.py"
    return [
        Stage("download", [py("-m", "renaro.data.pihps", "--price-type", "1"),
                           py("-m", "renaro.data.pihps", "--price-type", "4"),
                           py("-m", "renaro.data.sp2kp")],
              [], [], always=True,
              description="unduh JSON PIHPS t1/t4 + SP2KP yang belum ada (file yang ada tidak diunduh ulang)"),
        Stage("pihps", [py("-m", "renaro.data.pihps", "--parse-only")],
              ["data/raw/pihps/pt[14]_*.json"], ["data/interim/pihps_long.parquet"],
              ["src/renaro/data/pihps.py", "src/renaro/data/pihps_parse.py", contract]),
        Stage("sp2kp", [py("-m", "renaro.data.sp2kp", "--parse-only")],
              ["data/raw/sp2kp/l1_*.json", "data/ref/provinces.csv"], ["data/interim/sp2kp_long.parquet"],
              ["src/renaro/data/sp2kp.py", contract]),
        Stage("coverage", [py("-m", "renaro.data.coverage", "--out-dir", str(QA))],
              ["data/interim/pihps_long.parquet"], [f"{QA.as_posix()}/coverage_pihps.csv"],
              ["src/renaro/data/coverage.py", contract]),
        Stage("calendar", [py("-m", "renaro.data.calendar")],
              ["data/interim/pihps_long.parquet", "data/ref/religious_dates.csv", "data/ref/cuti_bersama.csv"],
              ["data/interim/calendar.csv"], ["src/renaro/data/calendar.py", contract]),
        Stage("cleaning", [py("-m", "renaro.data.cleaning", "--config", str(config_path), "--qa-dir", str(QA))],
              ["data/interim/pihps_long.parquet", "data/interim/sp2kp_long.parquet", "data/interim/calendar.csv",
               "data/ref/provinces.csv", str(config_path)],
              ["data/interim/prices_clean.parquet"], ["src/renaro/data/cleaning.py", contract]),
        Stage("bps_mask", [py("-m", "renaro.data.bps_mask", "--pdf", pdf, "--report", f"{QA.as_posix()}/bps_mask.md")],
              ["data/interim/bps_mask_entry.csv", pdf],
              ["data/interim/bps_mask.npy", "data/interim/bps_mask.csv", "data/interim/bps_mask_2022.csv"],
              ["src/renaro/data/bps_mask.py", contract]),
        Stage("climate",
              [py("scripts/cgs/build_kab_pixel_weights.py"),
               py("-m", "renaro.climate.rain", "--qa", f"{QA.as_posix()}/rain_prov.md"),
               py("-m", "renaro.climate.pentad", "--qa", f"{QA.as_posix()}/climate_features.md"),
               py("-m", "renaro.climate.availability")],
              ["data/raw/chirps_v3/chirps_v3_idn_*.npz", "data/raw/boundaries/idn_adm2.gpkg",
               "data/raw/bps/kab_area_weights.csv", "data/raw/bps/produksi_kab.csv"],
              ["data/interim/climate_features.parquet", "data/interim/roni.parquet",
               "data/interim/availability.csv"],
              ["scripts/cgs/build_kab_pixel_weights.py", "src/renaro/climate/rain.py",
               "src/renaro/climate/pentad.py", "src/renaro/climate/availability.py", contract],
              description="langkah iklim milik CGS (CGS-H2-01..03); roni.parquet = salinan segel CGS"),
        Stage("build", [py("scripts/build_dataset.py", "--start", start, "--end", end, "--out", repro,
                           "--coverage", f"{QA.as_posix()}/coverage_pihps.csv",
                           "--report", f"{QA.as_posix()}/dataset_v1.md")],
              ["data/interim/prices_clean.parquet", "data/interim/calendar.csv", "data/interim/bps_mask.npy",
               "data/interim/climate_features.parquet", "data/interim/roni.parquet", "data/ref/provinces.csv",
               f"{QA.as_posix()}/coverage_pihps.csv"],
              [f"{repro}/panel.parquet", f"{repro}/target.parquet", f"{repro}/nodes.csv",
               f"{repro}/bps_mask.npy", f"{repro}/VERSION"],
              ["scripts/build_dataset.py", "src/renaro/data/dataset_v1.py", contract],
              params={"start": start, "end": end}),
        Stage("tests", [py("-m", "pytest", "-q", "-p", "no:cacheprovider", *pcfg["tests"])], [], [], always=True),
        Stage("compare", [], [], [], always=True),
    ]


# ---------------------------------------------------------------------- stamp
def fingerprint(st: Stage, hc: HashCache) -> dict:
    files = expand(st.inputs)
    missing = [p for p in st.inputs if not any(c in p for c in "*?[") and not Path(p).is_file()]
    globs_empty = [p for p in st.inputs if any(c in p for c in "*?[") and not expand([p])]
    if missing or globs_empty:
        raise FileNotFoundError(f"[{st.name}] input tidak ada: {missing + globs_empty}")
    return {
        "inputs": {p.as_posix(): hc.sha(p) for p in files},
        "code": {c: hc.sha(Path(c)) for c in st.code},
        "params": st.params,
        "cmds": [[Path(a).name if i == 0 else a for i, a in enumerate(c)] for c in st.cmds],
    }


def up_to_date(st: Stage, fp: dict, hc: HashCache) -> tuple[bool, str]:
    path = STAMPS / f"{st.name}.json"
    if not path.exists():
        return False, "belum pernah dijalankan"
    old = json.loads(path.read_text(encoding="utf-8"))
    for key in ("inputs", "code", "params", "cmds"):
        if old.get(key) != fp[key]:
            changed = sorted(set(old.get(key, {})) ^ set(fp[key])) if isinstance(fp[key], dict) else []
            changed += [k for k in fp[key] if isinstance(fp[key], dict) and old.get(key, {}).get(k) != fp[key][k]]
            return False, f"{key} berubah {sorted(set(changed))[:3]}"
    for o, sha in old.get("outputs", {}).items():
        if not Path(o).is_file():
            return False, f"output hilang: {o}"
        if hc.sha(Path(o)) != sha:
            return False, f"output berubah: {o}"
    return True, "stamp cocok"


def write_stamp(st: Stage, fp: dict, hc: HashCache, seconds: float) -> None:
    STAMPS.mkdir(parents=True, exist_ok=True)
    outs = {}
    for o in st.outputs:
        if not Path(o).is_file():
            raise FileNotFoundError(f"[{st.name}] output yang dijanjikan tidak ada: {o}")
        outs[o] = hc.sha(Path(o))
    rec = {"stage": st.name, **fp, "outputs": outs, "seconds": round(seconds, 1),
           "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
           "python": sys.version.split()[0]}
    (STAMPS / f"{st.name}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8", newline="\n")


def run_cmds(st: Stage, env: dict) -> None:
    for cmd in st.cmds:
        shown = " ".join(["python" if i == 0 else a for i, a in enumerate(cmd)])
        print(f"    $ {shown}", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        if r.returncode != 0:
            raise SystemExit(f"[{st.name}] GAGAL (exit {r.returncode}): {shown}")


# -------------------------------------------------------------------- compare
def compare(frozen_dir: Path, repro_dir: Path) -> bool:
    fv = json.loads((frozen_dir / "VERSION").read_text(encoding="utf-8"))
    rv = json.loads((repro_dir / "VERSION").read_text(encoding="utf-8"))
    print(f"\n== compare: {repro_dir.as_posix()} vs {frozen_dir.as_posix()}/VERSION "
          f"(versi beku {fv['version']}, kode {fv.get('git_commit')})")
    ok = True
    for k in sorted(set(fv["content_hash"]) | set(rv["content_hash"])):
        a, b = fv["content_hash"].get(k), rv["content_hash"].get(k)
        same = a == b
        ok &= same
        print(f"   {k:9s} beku={str(a)[:16]}…  repro={str(b)[:16]}…  {'OK' if same else 'BEDA'}")
    for k in ("rows_panel", "n_dates", "date_min", "date_max"):
        if fv.get(k) != rv.get(k):
            print(f"   {k}: beku={fv.get(k)} repro={rv.get(k)}")
    if ok:
        print("\nREPRODUCED OK")
        return True
    diff_detail(frozen_dir, repro_dir, fv, rv)
    if numeric_equal(frozen_dir, repro_dir, fv, rv):
        print(f"\nREPRODUCED OK (numerik) — content_hash beda hanya karena pembulatan floating-point "
              f"(semua kolom identik kecuali float dengan |Δ| ≤ {ATOL:g} + {RTOL:g}·|x|; "
              "biasanya dari langkah iklim yang dihitung ulang di mesin/BLAS berbeda). "
              "Bit-exact: jalankan dengan --skip-climate memakai climate_features.parquet CGS.")
        return True
    print("\nREPRODUCED GAGAL — lihat diff di atas")
    return False


ATOL = 1e-9
RTOL = 1e-9


def numeric_equal(frozen_dir: Path, repro_dir: Path, fv: dict, rv: dict) -> bool:
    """True bila tabel yang hash-nya beda identik kecuali float dalam toleransi (dan pola NaN sama)."""
    import numpy as np
    import pandas as pd
    for name in ("nodes", "bps_mask"):
        if fv["content_hash"].get(name) != rv["content_hash"].get(name):
            return False
    for name in ("panel", "target"):
        if fv["content_hash"].get(name) == rv["content_hash"].get(name):
            continue
        fp = frozen_dir / f"{name}.parquet"
        if not fp.exists():
            return False
        a = pd.read_parquet(fp).sort_values(["date", "prov_code"]).reset_index(drop=True)
        b = pd.read_parquet(repro_dir / f"{name}.parquet").sort_values(["date", "prov_code"]).reset_index(drop=True)
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            return False
        for c in a.columns:
            if a[c].equals(b[c]):
                continue
            if not (pd.api.types.is_float_dtype(a[c]) and pd.api.types.is_float_dtype(b[c])):
                return False
            if not np.allclose(a[c].to_numpy(float), b[c].to_numpy(float), rtol=RTOL, atol=ATOL, equal_nan=True):
                return False
    return True


def diff_detail(frozen_dir: Path, repro_dir: Path, fv: dict, rv: dict) -> None:
    import numpy as np
    import pandas as pd
    for name in ("panel", "target"):
        fp = frozen_dir / f"{name}.parquet"
        if fv["content_hash"].get(name) == rv["content_hash"].get(name):
            continue
        if not fp.exists():
            print(f"   [{name}] parquet beku tidak ada lokal (ekstrak dataset_v1_mde.zip) — diff kolom dilewati")
            continue
        a = pd.read_parquet(fp).sort_values(["date", "prov_code"]).reset_index(drop=True)
        b = pd.read_parquet(repro_dir / f"{name}.parquet").sort_values(["date", "prov_code"]).reset_index(drop=True)
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            print(f"   [{name}] bentuk/kolom beda: beku {a.shape} vs repro {b.shape}; "
                  f"kolom hanya-beku={sorted(set(a) - set(b))} hanya-repro={sorted(set(b) - set(a))}")
            continue
        for c in a.columns:
            x, y = a[c], b[c]
            if x.equals(y):
                continue
            if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
                xa, ya = x.to_numpy(float), y.to_numpy(float)
                diff = ~((xa == ya) | (np.isnan(xa) & np.isnan(ya)))
                print(f"   [{name}.{c}] {int(diff.sum())} baris beda; max |Δ| = "
                      f"{np.nanmax(np.abs(xa[diff] - ya[diff])) if diff.any() else 0:.3g}; "
                      f"contoh tanggal {a.loc[diff, 'date'].head(3).dt.date.tolist()}")
            else:
                ne = (x.astype(str) != y.astype(str))
                print(f"   [{name}.{c}] {int(ne.sum())} baris beda (dtype {x.dtype} vs {y.dtype})")


# ----------------------------------------------------------------------- main
def load_config(path: Path) -> tuple[dict, dict]:
    import yaml
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pcfg = {**DEFAULT_PIPELINE, **(raw.get("pipeline") or {})}
    return raw, pcfg


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="MDE-H5-01 pipeline mentah -> dataset v1 (+ cek reproduksi)")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--skip-download", action="store_true", help="pakai data mentah yang sudah ada (drive bersama)")
    ap.add_argument("--skip-climate", action="store_true",
                    help="pakai climate_features.parquet/roni.parquet yang ada (tanpa menjalankan langkah CGS)")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--force", action="store_true", help="jalankan ulang semua tahap walau stamp cocok")
    ap.add_argument("--force-stage", action="append", default=[], help="jalankan ulang tahap tertentu")
    ap.add_argument("--only", nargs="+", help="hanya tahap ini (urutan tetap)")
    ap.add_argument("--dry-run", action="store_true", help="tampilkan tahap mana yang akan jalan/dilewati")
    args = ap.parse_args(argv)

    os.chdir(ROOT)
    raw, pcfg = load_config(args.config)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, ["src", os.environ.get("PYTHONPATH", "")])),
           "PYTHONIOENCODING": "utf-8"}
    QA.mkdir(parents=True, exist_ok=True)
    hc = HashCache(STAMPS / "_hashcache.json")
    plan = stages(raw, pcfg, args.config)
    skip = {"download"} if args.skip_download else set()
    if args.skip_climate:
        skip.add("climate")
    if args.skip_tests:
        skip.add("tests")
    if args.only:
        unknown = set(args.only) - {s.name for s in plan}
        if unknown:
            raise SystemExit(f"tahap tak dikenal: {sorted(unknown)}; pilihan: {[s.name for s in plan]}")
        skip |= {s.name for s in plan} - set(args.only)

    print(f"make_dataset: config={args.config.as_posix()} python={sys.version.split()[0]} root={ROOT}")
    entry, rl_entry = Path("data/interim/bps_mask_entry.csv"), Path("RL hasil/supporting_data/bps_mask_entry.csv")
    if not entry.exists() and rl_entry.exists() and not args.dry_run:
        # clone bersih: entri digitasi BPS (ter-track git di RL hasil/) dinormalisasi ke data/interim
        import pandas as pd
        sys.path.insert(0, str(ROOT / "src"))
        from renaro.data.bps_mask import normalize_entry
        entry.parent.mkdir(parents=True, exist_ok=True)
        normalize_entry(pd.read_csv(rl_entry, dtype=str)).to_csv(entry, index=False)
        print(f"[seed ] {entry} dari {rl_entry}")
    t_all = time.time()
    ok = True
    tests_failed = False
    for st in plan:
        if st.name in skip:
            note = " (pakai output yang ada)" if st.name == "climate" else ""
            print(f"[skip ] {st.name}{note}")
            if st.name == "climate":
                for o in st.outputs[:2]:          # climate_features + roni (availability.csv tidak dipakai build)
                    if not Path(o).is_file():
                        raise SystemExit(f"--skip-climate butuh {o} (salin dari drive bersama CGS)")
            continue
        if st.name == "compare":
            ok = compare(Path(pcfg["frozen_dir"]), Path(pcfg["repro_dir"]))
            continue
        if st.always:
            print(f"[run  ] {st.name}  {st.description}".rstrip(), flush=True)
            if not args.dry_run:
                try:
                    run_cmds(st, env)
                except SystemExit as e:
                    if st.name != "tests":
                        raise
                    tests_failed = True       # lanjut ke compare; exit code akhir != 0
                    print(f"        {e}", flush=True)
            continue
        try:
            fp = fingerprint(st, hc)
        except FileNotFoundError as e:
            if args.dry_run:      # input baru dibuat oleh tahap sebelumnya
                print(f"[run  ] {st.name}  (input dari tahap sebelumnya belum ada)")
                continue
            raise SystemExit(str(e))
        fresh, why = up_to_date(st, fp, hc)
        if fresh and not args.force and st.name not in args.force_stage:
            print(f"[ok   ] {st.name}  dilewati: {why}")
            continue
        print(f"[run  ] {st.name}  ({why}) {st.description}".rstrip(), flush=True)
        if args.dry_run:
            continue
        t0 = time.time()
        run_cmds(st, env)
        write_stamp(st, fp, hc, time.time() - t0)
        hc.save()
        print(f"        selesai {time.time() - t0:.1f} s", flush=True)
    hc.save()
    print(f"\nTotal {time.time() - t_all:.1f} s")
    if tests_failed:
        print("PERINGATAN: ada test yang gagal (lihat output pytest di atas)")
    if not args.dry_run and (tests_failed or ("compare" not in skip and not ok)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
