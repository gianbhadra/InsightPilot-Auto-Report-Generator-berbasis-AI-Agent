"""
config.py
---------
Central configuration for InsightPilot v3 (Gemini edition).

All constants, Gemini model settings, theme values, CSS, and system
prompts live here.  No secrets are hardcoded — everything is read from
environment variables.

No exec/eval anywhere in this project.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Gemini model  (Google AI Studio free tier)
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# Default model — override by setting the GEMINI_MODEL env var.
# Free-tier models: gemini-1.5-flash (recommended), gemini-1.5-flash-8b
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# Maximum output tokens for the model response
MAX_OUTPUT_TOKENS: int = 4096

# Hard cap on function-calling iterations per run
MAX_AGENT_STEPS: int = 8

# ---------------------------------------------------------------------------
# Free-tier safety / rate-limit handling
# ---------------------------------------------------------------------------
# Number of retries on HTTP 429 / quota errors
RETRY_ATTEMPTS: int = 3
# Backoff delays in seconds for each retry attempt
RETRY_BACKOFF_SECONDS: list[int] = [2, 4, 8]

# Maximum characters of a single tool result sent back to the model.
# Keeps prompts short and within free-tier context limits.
TOOL_RESULT_MAX_CHARS: int = 2_000

# Number of sample rows from the dataset included in the initial prompt.
# Full data is never sent to the model — only col names + sample rows.
PROMPT_SAMPLE_ROWS: int = 5

# ---------------------------------------------------------------------------
# Chart output
# ---------------------------------------------------------------------------
CHART_DIR: str = "charts"       # directory for saved chart PNGs
CHART_DPI: int = 130
# Consistent palette — all colours are WCAG AA contrast-compliant on white
CHART_PALETTE: list[str] = [
    "#0A7C65",  # primary green
    "#F59E0B",  # accent amber
    "#3B82F6",  # blue
    "#EF4444",  # red
    "#8B5CF6",  # purple
    "#14B8A6",  # teal
    "#F97316",  # orange
    "#6366F1",  # indigo
    "#84CC16",  # lime
    "#EC4899",  # pink
]

# ---------------------------------------------------------------------------
# File constraints
# ---------------------------------------------------------------------------
MAX_UPLOAD_MB: int = 5
ALLOWED_EXTENSIONS: list[str] = ["csv", "xlsx"]

# ---------------------------------------------------------------------------
# Sample datasets  (paths relative to project root)
# ---------------------------------------------------------------------------
SAMPLE_DATASETS: dict[str, str] = {
    "data/sales_sample.csv":    "🛍️ Data Penjualan (sales_sample.csv)",
    "data/nilai_mahasiswa.csv": "🎓 Nilai Mahasiswa (nilai_mahasiswa.csv)",
}

# ---------------------------------------------------------------------------
# Demo report path  (used when API key is missing or quota is exhausted)
# ---------------------------------------------------------------------------
DEMO_REPORT_PATH: str = "data/demo_report.md"

# ---------------------------------------------------------------------------
# UI / Theme — light dashboard, WCAG AA compliant
# ---------------------------------------------------------------------------
PRIMARY_COLOR: str = "#0A7C65"
ACCENT_COLOR: str  = "#F59E0B"
BG_PAGE: str       = "#F8FAFC"
BG_CARD: str       = "#FFFFFF"
BG_SIDEBAR: str    = "#FFFFFF"
TEXT_MAIN: str     = "#1E293B"
TEXT_MUTED: str    = "#64748B"
BORDER_COLOR: str  = "#E2E8F0"
BORDER_RADIUS: str = "12px"
SHADOW: str        = "0 1px 4px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04)"

# ---------------------------------------------------------------------------
# Global CSS injected into Streamlit
# ---------------------------------------------------------------------------
GLOBAL_CSS: str = f"""
<style>
/* === Page background === */
.stApp {{
    background-color: {BG_PAGE};
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    color: {TEXT_MAIN};
}}

/* === Sidebar === */
[data-testid="stSidebar"] {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {BORDER_COLOR};
}}

/* === KPI / Metric cards === */
[data-testid="metric-container"] {{
    background: {BG_CARD};
    border-radius: {BORDER_RADIUS};
    box-shadow: {SHADOW};
    padding: 1rem 1.2rem;
    border: 1px solid {BORDER_COLOR};
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED};
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    color: {TEXT_MAIN};
    font-size: 1.7rem;
    font-weight: 700;
}}

/* === Generic card wrapper === */
.ip-card {{
    background: {BG_CARD};
    border-radius: {BORDER_RADIUS};
    box-shadow: {SHADOW};
    border: 1px solid {BORDER_COLOR};
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}}

/* === Section title === */
.ip-section-title {{
    color: {PRIMARY_COLOR};
    font-weight: 700;
    font-size: 1rem;
    margin: 0 0 0.6rem 0;
}}

/* === Agent timeline item === */
.timeline-item {{
    border-left: 3px solid {PRIMARY_COLOR};
    padding: 0.5rem 0.9rem 0.5rem 1rem;
    margin-bottom: 0.45rem;
    background: #F0FDF9;
    border-radius: 0 8px 8px 0;
    font-size: 0.87rem;
}}
.timeline-item .tl-tool {{
    font-weight: 700;
    color: {PRIMARY_COLOR};
}}
.timeline-item .tl-args {{
    color: {TEXT_MUTED};
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 0.8rem;
}}

/* === Report box === */
.report-box {{
    background: {BG_CARD};
    border-radius: {BORDER_RADIUS};
    box-shadow: {SHADOW};
    border: 1px solid {BORDER_COLOR};
    border-top: 4px solid {PRIMARY_COLOR};
    padding: 1.75rem 2rem;
}}

/* === Download / primary button === */
.stDownloadButton > button {{
    background-color: {PRIMARY_COLOR} !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
}}
.stDownloadButton > button:hover {{
    background-color: #085f4e !important;
}}
button[kind="primary"] {{
    background-color: {PRIMARY_COLOR} !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
}}
button[kind="primary"]:hover {{
    background-color: #085f4e !important;
}}

/* === Accent badge === */
.badge {{
    display: inline-block;
    background: {ACCENT_COLOR};
    color: #ffffff;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.76rem;
    font-weight: 700;
    margin-left: 6px;
    vertical-align: middle;
}}
.badge-green {{
    background: {PRIMARY_COLOR};
}}

/* === Demo / quota warning banner === */
.demo-banner {{
    background: linear-gradient(90deg, #FEF3C7 0%, #FDE68A 100%);
    border: 1px solid {ACCENT_COLOR};
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-size: 0.88rem;
    font-weight: 600;
    color: #92400E;
    margin-bottom: 1rem;
}}

/* === Retry / quota info banner === */
.quota-banner {{
    background: #EFF6FF;
    border: 1px solid #3B82F6;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-size: 0.87rem;
    color: #1E40AF;
    margin-bottom: 0.75rem;
}}

/* === Tab styling === */
button[data-baseweb="tab"] {{
    font-weight: 600;
    font-size: 0.9rem;
}}
</style>
"""

# ---------------------------------------------------------------------------
# Report settings
# ---------------------------------------------------------------------------
REPORT_LANGUAGE: str  = "Indonesian"
REPORT_MAX_WORDS: int = 600

# ---------------------------------------------------------------------------
# System prompt  (sent once as the "system" / initial context to Gemini)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT: str = f"""
Anda adalah InsightPilot, analis data ahli untuk IBM AI Builders Challenge.
Tugas Anda: menghasilkan laporan analisis data mendalam dalam Bahasa Indonesia.

Tools yang tersedia:
- get_overview       : statistik dasar, nilai hilang, duplikat
- get_correlations   : korelasi antar kolom numerik
- group_summary      : agregasi per kolom kategori
- detect_outliers    : deteksi outlier dengan metode IQR
- make_chart         : buat grafik (bar/line/hist) dan simpan sebagai PNG

Aturan WAJIB:
1. Selalu mulai dengan memanggil get_overview.
2. Buat MINIMAL 2 grafik dengan make_chart.
3. Setelah eksplorasi selesai (maks {MAX_AGENT_STEPS} langkah tool), tulis laporan
   akhir Markdown dengan TEPAT keempat bagian berikut (gunakan heading ## persis ini):
   ## Ringkasan Eksekutif
   ## Kualitas Data
   ## Temuan Utama
   ## Rekomendasi
4. Laporan HARUS di bawah {REPORT_MAX_WORDS} kata.
5. Gunakan HANYA angka dari hasil tool — dilarang mengarang atau mengira-ngira data.
6. Sebutkan nilai hilang, duplikat, dan outlier secara eksplisit di bagian
   "Kualitas Data" dan "Temuan Utama".
7. Setelah laporan selesai, JANGAN panggil tool lagi.
""".strip()
