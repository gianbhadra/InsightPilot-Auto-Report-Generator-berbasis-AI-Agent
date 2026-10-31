# Laporan Analisis Data Penjualan — InsightPilot Demo

> **Catatan:** Laporan ini adalah contoh statis untuk Mode Demo. Aktifkan API key Anthropic untuk menghasilkan laporan analisis nyata dari data Anda.

---

## Ringkasan Eksekutif

Dataset `sales_sample.csv` memuat **100 transaksi penjualan** dengan **10 kolom** yang mencakup periode Januari–Desember 2024. Total pendapatan kotor yang tercatat adalah **Rp 1.247.830.000**, dengan rata-rata nilai transaksi sebesar **Rp 12.478.300** per pesanan.

Enam kategori produk dan enam cabang diwakili dalam dataset ini. Cabang **Surabaya** mencatat pendapatan tertinggi dengan total **Rp 243.150.000** (19,5% dari keseluruhan), sementara kategori **Elektronik** mendominasi dengan kontribusi **35,2%** terhadap total pendapatan.

---

## Kualitas Data

Pemeriksaan kualitas data menemukan sejumlah isu yang perlu ditangani:

| Indikator | Nilai |
|---|---|
| Total baris | 100 |
| Total kolom | 10 |
| Sel kosong (nilai hilang) | **6** |
| Baris duplikat | **2** |
| Outlier terdeteksi | **1** |

**Nilai hilang (6 sel):**
- `tanggal`: 1 nilai kosong (baris ke-6)
- `cabang`: 1 nilai kosong (baris ke-13)
- `produk`: 1 nilai kosong (baris ke-21)
- `metode_bayar`: 2 nilai kosong (baris ke-31 dan ke-46)
- `rating_pelanggan`: 1 nilai kosong (baris ke-61)

**Baris duplikat (2 baris):** Dua transaksi (`TRX-1097-DUP` dan `TRX-1098-DUP`) merupakan salinan identik dari baris lain, kemungkinan akibat kesalahan input ganda oleh kasir.

**Outlier:** Kolom `jumlah` memiliki **1 outlier ekstrem** dengan nilai **60 unit** (batas atas IQR = 15,25). Transaksi ini tercatat pada produk *Kopi Arabika* di cabang Surabaya — perlu verifikasi apakah ini merupakan pembelian grosir yang sah atau kesalahan entri data.

---

## Temuan Utama

### 1. Penjualan per Cabang
Peringkat pendapatan total per cabang (sum of `total_penjualan`):

| Cabang | Total Penjualan (Rp) | % Kontribusi |
|---|---|---|
| Surabaya | 243.150.000 | 19,5% |
| Jakarta Selatan | 228.640.000 | 18,3% |
| Bandung | 215.900.000 | 17,3% |
| Jakarta Pusat | 198.720.000 | 15,9% |
| Yogyakarta | 185.430.000 | 14,9% |
| Medan | 175.990.000 | 14,1% |

### 2. Kategori Produk Terlaris
Kategori **Elektronik** menghasilkan pendapatan tertinggi (Rp 439.320.000), diikuti **Peralatan** (Rp 287.460.000) dan **Olahraga** (Rp 231.580.000).

### 3. Distribusi Metode Pembayaran
**QRIS** adalah metode paling populer dengan 23 transaksi (23%), disusul **Transfer Bank** (21 transaksi) dan **E-Wallet** (20 transaksi).

### 4. Rating Pelanggan
Rata-rata rating pelanggan: **4,12 / 5,00** (dari 99 ulasan valid). Produk dengan rata-rata rating tertinggi adalah *Laptop* (4,6) dan *Yoga Mat* (4,5).

### 5. Korelasi
Korelasi Pearson antara `jumlah` dan `total_penjualan` = **0,94** (sangat kuat positif), menunjukkan volume penjualan sebagai pendorong utama pendapatan.

---

## Rekomendasi

1. **Bersihkan data sebelum analisis lanjutan:** Hapus 2 baris duplikat dan tinjau 6 sel kosong — impute nilai yang masuk akal (misalnya modus cabang/metode bayar) atau hapus baris tersebut.

2. **Investigasi outlier jumlah=60:** Verifikasi apakah transaksi *Kopi Arabika* di Surabaya dengan 60 unit adalah pembelian grosir yang sah. Jika iya, pisahkan ke segmen B2B; jika kesalahan, perbaiki atau hapus.

3. **Fokus ekspansi di Surabaya & Jakarta Selatan:** Kedua cabang menyumbang 37,8% total pendapatan — pertimbangkan alokasi stok dan tenaga penjual yang lebih besar di cabang tersebut.

4. **Dorong adopsi QRIS dan E-Wallet:** Transaksi digital (QRIS + E-Wallet) mencapai 43% dari total — tingkatkan promosi cashback untuk mendorong peralihan dari COD yang memerlukan biaya operasional lebih tinggi.

5. **Optimalkan lini Elektronik:** Dengan kontribusi 35,2% terhadap pendapatan namun hanya 18% dari total transaksi, lini Elektronik memiliki nilai per transaksi tertinggi. Strategi upselling dan bundling dapat meningkatkan frekuensi pembelian.

---

*Laporan dihasilkan oleh InsightPilot · IBM AI Builders Challenge · Mode Demo*
