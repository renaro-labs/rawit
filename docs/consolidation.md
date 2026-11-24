# Konsolidasi Repo — Satu Versi Kanonik (2026-11-24)

Dokumen ini mencatat konsolidasi kerja Sprint 1 ke **satu** repositori kanonik:
`D:\renaro\rawit` → GitHub `renaro-labs/rawit` (`main`).

Tujuan: tidak ada lagi dua versi pekerjaan CGS/MDE/MLE/RL yang tersebar di
folder lokal dan branch yang berbeda.

## 1. Sumber kebenaran

| Kebutuhan | Path kanonik |
|---|---|
| Kode pipeline iklim CGS | `src/renaro/climate/`, `src/renaro/contract.py` |
| Kode data MDE | `src/renaro/data/` (`pihps.py`, `pihps_parse.py`, `sp2kp.py`, `coverage.py`) |
| Kode evaluasi & baseline MLE | `src/renaro/eval/`, `src/renaro/baselines/`, `src/renaro/synth/` |
| Kontrak data | `docs/data_contract.md`, `configs/global.yaml` |
| Protokol evaluasi terkunci | `docs/eval_protocol_v1.md` (+ `.tex`), tag `protocol-v1` |
| Playbook Sprint 1 | `docs/playbook/` |
| Laporan QA | `reports/qa/` |
| Materi GIS CGS | `docs/gis/` |
| Spesifikasi API BPS | `docs/sources/bps_openapi.yaml` |
| Data mentah (tidak di-commit) | `data/raw/` |
| Data antara (tidak di-commit) | `data/interim/` |
| Holdout tersegel | `D:\renaro_sealed\holdout_v1\` |

## 2. Yang dipindahkan dari `D:\renaro\supplychain`

`supplychain` adalah folder kerja prototipe (bukan repo Git). Yang masih
relevan sudah disalin ke `rawit`:

| Dari `supplychain/` | Ke `rawit/` | Catatan |
|---|---|---|
| `sprint1_playbook/*.md` | `docs/playbook/*.md` | Spesifikasi tugas H1–H7 yang dirujuk task board |
| `docs/gis/Materi_GIS_Dasar_CGS.{tex,pdf}` | `docs/gis/` | Materi pelatihan GIS untuk CGS |
| `docs/bps_openapi.yaml` | `docs/sources/bps_openapi.yaml` | Spesifikasi API BPS untuk MDE/CGS |
| `result/CGS-H1-01/*`, `output/reports/qa/*` | `reports/qa/` | Sudah ada versi yang lebih baru di `rawit` |
| `data/raw/chirps_v3/`, `data/raw/{boundaries,enso,bps}` | `data/raw/` | Sudah ada dan terverifikasi di `rawit` (1.08 GB CHIRPS) |
| `scripts/cgs/*` (prototipe) | `scripts/cgs/` | Sudah digantikan versi `rawit` |

## 3. Yang sengaja **tidak** dipindahkan (usang)

Folder `D:\renaro\supplychain` **tidak dihapus**, tetapi bukan sumber kebenaran
lagi. Isi yang usang:

- `src/climgnn/` — prototipe model lama; sudah digantikan `src/renaro/` dan
  baseline di `src/renaro/baselines/`.
- `scripts/renaro_data/`, `scripts/build_dataset.py`, `scripts/fetch_*.py` —
  pipeline prototipe; fungsinya sudah ada di `src/renaro/` + `scripts/cgs/`.
- `handout_sprint1/` — scaffolding awal per tugas; implementasi final ada di
  `src/` dan `scripts/`.
- `experiments/{rq0,lag_recovery,robustness,benchmark}.py` — eksperimen awal;
  akan dihidupkan kembali pada H3–H5 dengan kode `rawit`.
- `data/processed/dataset_v1/` — dataset prototipe. Dataset v1 final dibangun
  ulang lewat MDE-H3-01 dari `data/raw/` di `rawit`.
- `dist/`, `output/`, `runs/`, `pips/`, `pihps/` — artefak lokal, tidak masuk git.

Jika suatu saat ada file dari `supplychain` yang dibutuhkan, ambil dari folder
tersebut lalu pindahkan ke path kanonik di atas — jangan menambah salinan baru.

## 4. Pembersihan duplikat di `rawit`

- `environment..yml` dihapus (duplikat persis `environment.yml`).
- `release_lag_probe_temp.py` dihapus (menimpa `reports/qa/chirps_release_lag_probe.csv`
  dengan subset 2 URL — berbahaya bila dijalankan).
- `rain_plot_temp.py` dirapikan menjadi `scripts/cgs/plot_rain_seasonal.py`
  dan figur hasilnya `reports/qa/fig_rain_seasonal.png`.
- Lockfile dipertahankan sesuai MLE-H0-01: `environment.yml`,
  `environment.lock.yml`, `requirements.txt`, `requirements.lock.txt`.

## 5. Branch

Per 2026-11-24, branch pekerjaan sudah di-merge ke `main`:

- `mle` → `main` (MLE H1: loader, generator sintetis, harness rolling-origin)
- `mde` → `main` (MDE H1: PIHPS, SP2KP, laporan cakupan)
- `job/CGS-H1`, `job/CGS-H2` sudah tidak memiliki commit unik (sudah di `main`).

Aturan ke depan: satu branch per job (`job/<JOB-ID>`), merge ke `main` setelah
audit. `main` adalah satu-satunya versi yang dipakai untuk Gate 1–3.

## 6. Verifikasi setelah konsolidasi

```powershell
cd D:\renaro\rawit
$env:PYTHONPATH = "$PWD\src"
python -m pytest tests -q
python scripts\cgs\verify_h1.py --root .
python scripts\cgs\verify_cgs_h2.py
```

Hasil terakhir: seluruh test hijau, CGS H1 587/587 check PASS, CGS H2 37/37
check PASS.
