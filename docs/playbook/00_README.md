# Sprint 1 Playbook: Climate-Conditioned Dynamic Graph Learning (Cabai Merah Keriting)

> **Sumber:** `Renaro_Lab_Research_Brief_Climate_GNN_v2.pdf` (23 Nov 2026), Bagian 7–12.
> **Isi dokumen ini:** turunan operasional dari brief v2. Setiap tugas di tabel harian brief dipecah menjadi *job card* yang menyebutkan input, tools, langkah, output konkret (path + skema), kriteria selesai, dan siapa yang memakai output tersebut.
> **Aturan main:** jika playbook ini bertentangan dengan brief v2, **brief v2 yang berlaku**. Nilai bertanda **[usulan default]** tidak ditetapkan di brief. Nilai itu adalah usulan playbook dan wajib dikonfirmasi/dikunci RL di protokol evaluasi (RL-H1-01 / RL-H2-01).

---

## 1. Peta dokumen

| File | Isi | Dibaca oleh |
|---|---|---|
| `00_README.md` | Ringkasan sprint, jadwal per hari, gate, tugas bersama, register output | Semua |
| `01_SETUP_ENV_DAN_KONTRAK.md` | Environment, tools, struktur repo, git, kontrak data (skema semua tabel), konvensi eksperimen, pengaman holdout | Semua (wajib sebelum kickoff) |
| `02_RL_Research_Lead.md` | Job card Research Lead | RL |
| `03_MDE_Market_Data_Engineer.md` | Job card Market Data Engineer | MDE |
| `04_MLE_ML_Graph_Engineer.md` | Job card ML/Graph Modeling Engineer | MLE |
| `05_CGS_Climate_Geospatial.md` | Job card Climate & Geospatial Scientist | CGS |

## 2. Peran

| Kode | Peran | Kepemilikan kunci (brief §9) |
|---|---|---|
| **RL** | Research Lead | Protokol terkunci; keputusan Gate 1–3; laporan |
| **MDE** | Market Data Engineer | Dataset v1; data card; pipeline |
| **MLE** | ML/Graph Modeling Engineer | Kode model, baseline, checkpoint |
| **CGS** | Climate & Geospatial Scientist | Fitur iklim; label regime; **segel holdout** |
| **SEMUA** | Tugas bersama | Kickoff, Gate 2, Gate 3 |

## 3. Konvensi job card

ID job: `<PERAN>-H<hari>-<nomor>`, misalnya `MDE-H1-01`. Tugas bersama memakai `ALL-H<hari>-<nomor>`.

Setiap job card memuat:

- **Mode**: `PARALEL` (boleh jalan sendiri) atau `SEKUENSIAL` (menunggu job lain; ID-nya disebutkan).
- **Input**: file/job yang dibutuhkan.
- **Tools**: library/aplikasi yang dipakai.
- **Langkah**: urutan kerja.
- **Output**: path file, format, dan isi/skema. *Output inilah yang diserahkan; tanpa file di path tersebut, job dianggap belum selesai.*
- **DoD (Definition of Done)**: checklist yang harus terpenuhi.
- **Handoff**: siapa yang memakai output dan untuk job apa.
- **Kalau macet**: fallback.

Setiap job selesai = **1 commit/PR** dengan pesan `[<JOB-ID>] ringkasan`, plus status di kanal tim (lihat §8).

## 4. Jadwal 7 hari (ringkasan job per peran)

Jam kerja diasumsikan 09.00–17.00. Holdout (data ≥ **1 Juni 2026**) **tidak boleh disentuh siapa pun selain CGS** sejak H1, dan baru dibuka H6 pagi.

| Hari | RL | MDE | MLE | CGS |
|---|---|---|---|---|
| **H1** Kickoff & akuisisi | ALL-H1-01 → RL-H1-01 protokol v0 · RL-H1-02 baca full-text | ALL-H1-01 → MDE-H1-01 scrape PIHPS · MDE-H1-02 SP2KP · MDE-H1-03 laporan cakupan | ALL-H1-01 → MLE-H1-01 loader · MLE-H1-02 generator sintetis · MLE-H1-03 harness naive+LightGBM | ALL-H1-01 → CGS-H1-01 unduh CHIRPS · CGS-H1-02 RONI+vintage · CGS-H1-03 produksi kab + batas wilayah |
| **H2** Fitur & prototipe | RL-H2-01 **kunci protokol** · RL-H2-02 tabel positioning | MDE-H2-01 cleaning · MDE-H2-02 kalender · MDE-H2-03 mask BPS | MLE-H2-01 GWN/MTGNN · MLE-H2-02 prototipe Modul 1 | CGS-H2-01 hujan terbobot · CGS-H2-02 indeks pentad · CGS-H2-03 availability · CGS-H2-04 label regime |
| **H3** Integrasi & **Gate 1** | RL-H3-01 review RQ0 · RL-H3-02 **Gate 1** | MDE-H3-01 **merge dataset v1** · MDE-H3-02 draft data card | MLE-H3-01 uji recovery jeda · MLE-H3-02 **RQ0** | (bantu MDE-H3-01) · CGS-H3-02 **segel holdout** |
| **H4** Model data riil | RL-H4-01 draft laporan · RL-H4-02 review run | MDE-H4-01 varian prior · MDE-H4-02 perturbasi | MLE-H4-01 Modul 1 riil · MLE-H4-02 ala RCSGNet · MLE-H4-03 ala MillGNN | CGS-H4-01 split per regime · CGS-H4-02 lead-lag |
| **H5** Ablation & **Gate 2** | RL-H5-01 figur sintetis · RL-H5-02 audit protokol | MDE-H5-01 pipeline 1-perintah · MDE-H5-02 data card final | MLE-H5-01 Modul 2–3 · MLE-H5-02 ablation · MLE-H5-03 paket beku · MLE-H5-04 Modul 4 *(stretch)* | CGS-H5-01 misspesifikasi + joint shift |
| | **ALL-H5-01 Gate 2: bekukan kode/config/seed** | | | |
| **H6** Holdout & analisis | (ikut MLE-H6-01) · ALL-H6-01 tulis | MDE-H6-01 bagian data + QA angka | MLE-H6-01 **analisis** (lead) | CGS-H6-01 **buka holdout 1×** · (ikut MLE-H6-01) |
| **H7** Paket & **Gate 3** | RL-H7-01 integrasi laporan | MDE-H7-01 paket data | MLE-H7-01 paket kode | CGS-H7-01 paket iklim |
| | **ALL-H7-01 Gate 3 + retro + rencana Sprint 2** | | | |

### Jalur kritis (brief §10.4)

```
ALL-H1-01 kickoff → MDE-H1-01 PIHPS → MDE-H2-01 cleaning → MDE-H3-01 dataset v1
→ MLE-H3-02 RQ0 → RL-H3-02 Gate 1 → MLE-H4-01 Modul 1 riil → MLE-H5-01 Modul 2–3
→ ALL-H5-01 Gate 2 → CGS-H6-01 buka holdout → MLE-H6-01 analisis → ALL-H7-01 Gate 3
```

Cabang **CHIRPS (CGS-H1-01 → CGS-H2-01/02 → MDE-H3-01)** hampir kritis (slack ≈ 0). Jalankan unduhan sejak H1 sebelum makan siang.
RL dan MLE punya slack di H1–H2. Bila akuisisi tersendat, mereka membantu MDE/CGS (mis. MLE membantu parsing JSON PIHPS, RL membantu digitasi mask BPS).

## 5. Gate keputusan (brief §10.1)

| Gate | Waktu | Pemutus | Kriteria GO | Jika NO-GO |
|---|---|---|---|---|
| **Gate 1** | H3 16.00 | RL | **Data:** ≥ 20 provinsi dengan cakupan ≥ 90% hari kerja selama ≥ 5 tahun + fitur iklim lengkap. **Sinyal:** model (c) menurunkan MAE vs (b) ≥ 3% rata-rata **dan** konsisten pada ≥ 2/3 origin, **atau** signifikan (DM, p < 0,05) pada ≥ 1 regime. | *Data gagal:* lanjut akuisisi/sumber cadangan (SP2KP), Sprint 1 fokus pipeline. *Sinyal gagal:* jalur benchmark + hasil negatif; Modul 1 tetap diuji tetapi bukan klaim utama. |
| **Gate 2** | H5 16.30 | SEMUA (RL tanda tangan) | Semua baseline wajib + Modul 1 selesai pada split identik; konfigurasi, seed, commit dibekukan; log eksperimen lengkap. | Model yang belum beku **tidak** ikut holdout. |
| **Gate 3** | H7 14.00 | SEMUA (RL putuskan) | Pilih jalur Sprint 2: **A** metode (RQ1 positif di validasi + holdout + lolos uji sintetis); **B** benchmark + temuan empiris; **C** pivot jika data tidak layak. | – |

Template catatan keputusan ada di `02_RL_Research_Lead.md` (lampiran A).

## 6. Tugas bersama (SEMUA)

### ALL-H1-01 · Kickoff + kontrak data
| | |
|---|---|
| Waktu | H1 09.00–11.00 |
| Mode | **SEKUENSIAL**, prasyarat semua job lain |
| Fasilitator | RL (notulen: MDE) |
| Input | Brief v2; `01_SETUP_ENV_DAN_KONTRAK.md` |
| Tools | Git + GitHub (repo privat), editor Markdown, kanal chat tim |

**Langkah**
1. (09.00–09.20) RL membacakan tujuan Sprint 1, cakupan **Wajib** vs **Stretch**, dan hal di luar cakupan (brief §10).
2. (09.20–10.00) Bahas `01_SETUP_ENV_DAN_KONTRAK.md` §5 (kontrak data) tabel per tabel: nama kolom, tipe, unit, kunci, aturan `available_at`. Semua keberatan diselesaikan di sini.
3. (10.00–10.20) Sepakati struktur repo (§3 di file setup), konvensi branch/commit, format run eksperimen (§6), dan pengaman holdout (§7).
4. (10.20–10.40) Putuskan 4 hal terbuka yang memengaruhi semua orang (catat di `docs/decisions/ALL-H1-01.md`):
   - Horizon prediksi **[usulan default: h = 5, 10, 20 hari kerja; utama h = 10]**.
   - Target **[usulan default: log harga level; metrik dihitung dalam Rp/kg setelah inverse]**.
   - Aturan ketersediaan CHIRPS *final* vs *prelim* (lihat CGS-H2-03; RL memutuskan di protokol).
   - Daftar origin rolling-origin **[usulan default di 02_RL §RL-H1-01]**.
5. (10.40–11.00) Setiap orang menjalankan *smoke test* environment (`python scripts/check_env.py`, lihat file setup §2.4) dan melapor ✅/❌.

**Output**
| File | Isi |
|---|---|
| `docs/data_contract.md` | Kontrak data final (salinan §5 file setup + perubahan hasil kickoff), status "v1.0 disepakati" + tanggal |
| `docs/decisions/ALL-H1-01.md` | Keputusan horizon, target, CHIRPS final/prelim, origin |
| Repo GitHub terinisialisasi | Struktur folder, `.gitignore`, `environment.yml`, `configs/global.yaml` |

**DoD**
- [ ] `data_contract.md` di-commit di `main` dan disetujui 4 peran (komentar "OK" di PR).
- [ ] Semua orang lolos smoke test environment.
- [ ] `configs/global.yaml` berisi `holdout_start: 2026-06-01` dan `train_start: 2018-01-02`.

### ALL-H5-01 · Gate 2: pembekuan
| | |
|---|---|
| Waktu | H5 16.00–17.00 |
| Mode | **SEKUENSIAL**, menunggu semua run H5 (MLE-H5-01/02/03, CGS-H5-01, MDE-H5-01) |

**Langkah**
1. MLE menunjukkan `experiments/registry.csv`: setiap model wajib (seasonal naive, LightGBM, GWN, MTGNN, ala RCSGNet, ala MillGNN, Modul 1, Modul 1–3) punya run pada **split identik** dan 5 seed.
2. RL mencocokkan dengan checklist protokol (RL-H5-02).
3. Buat tag git: `git tag -a gate2-freeze -m "Gate 2 freeze"` lalu `git push --tags`.
4. MLE menyerahkan `frozen/manifest.yaml` (daftar model → checkpoint → config → seed → commit) ke CGS.
5. RL menulis `docs/decisions/GATE2.md` (template lampiran A file RL).

**Output:** tag `gate2-freeze`; `frozen/manifest.yaml`; `docs/decisions/GATE2.md`.
**DoD:** [ ] tag ada di remote · [ ] setiap model di manifest punya checksum checkpoint · [ ] model yang tidak lolos dicatat sebagai "dikeluarkan dari holdout".

### ALL-H6-01 · Penulisan per bagian (H6 sore)
Setiap peran menulis bagiannya di `reports/sprint1/` (satu file per bagian, Markdown):
| Peran | File | Isi minimum |
|---|---|---|
| RL | `01_pendahuluan.md`, `02_related_work.md`, `03_metode.md` | dari RL-H4-01, diperbarui |
| MDE | `04_data.md` | dari MDE-H6-01 |
| CGS | `05_iklim_dan_regime.md` | sumber, pembobotan, indeks, definisi regime, availability |
| MLE | `06_eksperimen_dan_hasil.md` | setup, tabel hasil, ablation, sintetis, holdout |

### ALL-H7-01 · Gate 3 + retrospektif + rencana Sprint 2
| | |
|---|---|
| Waktu | H7 14.00–16.30 |
| Mode | **SEKUENSIAL**, menunggu RL-H7-01 (laporan Sprint 1) |

**Langkah**
1. (14.00–14.45) RL presentasi laporan: RQ0–RQ3, batas klaim (AMAN/BERISIKO/JANGAN DIKLAIM, brief §6).
2. (14.45–15.15) Putuskan jalur A/B/C dengan kriteria Gate 3; tulis di `docs/decisions/GATE3.md`.
3. (15.15–15.45) Retrospektif: apa yang berjalan, apa yang macet, estimasi vs aktual per job.
4. (15.45–16.30) Rencana Sprint 2: backlog dari "di luar cakupan" (TFT/TCN, DRAN/SDGF, STEVE, DynaSTar, harga produsen, komoditas pembanding, Modul 4 penuh, node kota) diprioritaskan sesuai jalur.

**Output:** `docs/decisions/GATE3.md`, `docs/retro_sprint1.md`, `docs/sprint2_plan.md`.

## 7. Register output (semua deliverable Sprint 1)

| Output | Path | Pembuat (job) | Pemakai (job) | Tenggat |
|---|---|---|---|---|
| Kontrak data | `docs/data_contract.md` | ALL-H1-01 | semua | H1 11.00 |
| Protokol v0 | `docs/eval_protocol_v0.md` | RL-H1-01 | MLE-H1-03, CGS-H2-04 | H1 17.00 |
| Catatan pembeda paper | `docs/lit/*.md` | RL-H1-02 | RL-H2-02, MLE-H4-02/03 | H1–H2 |
| Protokol v1 **terkunci** | `docs/eval_protocol_v1.md` + tag `protocol-v1` | RL-H2-01 | MLE-H3-02 dst. | H2 17.00 |
| PIHPS mentah | `data/raw/pihps/` | MDE-H1-01 | MDE-H1-03, MDE-H2-01 | H1 17.00 |
| SP2KP mentah | `data/raw/sp2kp/` | MDE-H1-02 | MDE-H2-01 (validasi) | H1 17.00 |
| Laporan cakupan | `reports/qa/coverage_pihps.md` + `.csv` | MDE-H1-03 | RL (Gate 1) | H1 17.00 |
| CHIRPS klip | `data/raw/chirps_v3/*.nc` + `manifest.csv` | CGS-H1-01 | CGS-H2-01 | H2 pagi (2018–2026) |
| RONI | `data/raw/enso/roni.csv` + `roni_vintage_log.csv` | CGS-H1-02 | CGS-H2-03/04 | H1 17.00 |
| Produksi cabai kab | `data/raw/bps/produksi_kab.csv` | CGS-H1-03 | CGS-H2-01, MDE-H4-01 | H1 17.00 |
| Harga bersih | `data/interim/prices_clean.parquet` | MDE-H2-01 | MDE-H3-01 | H2 17.00 |
| Kalender | `data/interim/calendar.csv` | MDE-H2-02 | MDE-H3-01 | H2 17.00 |
| Mask BPS | `data/interim/bps_mask.csv` + `.npy` | MDE-H2-03 | MDE-H3-01, MDE-H4-01, MLE | H2 17.00 |
| Fitur iklim | `data/interim/climate_features.parquet` | CGS-H2-01/02 | MDE-H3-01 | H2 17.00 |
| Tabel ketersediaan | `data/interim/availability.csv` | CGS-H2-03 | MDE-H3-01 (cek bocor) | H2 17.00 |
| Label regime | `data/interim/regime_labels.csv` | CGS-H2-04 | CGS-H4-01, evaluasi | H2 17.00 |
| Generator sintetis | `src/renaro/synth/` | MLE-H1-02 | MLE-H2-02, MLE-H3-01 | H1 17.00 |
| **Dataset v1 (beku)** | `data/processed/dataset_v1/` + `SHA256SUMS` | MDE-H3-01 | MLE-H3-02 dst. | **H3 11.00** |
| Holdout tersegel | di luar repo + `docs/holdout_seal.md` | CGS-H3-02 | CGS-H6-01 | H3 13.00 |
| Tabel RQ0 | `reports/rq0/rq0_results.csv` + `.md` | MLE-H3-02 | RL-H3-02 | H3 15.30 |
| Keputusan Gate 1 | `docs/decisions/GATE1.md` | RL-H3-02 | semua | H3 17.00 |
| Graph prior | `data/processed/graph_priors/` | MDE-H4-01 | MLE-H4-01, CGS-H5-01 | H4 17.00 |
| Set perturbasi | `data/processed/perturbations/` | MDE-H4-02 | CGS-H5-01 | H4 17.00 |
| Split per regime | `data/processed/eval_splits/` | CGS-H4-01 | MLE-H4/H5, MLE-H6-01 | H4 17.00 |
| Checkpoint Modul 1 | `experiments/runs/<run_id>/` | MLE-H4-01 | CGS-H5-01 | H4 17.00 |
| Tabel ablation | `reports/ablation/ablation_val.csv` | MLE-H5-02 | RL, laporan | H5 16.00 |
| Tabel robustness | `reports/robustness/robustness_val.csv` | CGS-H5-01 | laporan | H5 16.00 |
| Paket beku | `frozen/manifest.yaml` + tag `gate2-freeze` | MLE-H5-03 / ALL-H5-01 | CGS-H6-01 | H5 17.00 |
| Prediksi holdout | `reports/holdout/predictions/*.parquet` | CGS-H6-01 | MLE-H6-01 | H6 11.00 |
| Tabel & figur hasil | `reports/holdout/` | MLE-H6-01 | RL-H7-01 | H6 15.00 |
| Laporan Sprint 1 | `reports/sprint1/sprint1_report.md` (+PDF) | RL-H7-01 | ALL-H7-01 | H7 13.00 |
| Paket rilis | `release/` (kode + data turunan, **tanpa** PIHPS mentah) | MDE/MLE/CGS-H7-01 | publik/internal | H7 16.30 |

## 8. Ritme harian

| Waktu | Kegiatan | Format |
|---|---|---|
| 09.00–09.15 (H2–H7) | Stand-up | Tiap orang: selesai kemarin (job ID), rencana hari ini, blocker |
| Setiap job selesai | Post di kanal tim | `✅ [MDE-H2-01] prices_clean.parquet di-commit (abc1234). 31/34 provinsi lolos. Blocker: –` |
| 16.30–16.45 | Sinkron sore | Cek register output §7: apa yang sudah ada di path-nya |
| Kapan pun macet > 1 jam | Eskalasi ke RL | Sebut job ID + apa yang dicoba |

## 9. Aturan emas (berlaku untuk semua job)

1. **Tidak ada kebocoran waktu.** Setiap fitur yang dipakai pada baris tanggal `t` harus punya `available_at ≤ t`. Diuji otomatis di MDE-H3-01 (`tests/test_no_leakage.py`).
2. **Holdout tidak disentuh.** Data ≥ 2026-06-01 tidak dibuka, diplot, atau dihitung statistiknya oleh siapa pun selain CGS sampai H6. Semua loader memfilter berdasarkan `configs/global.yaml:holdout_start`.
3. **Label regime hanya untuk evaluasi.** Tidak boleh masuk sebagai fitur model.
4. **Satu sumber kebenaran.** Semua model membaca `data/processed/dataset_v1/` lewat loader yang sama (MLE-H1-01). Tidak ada CSV "versi pribadi".
5. **Setiap angka di laporan bisa dilacak** ke `run_id` → config → commit.
6. **Data mentah PIHPS tidak diredistribusi** (lisensi tidak terbuka, brief §11). Rilis hanya kode + data turunan/agregat.
7. **Edge = dependensi prediktif**, bukan arus pasokan atau kausalitas. Berlaku di semua tulisan.
