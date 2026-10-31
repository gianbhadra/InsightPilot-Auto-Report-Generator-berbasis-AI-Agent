"""
generate_sample.py
------------------
One-time script that creates sales_sample.csv (~100 rows).
Run: python generate_sample.py
"""

import random
import csv
from datetime import date, timedelta

random.seed(42)

REGIONS = ["Jawa Barat", "Jawa Tengah", "Jawa Timur", "Sumatera Utara", "Bali", "Kalimantan Selatan"]
CATEGORIES = ["Elektronik", "Fashion", "Makanan & Minuman", "Peralatan Rumah", "Olahraga", "Buku & Alat Tulis"]
PRODUCTS = {
    "Elektronik": ["Laptop", "Smartphone", "Earbuds", "Tablet", "Smartwatch"],
    "Fashion": ["Sepatu Sneakers", "Kaos Polos", "Jaket Denim", "Tas Ransel", "Topi Baseball"],
    "Makanan & Minuman": ["Kopi Arabika", "Teh Hijau", "Snack Box", "Madu Asli", "Cokelat Premium"],
    "Peralatan Rumah": ["Blender", "Rice Cooker", "Panci Set", "Sapu Robot", "Lampu LED"],
    "Olahraga": ["Sepatu Lari", "Yoga Mat", "Dumbbell Set", "Bola Futsal", "Raket Badminton"],
    "Buku & Alat Tulis": ["Novel Bestseller", "Buku Bisnis", "Planner 2025", "Pulpen Premium", "Sticky Notes"],
}
CHANNELS = ["Marketplace", "Toko Langsung", "WhatsApp", "Website", "Reseller"]

start_date = date(2024, 1, 1)
rows = []
for i in range(100):
    order_date = start_date + timedelta(days=random.randint(0, 364))
    region = random.choice(REGIONS)
    category = random.choice(CATEGORIES)
    product = random.choice(PRODUCTS[category])
    qty = random.randint(1, 15)
    unit_price = random.choice([49000, 75000, 120000, 250000, 499000, 750000, 1200000, 2500000])
    discount_pct = random.choice([0, 0, 0, 5, 10, 15, 20])
    revenue = round(qty * unit_price * (1 - discount_pct / 100))
    channel = random.choice(CHANNELS)
    rating = round(random.uniform(3.0, 5.0), 1)
    rows.append([
        f"ORD-{1000+i:04d}",
        order_date.isoformat(),
        region,
        category,
        product,
        channel,
        qty,
        unit_price,
        discount_pct,
        revenue,
        rating,
    ])

header = [
    "order_id", "order_date", "region", "category", "product",
    "channel", "quantity", "unit_price", "discount_pct", "revenue", "rating"
]

with open("sales_sample.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

print("sales_sample.csv created with", len(rows), "rows.")
