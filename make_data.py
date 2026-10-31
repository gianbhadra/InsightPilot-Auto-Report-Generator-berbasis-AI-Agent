"""
make_data.py
------------
One-time script to generate all datasets under data/.
Run: python make_data.py   (or python3 make_data.py)
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)

# ---------------------------------------------------------------------------
# sales_sample.csv
# Spec: ~100 rows, exactly 6 missing values, 2 duplicate rows, 1 outlier (jumlah=60)
# Columns: id_transaksi, tanggal, cabang, produk, kategori,
#          harga_satuan, jumlah, total_penjualan, metode_bayar, rating_pelanggan
# ---------------------------------------------------------------------------

CABANG = ["Jakarta Pusat", "Jakarta Selatan", "Bandung", "Surabaya", "Medan", "Yogyakarta"]
KATEGORI_PRODUK = {
    "Elektronik":  ["Laptop", "Smartphone", "Earbuds", "Tablet", "Smartwatch"],
    "Fashion":     ["Sepatu Sneakers", "Kaos Polos", "Jaket Denim", "Tas Ransel", "Topi Baseball"],
    "Makanan":     ["Kopi Arabika", "Teh Hijau", "Snack Box", "Madu Asli", "Cokelat Premium"],
    "Peralatan":   ["Blender", "Rice Cooker", "Panci Set", "Sapu Robot", "Lampu LED"],
    "Olahraga":    ["Sepatu Lari", "Yoga Mat", "Dumbbell Set", "Bola Futsal", "Raket Badminton"],
}
METODE_BAYAR = ["Transfer Bank", "Kartu Kredit", "QRIS", "COD", "E-Wallet"]
HARGA_MAP = {
    "Laptop": 8500000, "Smartphone": 4500000, "Earbuds": 350000, "Tablet": 3200000,
    "Smartwatch": 1200000, "Sepatu Sneakers": 450000, "Kaos Polos": 120000,
    "Jaket Denim": 380000, "Tas Ransel": 275000, "Topi Baseball": 85000,
    "Kopi Arabika": 95000, "Teh Hijau": 45000, "Snack Box": 65000,
    "Madu Asli": 150000, "Cokelat Premium": 85000, "Blender": 380000,
    "Rice Cooker": 450000, "Panci Set": 320000, "Sapu Robot": 1800000,
    "Lampu LED": 75000, "Sepatu Lari": 650000, "Yoga Mat": 220000,
    "Dumbbell Set": 480000, "Bola Futsal": 180000, "Raket Badminton": 350000,
}

start = date(2024, 1, 1)
rows = []
for i in range(96):  # 96 normal rows; we add 2 duplicates → 98; then 2 more → 100
    tgl = start + timedelta(days=random.randint(0, 364))
    kat = random.choice(list(KATEGORI_PRODUK))
    prod = random.choice(KATEGORI_PRODUK[kat])
    harga = HARGA_MAP[prod]
    jumlah = random.randint(1, 10)
    total = harga * jumlah
    rating = round(random.uniform(3.0, 5.0), 1)
    rows.append([
        f"TRX-{1000 + i:04d}",
        tgl.isoformat(),
        random.choice(CABANG),
        prod,
        kat,
        harga,
        jumlah,
        total,
        random.choice(METODE_BAYAR),
        rating,
    ])

# Add the required outlier: jumlah = 60 (far above normal range of 1-10)
# placed at index 96 (row 97)
outlier_prod = "Kopi Arabika"
outlier_harga = HARGA_MAP[outlier_prod]
rows.append([
    "TRX-1096",
    (start + timedelta(days=180)).isoformat(),
    "Surabaya",
    outlier_prod,
    "Makanan",
    outlier_harga,
    60,               # ← outlier
    outlier_harga * 60,
    "E-Wallet",
    4.5,
])

# Add 2 duplicate rows (exact copy of row 0 and row 1)
rows.append(rows[0][:])   # duplicate of row 0
rows.append(rows[1][:])   # duplicate of row 1
# Change IDs so CSV is importable without complaints
rows[-2][0] = "TRX-1097-DUP"
rows[-1][0] = "TRX-1098-DUP"

# Final row count = 99; add one more normal row to reach 100
tgl = start + timedelta(days=300)
kat = "Olahraga"
prod = "Yoga Mat"
harga = HARGA_MAP[prod]
rows.append([
    "TRX-1099",
    tgl.isoformat(),
    "Bandung",
    prod,
    kat,
    harga,
    3,
    harga * 3,
    "QRIS",
    4.8,
])

# Inject exactly 6 missing values at specific positions
# Missing in: tanggal(1), cabang(1), produk(1), metode_bayar(2), rating_pelanggan(1)
rows[5][1] = ""      # tanggal  row 5
rows[12][2] = ""     # cabang   row 12
rows[20][3] = ""     # produk   row 20
rows[30][8] = ""     # metode_bayar row 30
rows[45][8] = ""     # metode_bayar row 45
rows[60][9] = ""     # rating_pelanggan row 60

HEADER = [
    "id_transaksi", "tanggal", "cabang", "produk", "kategori",
    "harga_satuan", "jumlah", "total_penjualan", "metode_bayar", "rating_pelanggan",
]

with open("data/sales_sample.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow(row)

print(f"data/sales_sample.csv: {len(rows)} baris ditulis.")
print("  Outlier jumlah=60 di baris 97")
print("  Duplikat: baris 98 & 99 (copy of baris 1 & 2)")
print("  Nilai hilang: tanggal(1), cabang(1), produk(1), metode_bayar(2), rating(1) = 6")

# ---------------------------------------------------------------------------
# nilai_mahasiswa.csv
# ~80 rows, student grades
# Columns: nim, nama, kelas, mata_kuliah, dosen, nilai_uts, nilai_uas,
#          nilai_tugas, nilai_akhir, grade, kehadiran_pct
# ---------------------------------------------------------------------------

KELAS = ["A", "B", "C", "D"]
MATA_KULIAH = [
    "Pemrograman Web", "Basis Data", "Statistika", "Kecerdasan Buatan",
    "Jaringan Komputer", "Sistem Operasi",
]
DOSEN = {
    "Pemrograman Web": "Dr. Andi Wijaya",
    "Basis Data": "Prof. Siti Rahayu",
    "Statistika": "Dr. Budi Santoso",
    "Kecerdasan Buatan": "Dr. Rina Kartika",
    "Jaringan Komputer": "Ir. Hendra Kusuma",
    "Sistem Operasi": "Dr. Maya Pratiwi",
}

def grade(na: float) -> str:
    if na >= 85: return "A"
    if na >= 75: return "B"
    if na >= 65: return "C"
    if na >= 55: return "D"
    return "E"

mhs_rows = []
nim_base = 2024001
for i in range(80):
    mk = random.choice(MATA_KULIAH)
    uts = round(random.uniform(45, 100), 1)
    uas = round(random.uniform(45, 100), 1)
    tugas = round(random.uniform(60, 100), 1)
    na = round(uts * 0.35 + uas * 0.40 + tugas * 0.25, 2)
    kehadiran = round(random.uniform(60, 100), 1)
    mhs_rows.append([
        f"{nim_base + i}",
        f"Mahasiswa {i + 1:03d}",
        random.choice(KELAS),
        mk,
        DOSEN[mk],
        uts, uas, tugas,
        na,
        grade(na),
        kehadiran,
    ])

MHS_HEADER = [
    "nim", "nama", "kelas", "mata_kuliah", "dosen",
    "nilai_uts", "nilai_uas", "nilai_tugas", "nilai_akhir", "grade", "kehadiran_pct",
]

with open("data/nilai_mahasiswa.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(MHS_HEADER)
    for row in mhs_rows:
        writer.writerow(row)

print(f"data/nilai_mahasiswa.csv: {len(mhs_rows)} baris ditulis.")
