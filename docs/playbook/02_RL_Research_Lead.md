# 02 · RL: Research Lead

> **Tanggung jawab (brief §9):** klaim novelty dan positioning, protokol evaluasi, keputusan gate, penulisan; domain ekonomi pertanian.
> **Kepemilikan kunci:** protokol terkunci (akhir H2); Gate 1–3.
> **Pengaman bias:** protokol dikunci **sebelum** model inti selesai; RL tidak boleh mengubah protokol setelah tag `protocol-v1` kecuali lewat *amendment* tertulis yang menyebut alasan dan dicatat sebelum melihat hasil holdout.

## Ringkasan job

| ID | Hari | Job | Mode | Output utama |
|---|---|---|---|---|
| ALL-H1-01 | H1 pagi | Kickoff + kontrak data (fasilitator) | SEKUENSIAL | `docs/data_contract.md` |
| RL-H1-01 | H1 | Protokol evaluasi v0 | PARALEL | `docs/eval_protocol_v0.md` |
| RL-H1-02 | H1–H2 | Baca full-text RCSGNet, MarketDNA → MillGNN, SDGF, STEVE | PARALEL | `docs/lit/*.md` |
| RL-H2-01 | H2 | Finalisasi + **kunci** protokol | PARALEL (tenggat keras 17.00) | `docs/eval_protocol_v1.md` + tag `protocol-v1` |
| RL-H2-02 | H2 | Tabel positioning | PARALEL | `docs/positioning.md` |
| RL-H3-01 | H3 siang | Review spesifikasi & hasil RQ0 (bersama MLE) | SEKUENSIAL (dataset v1 + protokol) | komentar di `reports/rq0/` |
| RL-H3-02 | H3 sore | **Gate 1** go/no-go | SEKUENSIAL (hasil RQ0) | `docs/decisions/GATE1.md` |
| RL-H4-01 | H4 | Draft pendahuluan, related work, metode | PARALEL | `reports/sprint1/01–03_*.md` |
| RL-H4-02 | H4–H5 | Review run harian | PARALEL | komentar di `experiments/review_log.md` |
| RL-H5-01 | H5 | Figur uji sintetis | PARALEL | `reports/figures/synth_*.png` |
| RL-H5-02 | H5 | Audit kepatuhan protokol | PARALEL | `docs/protocol_audit.md` |
| ALL-H5-01 | H5 akhir | Gate 2 (tanda tangan) | SEKUENSIAL | `docs/decisions/GATE2.md` |
| (MLE-H6-01) | H6 | Ikut analisis holdout | SEKUENSIAL | – |
| RL-H7-01 | H7 | Integrasi laporan Sprint 1 | SEKUENSIAL (tulisan semua peran) | `reports/sprint1/sprint1_report.md` |
| ALL-H7-01 | H7 sore | Gate 3 + retro + rencana Sprint 2 | SEKUENSIAL | `docs/decisions/GATE3.md` |

---

## RL-H1-01 · Protokol evaluasi v0

| | |
|---|---|
| Waktu | H1 11.00–15.00 |
| Mode | PARALEL (setelah ALL-H1-01) |
| Input | Brief v2 §4, §7.2, §8; `docs/decisions/ALL-H1-01.md` |
| Tools | Markdown, Git |
| Handoff | MLE-H1-03 (harness butuh split & metrik), CGS-H2-04 (definisi regime), MDE (aturan cakupan) |

**Langkah**
1. Salin kerangka di bawah ke `docs/eval_protocol_v0.md`.
2. Isi setiap bagian. Bila memakai nilai **[usulan default]**, tulis "diadopsi dari playbook" atau ganti.
3. Kirim tautan PR ke MLE dan CGS sebelum 15.00 untuk umpan balik (tenggat umpan balik: H2 12.00).

**Kerangka isi `eval_protocol_v0.md`**

1. **Tugas prediksi**
   - Target: harga Cabai Merah Keriting, pasar tradisional (`price_type=1`), per provinsi, hari kerja.
   - Horizon *h* **[usulan default: 5, 10, 20 hari kerja; metrik utama h = 10]**.
   - Transformasi target **[usulan default: log(price); metrik dihitung setelah `exp`]**.
   - Panjang jendela input **[usulan default: 60 hari kerja]**.
   - Hanya hari dengan `is_observed = True` yang dievaluasi; target tidak pernah diimputasi.
2. **Node yang dievaluasi:** provinsi lolos kriteria cakupan (dari MDE-H1-03; ≥ 90% hari kerja/tahun).
3. **Split rolling-origin [usulan default]**

   | Origin | Latih | Validasi (early stopping) | Uji |
   |---|---|---|---|
   | O1 | 2018-01-02 – 2022-06-30 | 2022-07-01 – 2022-12-31 | 2023-01-01 – 2023-12-31 |
   | O2 | 2018-01-02 – 2023-06-30 | 2023-07-01 – 2023-12-31 | 2024-01-01 – 2024-12-31 |
   | O3 | 2018-01-02 – 2024-06-30 | 2024-07-01 – 2024-12-31 | 2025-01-01 – 2026-05-31 |
   | **Holdout** | 2018-01-02 – 2025-12-31 (refit beku) | 2026-01-01 – 2026-05-31 | **2026-06-01 – akhir data final** |

   Pastikan ada *gap* sebesar horizon maks antara akhir latih dan awal uji (embargo 20 hari kerja) agar target tidak tumpang-tindih.
   Catatan: O3 memuat El Niño 2023–24 secara parsial di latih dan La Niña 2024–25 di uji. Kontras regime per origin harus dicek CGS (CGS-H4-01).
4. **Regime (evaluasi saja)**, definisi diusulkan CGS (CGS-H2-04), dikunci di v1:
   - ENSO: El Niño / La Niña / netral berdasarkan RONI ±0,5 selama ≥ 5 musim berturut-turut (aturan NOAA).
   - Kering: per provinsi, akumulasi pentad terbobot < persentil ke-20 klimatologi selama ≥ 3 pentad berturut-turut.
   - Hujan ekstrem: akumulasi 5-harian > persentil ke-95 klimatologi provinsi.
   - Normal: bukan satupun di atas.
   - Prioritas label bila tumpang-tindih (mis. kering > ekstrem > ENSO > normal), atau laporkan multi-label.
5. **Model (Sprint 1 wajib):** seasonal naive; LightGBM; Graph WaveNet; MTGNN; regime laten ala RCSGNet; lag graph ala MillGNN (disederhanakan); Modul 1; Modul 1–3. Stretch: Modul 4.
6. **Metrik:** MAE, RMSE, sMAPE; **worst-regime error** = max MAE di antara regime; **perubahan error OOD** = MAE(regime) − MAE(normal) dan rasionya; stabilitas = std MAE antar 5 seed.
7. **Uji statistik:** Diebold–Mariano dengan koreksi Harvey–Leybourne–Newbold, loss absolut, pada deret *rata-rata lintas provinsi per hari* (satu deret per model per horizon), terhadap baseline terbaik di validasi. Lag HAC = h − 1.
8. **RQ0** (spesifikasi untuk MLE-H3-02):
   - (a) LightGBM: lag harga sendiri + kalender.
   - (b) (a) + hujan lokal (fitur iklim provinsi sendiri, jeda pentad 0–8).
   - (c) (b) + hujan **wilayah asal** berjeda: untuk provinsi tujuan *i*, asal = `{j : bps_mask[i, j] = 1}`; agregasi = rata-rata terbobot pangsa BPS (jika ada) atau rata-rata sederhana; jeda pentad 1–8. Provinsi tanpa asal di mask: **[usulan default: 3 provinsi produsen terdekat]**.
   - Hiperparameter LightGBM sama untuk (a)/(b)/(c); tidak ada tuning per varian.
   - Kriteria Gate 1 (sinyal) disalin dari brief §10.1.
9. **Holdout:** dibuka satu kali oleh CGS setelah Gate 2; hanya model di `frozen/manifest.yaml`.
10. **Uji sintetis (RQ1):** metrik recovery jeda (lihat MLE-H3-01); ambang lolos **[usulan default: akurasi argmax-jeda ≥ 0,8 pada edge benar dan korelasi Spearman massa-jeda vs jeda-benar ≥ 0,7 per regime]**.
11. **Robustness (RQ3):** perturbasi drop/add/rewire 10/20/30/40/50% × 3 seed perturbasi; varian tanpa prior; joint shift = perturbasi dievaluasi pada subset regime ekstrem.
12. **Aturan pelaporan:** hasil negatif dilaporkan; hasil OOD per episode dengan interval kepercayaan (bootstrap blok); tidak ada generalisasi dari 1 episode.

**DoD**
- [ ] 12 bagian terisi; tiap nilai default diberi tanda status (diadopsi/diubah).
- [ ] MLE dan CGS sudah diminta review (tag di PR).
- [ ] Split bebas tumpang-tindih (embargo tertulis).

---

## RL-H1-02 · Baca full-text pesaing terdekat → catatan pembeda

| | |
|---|---|
| Waktu | H1 15.00–17.00, lanjut H2 pagi bila perlu |
| Mode | PARALEL |
| Input | Ref. [8] RCSGNet, [9] MarketDNA (akses kampus/Springer), [10] MillGNN, [14] SDGF, [15] STEVE |
| Tools | Zotero, PDF reader, Markdown |
| Handoff | MLE-H4-02 (spesifikasi baseline ala RCSGNet), MLE-H4-03 (ala MillGNN), RL-H2-02 |

**Langkah**
1. Unduh full-text RCSGNet dan MarketDNA; simpan di folder Zotero tim (bukan di repo).
2. Untuk setiap paper buat `docs/lit/<nama>.md` dengan template:
   ```markdown
   # <Nama paper> (ref [n])
   - Data: komoditas, wilayah, frekuensi, periode, jumlah node
   - Graph: statis/dinamis, berarah?, bagaimana dipelajari, ada jeda per edge?
   - Kondisi/regime: laten atau teramati? dari apa diinfer?
   - Input eksogen (cuaca/iklim): ya/tidak, bagaimana
   - Evaluasi: split, baseline, OOD?, metrik
   - Kode tersedia? lisensi?
   - Detail yang perlu ditiru untuk baseline kita (arsitektur, K regime, hiperparameter)
   - Pembeda terhadap studi kita (1–3 kalimat, bisa dikutip di laporan)
   - Risiko: apakah paper ini sudah melakukan hal yang kita klaim?
   ```
3. **Prioritas: RCSGNet.** Brief menyebut penggunaan cuaca/jeda "tidak disebut pada abstrak". Verifikasi di full-text apakah RCSGNet memakai cuaca atau jeda per edge. **Jika ya, segera eskalasi** ke semua peran: klaim AMAN di brief §6 harus direvisi sebelum protokol dikunci.
4. Untuk RCSGNet dan MillGNN, tuliskan spesifikasi *baseline disederhanakan* (bagian "Detail yang perlu ditiru") secukupnya agar MLE bisa mengimplementasikannya tanpa membaca paper.

**Output:** `docs/lit/rcsgnet.md`, `marketdna.md`, `millgnn.md`, `sdgf.md`, `steve.md`.

**DoD**
- [ ] 5 catatan lengkap; kolom "Pembeda" terisi.
- [ ] Status klaim "cuaca/jeda pada RCSGNet" terverifikasi (ya/tidak + kutipan halaman).
- [ ] Spesifikasi baseline ala RCSGNet & MillGNN dikirim ke MLE paling lambat H2 17.00.

**Kalau macet:** full-text tidak bisa diakses → minta lewat perpustakaan/penulis; sementara itu MLE memakai spesifikasi dari abstrak + brief §2 dan keterbatasan ini dicatat di laporan.

---

## RL-H2-01 · Finalisasi dan kunci protokol (v1)

| | |
|---|---|
| Waktu | H2, tenggat **keras 17.00** |
| Mode | PARALEL, tetapi **prasyarat** MLE-H3-02 (RQ0) |
| Input | `eval_protocol_v0.md` + umpan balik MLE/CGS; definisi regime dari CGS-H2-04; hasil RL-H1-02 |
| Tools | Git |
| Handoff | Semua (protokol = hukum sprint) |

**Langkah**
1. Tutup semua komentar review di PR protokol v0.
2. Isi definisi regime final dari CGS (ambang persentil, panjang minimum, aturan prioritas).
3. Konfirmasi keputusan CHIRPS final/prelim untuk `available_at`.
4. Salin ke `docs/eval_protocol_v1.md`, tulis header:
   ```
   Status: TERKUNCI · Tanggal: <H2> · Disetujui: RL, MDE, MLE, CGS
   Perubahan setelah ini hanya lewat docs/protocol_amendments.md
   ```
5. Turunkan nilai protokol ke `configs/global.yaml` (horizon, origin, seed, embargo, holdout_start). Kode **membaca** dari file ini, bukan hard-code.
6. Commit, merge, lalu tag:
   ```powershell
   git tag -a protocol-v1 -m "[RL-H2-01] eval protocol locked"
   git push --tags
   ```
7. Umumkan commit hash di kanal tim.

**Output:** `docs/eval_protocol_v1.md`, `configs/global.yaml` (versi protokol), tag `protocol-v1`.

**DoD**
- [ ] Tag ada di remote; hash diumumkan.
- [ ] `configs/global.yaml` konsisten 100% dengan dokumen (MLE cek silang).
- [ ] Dibuat **sebelum** Modul 1 dijalankan pada data riil.

---

## RL-H2-02 · Tabel positioning vs paper terdekat

| | |
|---|---|
| Waktu | H2 (setelah RL-H1-02) |
| Mode | PARALEL |
| Output | `docs/positioning.md` |

**Langkah**
1. Buat tabel dengan kolom: *Paper · Domain/data · Graph berarah · Graph dinamis · Jeda per edge · Kondisi graph (laten/teramati/tidak ada) · Iklim eksogen · Uji OOD regime · Uji graph prior keliru*.
2. Baris: RCSGNet, MarketDNA, MillGNN, SAMSGL, CRAFormer, DRAN, SDGF, STEVE, CGNN, Min et al. 2025, teh Sri Lanka, **studi ini**.
3. Di bawah tabel tulis 3 kalimat posisi yang konsisten dengan batas klaim brief §6 (AMAN/BERISIKO/JANGAN DIKLAIM).

**DoD:** [ ] baris "studi ini" hanya berisi klaim kategori AMAN · [ ] setiap sel pesaing bersumber dari catatan `docs/lit/` atau abstrak (sebutkan sumbernya).

---

## RL-H3-01 · Review RQ0 (bersama MLE)

| | |
|---|---|
| Waktu | H3 11.00–15.30 |
| Mode | SEKUENSIAL (menunggu `dataset_v1` dari MDE-H3-01 + `protocol-v1`) |
| Input | Kode MLE-H3-02, `reports/rq0/` |

**Langkah**
1. Sebelum run (11.00–11.30): cek spesifikasi fitur (a)/(b)/(c) di kode sesuai protokol §8. Pastikan fitur asal memakai mask BPS di dataset v1 dan tidak ada fitur yang `available_at > t`.
2. Selama run: siapkan template `GATE1.md`.
3. Setelah hasil (15.00–15.30): cek sanity: (a) harus mengalahkan seasonal naive; jika tidak, ada bug. Bandingkan skala MAE dengan level harga (Rp/kg).

**Output:** komentar review di PR `job/MLE-H3-02`.

---

## RL-H3-02 · Gate 1 go/no-go

| | |
|---|---|
| Waktu | H3 15.30–17.00 |
| Mode | SEKUENSIAL (menunggu `reports/rq0/rq0_results.csv` + `reports/qa/coverage_pihps.csv` + QA dataset v1) |
| Output | `docs/decisions/GATE1.md` |

**Langkah**
1. **Kriteria data:** dari laporan cakupan, hitung jumlah provinsi dengan cakupan ≥ 90% hari kerja selama ≥ 5 tahun (2018–2025). Butuh ≥ 20. Cek juga fitur iklim lengkap untuk semua provinsi tersebut (CGS konfirmasi).
2. **Kriteria sinyal:** dari tabel RQ0:
   - Δ MAE (c vs b) rata-rata di 3 origin ≥ 3% **dan** (c) < (b) pada ≥ 2 dari 3 origin; **atau**
   - DM p < 0,05 (c lebih baik dari b) pada ≥ 1 regime.
3. Tentukan hasil: **GO penuh**, **GO-benchmark** (data lolos, sinyal gagal), atau **NO-GO data**.
4. Isi template (lampiran A), umumkan di kanal tim, lalu sesuaikan rencana H4–H7 sesuai tabel "Jika NO-GO" di README §5.

**DoD:** [ ] angka di `GATE1.md` dapat dilacak ke `run_id` · [ ] keputusan diumumkan sebelum 17.00.

---

## RL-H4-01 · Draft pendahuluan, related work, metode

| | |
|---|---|
| Waktu | H4 (sisa waktu di luar RL-H4-02) |
| Mode | PARALEL |
| Output | `reports/sprint1/01_pendahuluan.md`, `02_related_work.md`, `03_metode.md` |

**Isi minimum**
- *Pendahuluan:* masalah (harga cabai antarprovinsi, dependensi berubah mengikuti iklim), RQ0–RQ3, kontribusi berurutan **benchmark → bukti empiris → metode**, scope A, batas (bukan identifikasi kausal).
- *Related work:* diringkas dari `docs/positioning.md`, 4 kelompok sesuai brief §2.
- *Metode:* Modul 1 (rumus $A^{(\ell)}_{ij,t}$ dari brief §5), Modul 2–3 (rumus gate), Modul 4 (stretch), baseline, protokol (ringkasan v1).

**DoD:** [ ] semua klaim novelty memakai frasa "sepengetahuan kami" · [ ] tidak ada klaim kategori JANGAN DIKLAIM.

## RL-H4-02 · Review run harian (H4–H5)

**Langkah (setiap hari 15.00):**
1. Buka `experiments/registry.csv`, cek run baru: `git_sha` bersih, `split_hash` sama dengan dataset v1, 5 seed.
2. Tandai anomali (MAE di bawah seasonal naive secara tidak wajar = indikasi bocor; varians antar seed besar).
3. Catat di `experiments/review_log.md`: tanggal, run_id, temuan, tindakan.

---

## RL-H5-01 · Figur uji sintetis

| | |
|---|---|
| Input | Hasil MLE-H3-01 (`reports/synth/recovery_*.csv`) |
| Tools | matplotlib (atau minta MLE menyiapkan skrip, RL mengurasi) |
| Output | `reports/figures/synth_lag_recovery.png`, `synth_edge_heatmap.png` + caption di `reports/figures/captions.md` |

**Isi figur**
1. Jeda benar vs jeda terpelajari (argmax $\ell$) per edge, dipisah regime iklim sintetis (normal vs kering).
2. Heatmap $A$ benar vs $A$ terpelajari (34×34) untuk 2 regime.
Caption menyebut ambang lolos protokol dan apakah lolos.

## RL-H5-02 · Audit kepatuhan protokol

**Output:** `docs/protocol_audit.md` berisi checklist berikut dengan status ✅/❌ + bukti (path/run_id):

- [ ] Semua run memakai `split_hash` dataset v1 yang sama.
- [ ] Tidak ada fitur dengan `available_at > t` (`tests/test_no_leakage.py` lulus di commit terakhir).
- [ ] Label regime tidak ada di daftar fitur model mana pun (`grep regime` di `configs/models/`).
- [ ] Hiperparameter tidak dituning pada periode uji (hanya validasi).
- [ ] 5 seed untuk tiap model wajib.
- [ ] Tidak ada artefak yang menyentuh tanggal ≥ 2026-06-01 (cek `max(date)` semua `preds.parquet`).
- [ ] Amandemen protokol (jika ada) tercatat sebelum Gate 2.

---

## RL-H7-01 · Integrasi laporan Sprint 1

| | |
|---|---|
| Waktu | H7 09.00–13.00 |
| Mode | SEKUENSIAL (menunggu ALL-H6-01 semua peran) |
| Output | `reports/sprint1/sprint1_report.md` (+ ekspor PDF) |

**Struktur laporan**
1. Ringkasan eksekutif (½ halaman): jawaban RQ0–RQ3 dalam 1 kalimat masing-masing + keputusan Gate 1/2.
2. Pendahuluan · 3. Related work · 4. Data · 5. Iklim & regime · 6. Metode · 7. Eksperimen & hasil (validasi, sintetis, robustness, holdout) · 8. Batas klaim (tabel AMAN/BERISIKO/JANGAN DIKLAIM yang diperbarui berdasarkan hasil) · 9. Rekomendasi jalur Sprint 2.

**DoD**
- [ ] Setiap angka punya rujukan `run_id` (catatan kaki atau tabel lampiran).
- [ ] Hasil negatif ditulis eksplisit.
- [ ] MDE sudah QA semua angka (MDE-H6-01).

---

## Lampiran A · Template catatan keputusan gate

```markdown
# GATE <n>: <tanggal, jam>
Hadir: RL, MDE, MLE, CGS
Commit yang dinilai: <sha>   Dataset: dataset_v1 <hash>

## Kriteria dan bukti
| Kriteria | Ambang | Nilai | Sumber (path/run_id) | Lolos? |
|---|---|---|---|---|

## Keputusan
GO / GO-benchmark / NO-GO / Jalur A|B|C

## Alasan (≤ 5 kalimat)

## Dampak ke rencana
- Job yang berubah: ...
- Job baru: ...

## Risiko yang diterima
```
