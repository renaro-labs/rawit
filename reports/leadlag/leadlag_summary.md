# CGS-H4-02 — Diagnostik lead-lag hujan asal → harga

Diagnostik memakai 99 edge BPS dan 4,472 uji korelasi pada data latih O3 (≤ 2024-06-30); 0 uji signifikan q<0.05 (BH-FDR).
Tidak ada uji yang lolos q<0.05 setelah BH-FDR; korelasi terkuat adalah 35->73 (neutral, lag 11, r=0.528, q=0.1488) dan masih deskriptif.
Analisis dipisah per fase ENSO (El Niño/La Niña/netral) dan asal kering vs tidak, dengan lag 0–12 pentad.
Hasil ini adalah dependensi prediktif, bukan bukti arus pasokan fisik; interpretasi kausal memerlukan validasi tambahan.
Output lengkap: `leadlag_edges.csv`, `leadlag_peak.csv`, `fig_peak_lag_hist.png`, dan `fig_top_edges.png`; hanya data latih, tanpa holdout.
