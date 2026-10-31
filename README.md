# 📊 InsightPilot v3 — Auto-Report Generator berbasis AI Agent (Gemini Free Tier)

> **IBM AI Builders Challenge · AI Agent for Data Analysis Track**

InsightPilot menggunakan **Google Gemini** (via Google AI Studio — **FREE**) sebagai AI Agent untuk menganalisis dataset CSV/Excel dan menghasilkan laporan mendalam dalam **Bahasa Indonesia** — dirancang untuk mahasiswa dan pemilik usaha kecil.

> ⚠️ **Catatan privasi:** Pada free tier, Google dapat menggunakan data yang dikirim ke API untuk meningkatkan model. Jangan unggah data sensitif. Lihat [Google AI Studio Terms](https://ai.google.dev/gemini-api/terms).

---

## ✨ Fitur Utama

| Fitur | Detail |
|---|---|
| 📂 Upload Dataset | `.csv` / `.xlsx`, maksimum **5 MB** |
| 📊 4 KPI Cards | Baris, Kolom, Nilai Hilang, Baris Duplikat |
| 🤖 Agent Loop | Maks 8 langkah; 5 tools: `get_overview`, `get_correlations`, `group_summary`, `detect_outliers` (IQR), `make_chart` |
| 🔄 429 Retry | Otomatis retry 3× (2s/4s/8s backoff) pada quota errors |
| 🎭 Mode Demo | Laporan statis tanpa API key — aktif otomatis jika key hilang |
| ⚡ Caching | Laporan di-cache per file hash + fokus (hemat kuota) |
| 🔍 Log Agen | Timeline interaktif setiap function call |
| 📄 Tabs | **Laporan** · **Grafik** · **Log Agen** |
| 📋 Laporan Bahasa Indonesia | Ringkasan Eksekutif, Kualitas Data, Temuan Utama, Rekomendasi (≤600 kata) |
| ⬇️ Unduh | `.md` dan `.docx` (dengan grafik tersemat) |

---

## 🚀 Setup (5 Menit)

### 1. Dapatkan API Key GRATIS

1. Buka [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Login dengan akun Google
3. Klik **"Create API key"**
4. Salin key yang dihasilkan (`AIza...`)

### 2. Clone & Install

```bash
git clone https://github.com/your-username/InsightPilot.git
cd InsightPilot

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set Environment Variables

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY = "AIzaSy..."
# Opsional — default: gemini-1.5-flash
$env:GEMINI_MODEL = "gemini-1.5-flash"
```

**macOS / Linux:**
```bash
export GEMINI_API_KEY="AIzaSy..."
export GEMINI_MODEL="gemini-1.5-flash"   # opsional
```

### 4. Jalankan

```bash
streamlit run app.py
```

Buka browser di `http://localhost:8501`.

### 5. Mode Demo (tanpa API key)

Aktifkan toggle **"🎭 Mode Demo"** di sidebar — tidak perlu API key.

---

## 🗂️ Struktur Proyek

```
InsightPilot/
├── app.py               # Streamlit UI — sidebar, KPI, tabs, demo fallback
├── agent.py             # Gemini function-calling loop, retry, cache
├── tools.py             # 5 tools + Gemini schemas + dispatcher
├── report.py            # Markdown → .docx (embedded charts)
├── config.py            # Semua konstanta, CSS, env vars, system prompt
├── make_data.py         # Script generator dataset
├── requirements.txt
├── README.md
├── data/
│   ├── sales_sample.csv      # 100 baris, 6 missing, 2 dup, 1 outlier
│   ├── nilai_mahasiswa.csv   # 80 baris data akademik
│   └── demo_report.md        # Laporan statis untuk Mode Demo
└── charts/              # Output PNG grafik (dibuat otomatis)
```

---

## 🤖 Arsitektur Agent Loop

```
┌────────────────────────────────────────────────────────────────┐
│                    app.py  (Streamlit UI)                       │
│  Sidebar: upload · demo · fokus · "Buat Laporan"                │
│  Main: 4 KPI cards · 10-row preview                             │
│  Tabs: Laporan | Grafik | Log Agen                              │
│  Auto-fallback: quota/key error → demo mode banner              │
└──────────────────────────┬─────────────────────────────────────┘
                           │ run_agent(df, focus, file_hash)
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                    agent.py  (Gemini Loop)                      │
│  0. Check report cache (file_hash + focus)                      │
│  1. Verify GEMINI_API_KEY + google-genai installed              │
│  2. Build prompt (cols + 5 sample rows only — NOT full data)    │
│  3. while step < MAX_AGENT_STEPS (8):                           │
│     a. _call_with_retry(generate_content) — 3× backoff on 429  │
│     b. Collect FunctionCall parts → dispatch_tool()             │
│     c. yield StepEvent per call                                 │
│     d. Send FunctionResponse back as Content role="function"    │
│     e. If no function calls → yield ReportEvent (done)          │
│     f. If step == MAX_STEPS → force text-only final call        │
│  4. Cache result; yield ReportEvent                             │
│  ErrorEvent.is_quota_error=True → app activates demo mode       │
└──────────────────────────┬─────────────────────────────────────┘
                           │ dispatch_tool(name, args, df)
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                    tools.py                                     │
│  get_overview      → shape, dtypes, missing, dups, stats        │
│  get_correlations  → Pearson/Spearman/Kendall matrix            │
│  group_summary     → df.groupby().agg()                         │
│  detect_outliers   → IQR fences, outlier list                   │
│  make_chart        → bar/line/hist PNG → charts/                │
│  ─────────────────────────────────────────────────────────      │
│  Tool results truncated to 2,000 chars before model sees them   │
│  All errors returned as {"error":"..."} JSON — agent corrects   │
└──────────────────────────┬─────────────────────────────────────┘
                           │ markdown_to_docx(report_md, charts)
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                    report.py                                    │
│  word_count()     → count words (strips Markdown syntax)        │
│  markdown_to_docx → python-docx: headings, bullets, bold,       │
│                     inline code, embedded PNG charts            │
└────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tools

| Tool | Input | Output |
|---|---|---|
| `get_overview` | — | shape, dtypes, missing values, duplicates, descriptive stats |
| `get_correlations` | `method`, `top_n` | correlation matrix + ranked pairs |
| `group_summary` | `group_col`, `agg_col`, `agg_func`, `top_n` | grouped results descending |
| `detect_outliers` | `column`, `iqr_multiplier` | IQR fences, outlier count & values |
| `make_chart` | `chart_type`, `x_col`, `y_col`, `title`, `top_n` | PNG file path |

---

## 📋 Dataset: sales_sample.csv

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id_transaksi` | string | ID unik |
| `tanggal` | date | Tanggal transaksi 2024 |
| `cabang` | kategori | 6 cabang kota |
| `produk` | kategori | Nama produk |
| `kategori` | kategori | 5 kategori produk |
| `harga_satuan` | int | Harga per unit (IDR) |
| `jumlah` | int | Unit terjual — **1 outlier: jumlah=60** |
| `total_penjualan` | int | harga × jumlah |
| `metode_bayar` | kategori | 5 metode |
| `rating_pelanggan` | float | 3.0–5.0 |

**Data quality by design:** 6 missing values · 2 duplicate rows · 1 outlier (jumlah=60)

---

## ⚙️ Konfigurasi (`config.py`)

```python
GEMINI_MODEL         = "gemini-1.5-flash"  # dari env GEMINI_MODEL
MAX_AGENT_STEPS      = 8                    # maks langkah function calling
RETRY_ATTEMPTS       = 3                    # retry pada 429
RETRY_BACKOFF_SECONDS= [2, 4, 8]           # backoff (detik)
TOOL_RESULT_MAX_CHARS= 2_000               # truncate tool results
PROMPT_SAMPLE_ROWS   = 5                    # baris sampel ke model
REPORT_MAX_WORDS     = 600                  # target panjang laporan
MAX_UPLOAD_MB        = 5                    # batas upload
```

---

## 🔒 Keamanan & Privasi

- API key dibaca **hanya** dari environment variable `GEMINI_API_KEY`.
- **Data pengguna TIDAK pernah dikirim langsung ke Gemini** — hanya nama kolom dan 5 baris sampel.
- Tidak ada `exec()` atau `eval()` di seluruh kodebase.
- **Free tier:** Google dapat menggunakan input/output untuk meningkatkan model. Gunakan [Google AI Studio Paid Tier](https://ai.google.dev/pricing) atau Vertex AI untuk data sensitif.

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
