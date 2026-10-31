"""
config.py
---------
Central configuration for InsightPilot v2.
All constants, theme values, CSS, and system prompts live here.
No exec/eval anywhere in this project.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Anthropic model
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL_NAME: str = "claude-opus-4-5"
MAX_TOKENS: int = 4096
MAX_AGENT_STEPS: int = 12  # hard cap on agent loop iterations

# ---------------------------------------------------------------------------
# Chart output
# ---------------------------------------------------------------------------
CHART_DIR: str = "charts"  # directory for saved chart PNGs
CHART_DPI: int = 130
# Consistent palette for all charts (WCAG AA contrast on white)
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
# Sample datasets (relative paths from project root)
# ---------------------------------------------------------------------------
SAMPLE_DATASETS: dict[str, str] = {
    "data/sales_sample.csv": "🛍️ Data Penjualan (sales_sample.csv)",
    "data/nilai_mahasiswa.csv": "🎓 Nilai Mahasiswa (nilai_mahasiswa.csv)",
}

# ---------------------------------------------------------------------------
# UI / Theme — light dashboard, WCAG AA compliant
# ---------------------------------------------------------------------------
PRIMARY_COLOR: str = "#0A7C65"
ACCENT_COLOR: str = "#F59E0B"
BG_PAGE: str = "#F8FAFC"
BG_CARD: str = "#FFFFFF"
BG_SIDEBAR: str = "#FFFFFF"
TEXT_MAIN: str = "#1E293B"
TEXT_MUTED: str = "#64748B"
BORDER_COLOR: str = "#E2E8F0"
BORDER_RADIUS: str = "12px"
SHADOW: str = "0 1px 4px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04)"

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

/* === Demo mode banner === */
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

/* === Tab styling === */
button[data-baseweb="tab"] {{
    font-weight: 600;
    font-size: 0.9rem;
}}
</style>
"""

# ---------------------------------------------------------------------------
# Report language
# ---------------------------------------------------------------------------
REPORT_LANGUAGE: str = "Indonesian"
REPORT_MAX_WORDS: int = 600

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT: str = f"""
Anda adalah InsightPilot, analis data ahli untuk IBM AI Builders Challenge.
Tugas Anda: menghasilkan laporan data mendalam dalam Bahasa Indonesia.

Tools yang tersedia:
- get_overview       : statistik dasar, nilai hilang, duplikat
- get_correlations   : korelasi antar kolom numerik
- group_summary      : agregasi per kolom kategori
- detect_outliers    : deteksi outlier dengan metode IQR
- make_chart         : buat grafik (bar/line/hist) dan simpan sebagai PNG

Aturan WAJIB:
1. Panggil tools secara bertahap. Mulai dengan get_overview.
2. Buat MINIMAL 2 grafik dengan make_chart.
3. Setelah eksplorasi (maks {MAX_AGENT_STEPS} langkah), tulis laporan akhir Markdown
   dengan TEPAT keempat bagian berikut (gunakan heading ## persis ini):
   ## Ringkasan Eksekutif
   ## Kualitas Data
   ## Temuan Utama
   ## Rekomendasi
4. Laporan HARUS di bawah {REPORT_MAX_WORDS} kata.
5. Gunakan HANYA angka dari hasil tool — dilarang mengarang data.
6. Sebutkan nilai hilang, duplikat, dan outlier secara eksplisit di bagian
   "Kualitas Data" dan "Temuan Utama".
""".strip()
