"""Uji mask BPS Poldis 2022 (MDE-H2-03)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renaro.contract import N_NODES, NODE_INDEX, PROV_CODES
from renaro.data import bps_mask as B

ENTRY = B.ENTRY
NPY = B.MASK_NPY

need_outputs = pytest.mark.skipif(
    not (ENTRY.exists() and NPY.exists()),
    reason="jalankan dulu: python -m renaro.data.bps_mask",
)

#: 3 edge known dari PDF (origin -> dest, halaman PDF tempat tercetak).
KNOWN_EDGES = [
    ("11", "13", "45;53"),   # Aceh -> Sumatera Barat: kotak penjualan Aceh hal.45 + pembelian Sumbar hal.53
    ("33", "12", "49;93"),   # Jawa Tengah -> Sumatera Utara: hal.49 (Sumut) + hal.93 (Jateng)
    ("35", "64", "101;133"),  # Jawa Timur -> Kalimantan Timur: hal.101 (Jatim) + hal.133 (Kaltim)
]
#: Arah sebaliknya TIDAK tercetak di PDF.
KNOWN_ABSENT = [("13", "11"), ("12", "33"), ("64", "35")]


def _e(rows):
    return pd.DataFrame(rows, columns=list(B.ENTRY_COLUMNS))


# ------------------------------------------------------------- logika (tanpa data)
def test_merge_union_diag_foreign_and_max_share():
    entry = _e([
        ["13", "11", None, "tujuan", 45, "text", "t"],
        ["13", "11", 30.0, "asal", 53, "text", "t"],
        ["13", "11", 55.0, "asal", 53, "manual", "t"],
        ["13", "13", None, "asal", 53, "text", "t"],        # diagonal
        ["13", "LN", None, "asal", 53, "text", "t"],        # luar negeri
        ["lainnya", "11", None, "tujuan", 45, "text", "t"],  # lainnya
    ])
    edges = B.merge_entry(entry)
    assert len(edges) == 1
    r = edges.iloc[0]
    assert (r.dest_code, r.origin_code) == ("13", "11")
    assert r.share_pct == 55.0 and r.relations == "asal+tujuan" and r.pages == "45;53"
    assert r.n_confirmations == 2


def test_unknown_code_and_bad_relation_fail_loud():
    with pytest.raises(ValueError):
        B.merge_entry(_e([["13", "77", None, "asal", 53, "text", "t"]]))
    with pytest.raises(ValueError):
        B.merge_entry(_e([["13", "11", None, "pembelian", 53, "text", "t"]]))


def test_matrix_orientation_row_is_destination():
    edges = B.merge_entry(_e([["13", "11", None, "asal", 53, "text", "t"]]))
    A = B.to_matrix(edges)
    assert A.shape == (N_NODES, N_NODES) and A.dtype == np.uint8
    assert A[NODE_INDEX["13"], NODE_INDEX["11"]] == 1   # A[i=tujuan, j=asal]
    assert A[NODE_INDEX["11"], NODE_INDEX["13"]] == 0
    assert A.sum() == 1
    m = B.to_src_dst_matrix(A)                          # baris = pemasok
    assert m.loc["Aceh", "Sumatera Barat"] == "1" and m.loc["Sumatera Barat", "Aceh"] == ""


def test_chapter_pages():
    assert B.CHAPTER_PAGE["11"] == 45 and B.CHAPTER_PAGE["94"] == 177
    assert B.CHAPTER_PAGE["64"] == 133 and B.CHAPTER_PAGE["73"] == 149
    assert len(set(B.CHAPTER_PAGE.values())) == 34


def test_find_provinces_longest_match():
    got = B.find_provinces("PAPUA BARAT\nKEPULAUAN RIAU\nKEP. BANGKA BELITUNG\nDI YOGYAKARTA\nLUAR NEGERI")
    assert got == ["91", "21", "19", "34", "LN"]
    assert B.find_provinces("SULAWESI TENGGARA, SULAWESI SELATAN") == ["74", "73"]


def test_pdf_extract_and_parse_synthetic(tmp_path):
    pm = pytest.importorskip("pymupdf")
    pdf = tmp_path / "mini.pdf"
    doc = pm.open()
    for i in range(1, 50):
        page = doc.new_page(width=600, height=800)
        if i == 45:  # bab Aceh
            page.insert_text((50, 60), "WILAYAH PEMBELIAN DARI LUAR PROVINSI")
            page.insert_text((50, 90), "SUMATERA UTARA")
            page.insert_text((350, 60), "WILAYAH PENJUALAN KE LUAR PROVINSI")
            page.insert_text((350, 90), "SUMATERA BARAT")
            page.insert_text((350, 300), "LUAR NEGERI")
    doc.save(pdf)
    pages = B.extract_text_pages(pdf, tmp_path / "txt")
    assert len(pages) == 49 and (tmp_path / "txt" / "page_045.txt").exists()
    cand = B.parse_province_pages(pdf, pages)
    pairs = set(zip(cand.origin_code, cand.dest_code, cand.relation))
    assert ("12", "11", "asal") in pairs and ("11", "13", "tujuan") in pairs
    edges = B.merge_entry(cand)                         # LN dibuang
    assert set(zip(edges.origin_code, edges.dest_code)) == {("12", "11"), ("11", "13")}


def test_compare_text_vs_entry_survives_dataframe_attrs():
    """Regresi audit H2-03: DataFrame di .attrs membuat astype gagal di pandas 3."""
    entry = _e([["13", "11", None, "tujuan", 45, "text", "t"],
                ["13", "11", None, "asal", 53, "text", "t"]])
    cand = _e([["13", "11", None, "tujuan", 45, "text", "pymupdf"],
               ["12", "11", None, "asal", 45, "text", "pymupdf"]])
    cand.attrs["flagged_pages"] = pd.DataFrame({"page": [177], "relation": ["NO_BOX"]})
    entry.attrs["x"] = pd.DataFrame({"a": [1]})
    m = B.compare_text_vs_entry(cand, entry)
    st = m.set_index(["dest_code", "origin_code", "relation", "page"])["status"]
    assert st[("13", "11", "tujuan", "45")] == "match"
    assert st[("13", "11", "asal", "53")] == "entry_only"
    assert st[("12", "11", "asal", "45")] == "text_only"


def test_parse_attrs_are_plain_python(tmp_path):
    pm = pytest.importorskip("pymupdf")
    pdf = tmp_path / "mini.pdf"
    doc = pm.open()
    for _ in range(49):
        doc.new_page(width=600, height=800)       # semua halaman bab tanpa kotak -> NO_BOX
    doc.save(pdf)
    cand = B.parse_province_pages(pdf, B.extract_text_pages(pdf, tmp_path / "txt"))
    fp = cand.attrs["flagged_pages"]
    assert isinstance(fp, list) and (45, "NO_BOX") in fp
    cand.astype(str)                              # tidak boleh error


def test_split_labels_and_percent_blocks(tmp_path):
    """Layout PDF asli: nama terpecah 2 baris/2 blok dan angka % satu blok dengan nama."""
    pm = pytest.importorskip("pymupdf")
    pdf = tmp_path / "split.pdf"
    doc = pm.open()
    for i in range(1, 50):
        page = doc.new_page(width=780, height=540)
        if i == 45:
            page.insert_text((60, 110), "WILAYAH PEMBELIAN DARI LUAR PROVINSI")
            page.insert_text((70, 200), "NUSA TENGGARA")       # blok 1
            page.insert_text((90, 211), "BARAT")               # blok 2, rapat di bawahnya
            page.insert_text((620, 110), "WILAYAH PENJUALAN KE LUAR PROVINSI")
            page.insert_text((610, 200), "SULAWESI")
            page.insert_text((615, 211), "TENGAH")
            page.insert_text((620, 300), "KALIMANTAN")         # nama di bawah jauh: label lain
            page.insert_text((620, 311), "TIMUR")
            page.insert_textbox(pm.Rect(480, 400, 700, 440), "67,09%\nGORONTALO")
    doc.save(pdf)
    cand = B.parse_province_pages(pdf, B.extract_text_pages(pdf, tmp_path / "t"))
    got = set(zip(cand.origin_code, cand.dest_code, cand.relation))
    assert ("52", "11", "asal") in got                    # bukan "Nusa Tenggara" kosong / Barat salah
    assert {("11", "72", "tujuan"), ("11", "64", "tujuan"), ("11", "75", "tujuan")} <= got
    assert not {o for o, d, r in got if r == "asal"} - {"52"}


# ------------------------------------------------------------- output nyata
@need_outputs
@pytest.mark.parametrize("origin,dest,pages", KNOWN_EDGES)
def test_known_edges_from_pdf(origin, dest, pages):
    A = np.load(NPY)
    assert A[NODE_INDEX[dest], NODE_INDEX[origin]] == 1
    edges = pd.read_csv(B.MASK_CSV, dtype=str)
    row = edges[(edges.origin_code == origin) & (edges.dest_code == dest)]
    assert len(row) == 1 and row.iloc[0].pages == pages and row.iloc[0].n_confirmations == "2"


@need_outputs
@pytest.mark.parametrize("origin,dest", KNOWN_ABSENT)
def test_reverse_direction_not_printed(origin, dest):
    A = np.load(NPY)
    assert A[NODE_INDEX[dest], NODE_INDEX[origin]] == 0


@need_outputs
def test_outputs_consistent():
    entry, edges, A0 = B.build(ENTRY)
    A = np.load(NPY)
    assert A.dtype == np.uint8 and A.shape == (N_NODES, N_NODES)
    assert (A == A0).all() and np.diag(A).sum() == 0
    assert set(np.unique(A)) <= {0, 1}
    assert len(edges) == A.sum() == len(pd.read_csv(B.MASK_CSV))
    m = pd.read_csv(B.MATRIX_CSV, index_col=0, dtype=str).fillna("")
    assert m.shape == (34, 34) and int((m == "1").sum().sum()) == A.sum()
    names = [n for _, n in B.PROVINCES]
    assert list(m.index) == names and list(m.columns) == names          # urutan provinces.csv
    assert ((m.to_numpy() == "1").astype(np.uint8) == A.T).all()        # = npy.T
    assert len(pd.read_csv(B.PAGES_CSV)) == len(entry)


@need_outputs
def test_coverage_and_verification_dod():
    entry, edges, A = B.build(ENTRY)
    s = B.summarize(edges, A, entry)
    # 34 provinsi: punya entri, atau dicatat "tidak ada data" (Papua 94, in=out=0)
    assert set(s["covered"]) | set(s["no_origin"]) == set(PROV_CODES)
    assert s["no_origin"] == ["94"]
    assert s["asym_rate"] < B.MAX_VERIFY_ERROR
    for o, d in B.AUDIT_NOTES:  # semua edge 1-kotak sudah diaudit
        assert A[NODE_INDEX[d], NODE_INDEX[o]] == 1
    single = set(zip(s["single"].origin_code, s["single"].dest_code))
    assert single == set(B.AUDIT_NOTES)
    assert 0.05 < s["density"] < 0.20
