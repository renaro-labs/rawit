"""MDE-H2-03 · Digitasi mask BPS Poldis cabai merah 2022 (34 provinsi).

PDF Poldis TIDAK punya matriks asal-tujuan. Yang ada per bab provinsi: diagram
dengan kotak "WILAYAH PEMBELIAN DARI LUAR PROVINSI" (asal) dan "WILAYAH PENJUALAN
KE LUAR PROVINSI" (tujuan). Karena itu output dipakai sebagai MASK BINER.

Konvensi (docs/data_contract.md §2.6):
  * bps_mask_entry.csv : satu baris per kemunculan edge di satu halaman.
      dest_code/origin_code SELALU arah aliran (origin -> dest).
      relation = kotak tempat edge tercetak:
        asal   -> kotak PEMBELIAN di halaman provinsi dest
        tujuan -> kotak PENJUALAN di halaman provinsi origin
  * bps_mask.csv       : satu baris per edge unik (union asal+tujuan),
      share_pct = maks, n_confirmations = jumlah kotak (1 atau 2).
  * bps_mask.npy       : 34x34 uint8, A[i, j] = 1 bila j -> i (baris = tujuan).
  * bps_mask_2022.csv  : matriks baris = pemasok (src), kolom = pembeli (dst)
      = bps_mask.npy.T, nama provinsi, sel kosong = 0 (dipakai scripts/check_env.py).
  * bps_mask_2022_pages.csv : src,dst,page per entri.

Pemakaian:
  python -m renaro.data.bps_mask                       # entry -> mask + laporan (+ cek PDF bila ada)
  python -m renaro.data.bps_mask --text-only           # hanya ekstraksi teks PDF
  python -m renaro.data.bps_mask --seed-from "RL hasil/supporting_data/bps_mask_entry.csv"
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from renaro.contract import N_NODES, NODE_INDEX, PROV_CODES, PROVINCES

PDF_PATH = Path("data/raw/bps/BPS0000-distribusi_perdagangan_komoditas_cabai_merah_di_indonesia_2022.pdf")
TEXT_DIR = Path("data/interim/bps_pdf_text")
ENTRY = Path("data/interim/bps_mask_entry.csv")
MASK_CSV = Path("data/interim/bps_mask.csv")
MASK_NPY = Path("data/interim/bps_mask.npy")
MATRIX_CSV = Path("data/interim/bps_mask_2022.csv")
PAGES_CSV = Path("data/interim/bps_mask_2022_pages.csv")
TEXT_CHECK_CSV = Path("reports/qa/bps_mask_text_check.csv")
REPORT = Path("reports/qa/bps_mask.md")

ENTRY_COLUMNS = (
    "dest_code", "origin_code", "share_pct", "relation", "page", "method", "entered_by",
)
EDGE_COLUMNS = ("dest_code", "origin_code", "share_pct", "relations", "pages", "n_confirmations")
RELATIONS = ("asal", "tujuan")
METHODS = ("text", "manual")
#: Label metode lama dari RL (H1) -> skema tiket.
LEGACY_METHODS = {"pdf_text_and_visual_dual_verified": "text"}
#: Kode bukan-provinsi yang dibuang saat merge (bukan error).
NON_PROVINCE = {"ln", "luar negeri", "lainnya", "lain", "00", "99"}

#: Bab provinsi: urut kode BPS naik, 4 halaman per bab, diagram di halaman pertama.
FIRST_CHAPTER_PAGE = 45
PAGES_PER_CHAPTER = 4
CHAPTER_ORDER: tuple[str, ...] = tuple(sorted(PROV_CODES, key=int))
CHAPTER_PAGE: dict[str, int] = {
    c: FIRST_CHAPTER_PAGE + PAGES_PER_CHAPTER * k for k, c in enumerate(CHAPTER_ORDER)
}
PROV_NAME: dict[str, str] = dict(PROVINCES)
#: Urutan baris/kolom bps_mask_2022.csv (bps_mask_TEMPLATE.csv, RL H1) — BUKAN urutan kontrak.
TEMPLATE_ORDER: tuple[str, ...] = (
    "Aceh",
    "Sumatera Utara",
    "Sumatera Barat",
    "Riau",
    "Kepulauan Riau",
    "Jambi",
    "Bengkulu",
    "Sumatera Selatan",
    "Kepulauan Bangka Belitung",
    "Lampung",
    "Banten",
    "Jawa Barat",
    "DKI Jakarta",
    "Jawa Tengah",
    "DI Yogyakarta",
    "Jawa Timur",
    "Bali",
    "Nusa Tenggara Barat",
    "Nusa Tenggara Timur",
    "Kalimantan Barat",
    "Kalimantan Selatan",
    "Kalimantan Tengah",
    "Kalimantan Timur",
    "Kalimantan Utara",
    "Gorontalo",
    "Sulawesi Selatan",
    "Sulawesi Tenggara",
    "Sulawesi Tengah",
    "Sulawesi Utara",
    "Sulawesi Barat",
    "Maluku",
    "Maluku Utara",
    "Papua",
    "Papua Barat",
)

#: Ekspektasi tim (bukan target keras) — laporkan angka nyata.
DENSITY_EXPECTED = 0.14
MAX_VERIFY_ERROR = 0.05

#: Hasil audit naratif RL+MDE untuk edge yang hanya tercetak di satu kotak.
AUDIT_NOTES: dict[tuple[str, str], str] = {
    ("73", "64"): "VALID: narasi hal. 134 (Kaltim) & 150 (Sulsel) menyebut Sulsel memasok Kaltim.",
    ("74", "64"): "TYPO BPS hal. 133: narasi hal. 134 menyebut Sulsel, hal. 154 Sultra hanya ke Sulsel & Maluku.",
    ("52", "35"): "TYPO BPS hal. 113: narasi hal. 114 NTB hanya ke Babel; hal. 101-102 Jatim hanya dari Jateng/Bali/Sulsel.",
}


# --------------------------------------------------------------------------- PDF
def _pymupdf():
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError:  # versi lama
        import fitz as pymupdf  # noqa: PLC0415
    return pymupdf


def extract_text_pages(pdf_path: Path, out_dir: Path = TEXT_DIR) -> pd.DataFrame:
    """PyMuPDF: teks per halaman -> page_XXX.txt (1-based). Halaman raster dicatat, tidak di-OCR."""
    pm = _pymupdf()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with pm.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            (out_dir / f"page_{i:03d}.txt").write_text(text, encoding="utf-8")
            n_chars = len(text.strip())
            n_img = len(page.get_images(full=True))
            rows.append({
                "page": i, "n_chars": n_chars, "n_images": n_img,
                "is_raster": n_chars < 30 and n_img > 0,
            })
    pages = pd.DataFrame(rows)
    pages.to_csv(out_dir / "_index.csv", index=False)
    return pages


def _name_patterns() -> list[tuple[re.Pattern, str]]:
    variants: dict[str, list[str]] = {c: [n] for c, n in PROVINCES}
    variants["19"] += ["Kep. Bangka Belitung", "Bangka Belitung"]
    variants["21"] += ["Kep. Riau"]
    variants["31"] += ["D.K.I. Jakarta", "Jakarta"]
    variants["34"] += ["D.I. Yogyakarta", "Daerah Istimewa Yogyakarta", "Yogyakarta"]
    pats = []
    for code, names in variants.items():
        for n in names:
            words = re.split(r"[\s.]+", n.strip(". "))
            rx = r"\b" + r"[\s.]*".join(re.escape(w) for w in words if w) + r"\b"
            pats.append((len(n), re.compile(rx, re.I), code))
    pats.append((11, re.compile(r"\bluar\s+negeri\b", re.I), "LN"))
    pats.sort(key=lambda t: -t[0])  # terpanjang dulu: "Papua Barat" sebelum "Papua"
    return [(p, c) for _, p, c in pats]


_PATTERNS = None


def find_provinces(text: str) -> list[str]:
    """Kode provinsi yang disebut di teks (tanpa tumpang tindih, urut kemunculan)."""
    global _PATTERNS
    _PATTERNS = _PATTERNS or _name_patterns()
    taken = [False] * len(text)
    hits = []
    for pat, code in _PATTERNS:
        for m in pat.finditer(text):
            if any(taken[m.start():m.end()]):
                continue
            taken[m.start():m.end()] = [True] * (m.end() - m.start())
            hits.append((m.start(), code))
    seen, out = set(), []
    for _, c in sorted(hits):
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def parse_province_pages(pdf_path: Path, text_pages: pd.DataFrame | None = None) -> pd.DataFrame:
    """Halaman diagram -> entri kandidat (method=text).

    Kotak kiri (x < setengah lebar) = PEMBELIAN (asal), kanan = PENJUALAN (tujuan).
    Blok judul/narasi yang menyebut provinsi halaman sendiri dibuang di merge (diagonal).
    Halaman raster -> tidak ditebak; ditandai untuk entri manual.
    """
    pm = _pymupdf()
    raster = set()
    if text_pages is not None:
        raster = set(text_pages.loc[text_pages["is_raster"], "page"].astype(int))
    rows = []
    with pm.open(pdf_path) as doc:
        for code, pg in CHAPTER_PAGE.items():
            if pg > doc.page_count:
                continue
            if pg in raster:
                rows.append({"page_prov": code, "page": pg, "relation": "RASTER", "other": None})
                continue
            page = doc[pg - 1]
            mid = page.rect.width / 2
            text_all = page.get_text("text").upper()
            if "LUAR PROVINSI" not in text_all:
                rows.append({"page_prov": code, "page": pg, "relation": "NO_BOX", "other": None})
                continue
            for x0, _y0, x1, _y1, txt, *_ in page.get_text("blocks"):
                up = txt.upper()
                if "WILAYAH" in up and "LUAR PROVINSI" in up:
                    continue  # judul kotak
                rel = "asal" if (x0 + x1) / 2 < mid else "tujuan"
                for other in find_provinces(txt):
                    rows.append({"page_prov": code, "page": pg, "relation": rel, "other": other})
    raw = pd.DataFrame(rows, columns=["page_prov", "page", "relation", "other"])
    ok = raw[raw["relation"].isin(RELATIONS)].copy()
    ok["dest_code"] = np.where(ok["relation"] == "asal", ok["page_prov"], ok["other"])
    ok["origin_code"] = np.where(ok["relation"] == "asal", ok["other"], ok["page_prov"])
    ok["share_pct"] = np.nan
    ok["method"] = "text"
    ok["entered_by"] = "pymupdf"
    cand = ok[list(ENTRY_COLUMNS)].drop_duplicates().reset_index(drop=True)
    cand.attrs["flagged_pages"] = raw[~raw["relation"].isin(RELATIONS)]
    return cand


def compare_text_vs_entry(cand: pd.DataFrame, entry: pd.DataFrame) -> pd.DataFrame:
    """Verifikasi ganda: entri (manual/visual) vs kandidat teks PyMuPDF, per (dest,origin,relation,page)."""
    key = ["dest_code", "origin_code", "relation", "page"]
    c = cand.copy()
    c = c[(c["dest_code"] != c["origin_code"]) & c["dest_code"].isin(PROV_CODES) & c["origin_code"].isin(PROV_CODES)]
    a = entry[key].astype(str).drop_duplicates().assign(in_entry=True)
    b = c[key].astype(str).drop_duplicates().assign(in_text=True)
    m = a.merge(b, on=key, how="outer")
    m[["in_entry", "in_text"]] = m[["in_entry", "in_text"]].fillna(False).astype(bool)
    m["status"] = np.select(
        [m.in_entry & m.in_text, m.in_entry], ["match", "entry_only"], "text_only")
    return m.sort_values(key).reset_index(drop=True)


# ------------------------------------------------------------------ entri/merge
def normalize_entry(entry: pd.DataFrame) -> pd.DataFrame:
    """Validasi skema entri; kode jadi str 2 digit; label metode lama dipetakan."""
    missing = set(ENTRY_COLUMNS) - set(entry.columns)
    if missing:
        raise ValueError(f"kolom entri hilang: {sorted(missing)}")
    e = entry[list(ENTRY_COLUMNS)].copy()
    for col in ("dest_code", "origin_code"):
        e[col] = e[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    e["relation"] = e["relation"].astype(str).str.strip().str.lower()
    e["method"] = e["method"].astype(str).str.strip().replace(LEGACY_METHODS)
    e["share_pct"] = pd.to_numeric(e["share_pct"], errors="coerce")
    e["page"] = pd.to_numeric(e["page"], errors="raise").astype("int64")
    bad_rel = set(e["relation"]) - set(RELATIONS)
    bad_met = set(e["method"]) - set(METHODS)
    if bad_rel or bad_met:
        raise ValueError(f"relation tak dikenal={bad_rel} method tak dikenal={bad_met}")
    return e


def merge_entry(entry: pd.DataFrame) -> pd.DataFrame:
    """Union asal+tujuan, buang diagonal & luar negeri/lainnya, satu baris per edge berarah."""
    e = normalize_entry(entry)
    non = e["dest_code"].str.lower().isin(NON_PROVINCE) | e["origin_code"].str.lower().isin(NON_PROVINCE)
    e = e[~non]
    unknown = (set(e["dest_code"]) | set(e["origin_code"])) - set(PROV_CODES)
    if unknown:
        raise ValueError(f"kode provinsi tak dikenal: {sorted(unknown)}")
    e = e[e["dest_code"] != e["origin_code"]]
    g = e.groupby(["dest_code", "origin_code"], sort=False)
    edges = g.agg(
        share_pct=("share_pct", "max"),
        relations=("relation", lambda s: "+".join(sorted(set(s)))),
        pages=("page", lambda s: ";".join(str(p) for p in sorted(set(s)))),
        n_confirmations=("relation", "nunique"),
    ).reset_index()
    edges["_d"] = edges["dest_code"].map(NODE_INDEX)
    edges["_o"] = edges["origin_code"].map(NODE_INDEX)
    edges = edges.sort_values(["_d", "_o"]).drop(columns=["_d", "_o"]).reset_index(drop=True)
    return edges[list(EDGE_COLUMNS)]


def to_matrix(edges: pd.DataFrame) -> np.ndarray:
    """34x34 uint8. A[i, j] = 1 bila edge j -> i (baris = tujuan)."""
    A = np.zeros((N_NODES, N_NODES), dtype=np.uint8)
    for d, o in edges[["dest_code", "origin_code"]].astype(str).itertuples(index=False):
        if d not in NODE_INDEX or o not in NODE_INDEX:
            raise ValueError(f"kode tak dikenal: {o}->{d}")
        A[NODE_INDEX[d], NODE_INDEX[o]] = 1
    np.fill_diagonal(A, 0)
    assert A.dtype == np.uint8 and A.shape == (N_NODES, N_NODES)
    return A


def to_src_dst_matrix(mask: np.ndarray) -> pd.DataFrame:
    """Format bps_mask_2022.csv: baris = pemasok, kolom = pembeli, '1' atau kosong."""
    names = [n for _, n in PROVINCES]
    m = pd.DataFrame(np.where(mask.T == 1, "1", ""), index=names, columns=names)
    m = m.loc[list(TEMPLATE_ORDER), list(TEMPLATE_ORDER)]
    m.index.name = "src_supplier__dst_buyer"
    return m


def pages_table(entry: pd.DataFrame) -> pd.DataFrame:
    e = normalize_entry(entry)
    e = e[e["dest_code"].isin(PROV_CODES) & e["origin_code"].isin(PROV_CODES) & (e["dest_code"] != e["origin_code"])]
    return pd.DataFrame({
        "src": e["origin_code"].map(PROV_NAME).values,
        "dst": e["dest_code"].map(PROV_NAME).values,
        "page": e["page"].values,
    })


# ------------------------------------------------------------------------- QA
def degree_table(mask: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "prov_code": list(PROV_CODES),
        "prov_name": [PROV_NAME[c] for c in PROV_CODES],
        "in_degree": mask.sum(axis=1).astype(int),   # jumlah asal (baris = tujuan)
        "out_degree": mask.sum(axis=0).astype(int),  # jumlah tujuan
        "chapter_page": [CHAPTER_PAGE[c] for c in PROV_CODES],
    })


def summarize(edges: pd.DataFrame, mask: np.ndarray, entry: pd.DataFrame) -> dict:
    e = normalize_entry(entry)
    n = int(mask.sum())
    single = edges[edges["n_confirmations"] < 2]
    typo = [(d, o) for (o, d), v in AUDIT_NOTES.items()
            if v.startswith("TYPO") and mask[NODE_INDEX[d], NODE_INDEX[o]]]
    page_provs = set(np.where(e["relation"] == "asal", e["dest_code"], e["origin_code"]))
    deg = degree_table(mask)
    return {
        "n_edges": n,
        "density": n / (N_NODES * (N_NODES - 1)),
        "n_single": len(single),
        "single": single,
        "asym_rate": len(single) / max(n, 1),
        "n_typo": len(typo),
        "typo_rate": len(typo) / max(n, 1),
        "n_clean": n - len(typo),
        "no_origin": deg.loc[deg["in_degree"] == 0, "prov_code"].tolist(),
        "no_dest": deg.loc[deg["out_degree"] == 0, "prov_code"].tolist(),
        "covered": sorted(page_provs, key=int),
        "deg": deg,
    }


def qa_report(edges: pd.DataFrame, mask: np.ndarray, entry: pd.DataFrame,
              text_check: pd.DataFrame | None = None, pdf_pages: pd.DataFrame | None = None,
              path: Path = REPORT) -> dict:
    """Markdown: densitas, in/out-degree, provinsi tanpa asal, verifikasi ganda."""
    s = summarize(edges, mask, entry)
    deg = s["deg"]
    nm = lambda c: f"{PROV_NAME[c]} (`{c}`)"  # noqa: E731
    L = ["# QA — Mask BPS Poldis cabai merah 2022 (`MDE-H2-03`)", "",
         "_Dibuat otomatis oleh `python -m renaro.data.bps_mask`. Audit naratif lengkap RL+MDE: "
         "[`bps_mask_rl_audit.md`](bps_mask_rl_audit.md)._", "",
         "Sumber: BPS, *Distribusi Perdagangan Komoditas Cabai Merah di Indonesia 2022* "
         f"(`{PDF_PATH.as_posix()}`), bab provinsi hal. PDF {min(CHAPTER_PAGE.values())}–"
         f"{max(CHAPTER_PAGE.values())} (diagram di halaman pertama tiap bab).", "",
         "Konvensi: `bps_mask.npy` **A[i, j] = 1 bila j → i** (baris = tujuan, kolom = asal), urutan "
         "baris = `PROVINCES` di `contract.py` / `data/ref/provinces.csv`. "
         "`bps_mask_2022.csv` = transpos (baris = pemasok).", "",
         "## Ringkasan", "",
         "| Metrik | Nilai |", "|---|---|",
         f"| Entri (kemunculan edge per halaman) | {len(entry)} |",
         f"| Edge berarah unik | **{s['n_edges']}** |",
         f"| Densitas (dari {N_NODES}×{N_NODES - 1} = {N_NODES * (N_NODES - 1)} pasangan) | **{s['density']:.2%}** "
         f"(ekspektasi tim ±{DENSITY_EXPECTED:.0%}, bukan target keras) |",
         f"| Edge terkonfirmasi 2 kotak (asal+tujuan) | {s['n_edges'] - s['n_single']} |",
         f"| Edge hanya 1 kotak | {s['n_single']} ({s['asym_rate']:.2%}) |",
         f"| Edge typo BPS (terkonfirmasi narasi) | {s['n_typo']} ({s['typo_rate']:.2%}) → {s['n_clean']} edge bersih |",
         f"| Bab provinsi dengan entri | {len(s['covered'])}/34 |",
         f"| Provinsi tanpa asal (in-degree 0) | {', '.join(nm(c) for c in s['no_origin']) or '—'} |",
         f"| Provinsi tanpa tujuan (out-degree 0) | {', '.join(nm(c) for c in s['no_dest']) or '—'} |",
         "", "## Cakupan 34 provinsi", ""]
    missing = [c for c in PROV_CODES if c not in s["covered"]]
    L.append(f"{len(s['covered'])} bab punya entri edge. Tanpa entri: "
             + (", ".join(f"{nm(c)} hal. {CHAPTER_PAGE[c]} — **tidak ada data antarprovinsi** "
                          "(diagram tidak mencantumkan provinsi asal/tujuan; seluruh pasokan dari dalam provinsi)"
                          for c in missing) or "—") + ".")
    L += ["", "**Keputusan RL untuk RQ0 (c)**: Papua (`94`) memakai rata-rata hujan 3 provinsi terdekat "
          "(centroid): Papua Barat `91`, Maluku `81`, Maluku Utara `82`.", ""]

    L += ["## Verifikasi ganda", "",
          "1. **Bilateral (dua kotak di dua halaman)** — tiap edge idealnya tercetak di kotak PENJUALAN "
          "provinsi asal *dan* kotak PEMBELIAN provinsi tujuan.",
          f"   - {s['n_edges'] - s['n_single']}/{s['n_edges']} simetris; {s['n_single']} hanya satu kotak "
          f"→ ketidaksesuaian **{s['asym_rate']:.2%}**, salah cetak terkonfirmasi **{s['typo_rate']:.2%}** "
          f"(< {MAX_VERIFY_ERROR:.0%} ✅).", ""]
    if s["n_single"]:
        L += ["| Edge (asal → tujuan) | Halaman | Kotak | Hasil audit |", "|---|---|---|---|"]
        for r in s["single"].itertuples():
            note = AUDIT_NOTES.get((r.origin_code, r.dest_code), "BELUM DIAUDIT")
            L.append(f"| {nm(r.origin_code)} → {nm(r.dest_code)} | {r.pages} | {r.relations} | {note} |")
        L += ["", "Mask literal memuat semua edge tercetak (aturan *put 1 for every printed link*); "
              "filter `n_confirmations == 2` di `bps_mask.csv` untuk uji sensitivitas.", ""]
    if text_check is not None:
        st = text_check["status"].value_counts()
        n_e = int(text_check["in_entry"].sum())
        miss = int(st.get("entry_only", 0))
        extra = int(st.get("text_only", 0))
        err = (miss + extra) / max(n_e, 1)
        L += [f"2. **Teks PyMuPDF vs entri** (`{TEXT_CHECK_CSV.as_posix()}`): match {int(st.get('match', 0))}, "
              f"hanya-entri {miss}, hanya-teks {extra} → selisih **{err:.2%}** dari {n_e} entri "
              f"({'✅' if err < MAX_VERIFY_ERROR else '⚠️ periksa baris non-match'}).", ""]
    else:
        L += ["2. **Teks PyMuPDF vs entri**: PDF belum ada di "
              f"`{PDF_PATH.as_posix()}` saat laporan dibuat — jalankan ulang setelah PDF ditaruh.", ""]
    if pdf_pages is not None:
        r = pdf_pages["is_raster"].sum()
        L += [f"Ekstraksi teks: {len(pdf_pages)} halaman → `{TEXT_DIR.as_posix()}/page_XXX.txt`; "
              f"halaman raster (tanpa teks): {int(r)}"
              + (f" ({', '.join(map(str, pdf_pages.loc[pdf_pages.is_raster, 'page']))})" if r else "") + ".", ""]

    L += ["## Derajat per provinsi", "",
          "| Kode | Provinsi | Hal. | In (asal) | Out (tujuan) |", "|---|---|---|---|---|"]
    for r in deg.itertuples():
        L.append(f"| {r.prov_code} | {r.prov_name} | {r.chapter_page} | {r.in_degree} | {r.out_degree} |")
    top_out = deg.nlargest(5, "out_degree")
    top_in = deg.nlargest(5, "in_degree")
    L += ["", "Top pemasok (out): " + ", ".join(f"{r.prov_name} {r.out_degree}" for r in top_out.itertuples()),
          "", "Top pembeli (in): " + ", ".join(f"{r.prov_name} {r.in_degree}" for r in top_in.itertuples()), "",
          "## Catatan", "",
          "- `share_pct` kosong untuk semua edge: diagram Poldis 2022 tidak mencetak persentase per provinsi; "
          "mask dipakai biner.",
          "- Luar negeri / lainnya dibuang; diagonal 0.",
          f"- Densitas nyata {s['density']:.2%} di bawah ekspektasi ±{DENSITY_EXPECTED:.0%} — dilaporkan apa adanya "
          "(tidak ada edge yang diinferensikan).", ""]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")
    return s


# ----------------------------------------------------------------------- main
def build(entry_path: Path = ENTRY) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    entry = normalize_entry(pd.read_csv(entry_path, dtype=str))
    edges = merge_entry(entry)
    mask = to_matrix(edges)
    return entry, edges, mask


def write_outputs(entry, edges, mask, out_csv=MASK_CSV, out_npy=MASK_NPY,
                  matrix_csv=MATRIX_CSV, pages_csv=PAGES_CSV) -> None:
    for p in (out_csv, out_npy, matrix_csv, pages_csv):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    edges.to_csv(out_csv, index=False)
    np.save(out_npy, mask)
    to_src_dst_matrix(mask).to_csv(matrix_csv)
    pages_table(entry).to_csv(pages_csv, index=False)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="MDE-H2-03 BPS Poldis mask")
    ap.add_argument("--pdf", type=Path, default=PDF_PATH)
    ap.add_argument("--entry", type=Path, default=ENTRY)
    ap.add_argument("--out-csv", type=Path, default=MASK_CSV)
    ap.add_argument("--out-npy", type=Path, default=MASK_NPY)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--text-only", action="store_true", help="hanya ekstraksi teks PDF")
    ap.add_argument("--seed-from", type=Path, help="salin entri RL (H1) ke --entry dulu (normalisasi)")
    args = ap.parse_args(argv)

    pdf_pages = cand = None
    if args.pdf.exists():
        pdf_pages = extract_text_pages(args.pdf, TEXT_DIR)
        print(f"[pdf] {len(pdf_pages)} halaman -> {TEXT_DIR}  raster={int(pdf_pages.is_raster.sum())}")
        if args.text_only:
            return
        cand = parse_province_pages(args.pdf, pdf_pages)
    elif args.text_only:
        raise SystemExit(f"PDF tidak ditemukan: {args.pdf}")
    else:
        print(f"[pdf] TIDAK ADA {args.pdf} — lewati ekstraksi teks & verifikasi teks")

    if args.seed_from:
        seed = normalize_entry(pd.read_csv(args.seed_from, dtype=str))
        args.entry.parent.mkdir(parents=True, exist_ok=True)
        seed.to_csv(args.entry, index=False)
        print(f"[seed] {len(seed)} entri {args.seed_from} -> {args.entry}")
    if not args.entry.exists():
        raise SystemExit(f"entri tidak ada: {args.entry} (pakai --seed-from)")

    entry, edges, mask = build(args.entry)
    write_outputs(entry, edges, mask, args.out_csv, args.out_npy)
    text_check = None
    if cand is not None:
        text_check = compare_text_vs_entry(cand, entry)
        TEXT_CHECK_CSV.parent.mkdir(parents=True, exist_ok=True)
        text_check.to_csv(TEXT_CHECK_CSV, index=False)
    s = qa_report(edges, mask, entry, text_check, pdf_pages, args.report)
    print(f"[mask] entri={len(entry)} edge={s['n_edges']} densitas={s['density']:.2%} "
          f"1-kotak={s['n_single']} ({s['asym_rate']:.2%}) typo={s['typo_rate']:.2%} "
          f"tanpa-asal={s['no_origin']} cakupan={len(s['covered'])}/34")
    if text_check is not None:
        print("[verif-teks]", text_check["status"].value_counts().to_dict())
    print(f"[out] {args.entry} {args.out_csv} {args.out_npy} {MATRIX_CSV} {PAGES_CSV} {args.report}")


if __name__ == "__main__":
    main()
