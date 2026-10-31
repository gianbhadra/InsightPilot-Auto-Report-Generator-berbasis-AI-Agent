"""
app.py
------
InsightPilot v3 (Gemini edition) — Streamlit front-end.

Layout
------
  Sidebar : file uploader (≤5 MB), sample-data selector, analysis focus,
            "Buat laporan" button, "Mode demo" toggle
  Main    : 4 KPI cards + 10-row preview
            Tabs: "Laporan" | "Grafik" | "Log Agen"

Free-tier safety:
  • File bytes are SHA256-hashed for report caching (no data sent to Gemini).
  • Quota / missing-key errors automatically show the demo report with a
    friendly banner — no stack traces.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from agent import ErrorEvent, ReportEvent, StepEvent, run_agent
from report import DOCX_AVAILABLE, markdown_to_docx, word_count

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="InsightPilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(config.GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

def _init_state() -> None:
    """Initialise all session-state keys with safe defaults."""
    defaults: dict = {
        "df": None,
        "file_label": "",
        "file_hash": "",        # SHA256 hex prefix for caching
        "step_log": [],         # list[StepEvent]
        "report": None,         # ReportEvent | None
        "chart_paths": [],
        "running": False,
        "error": None,          # str | None
        "is_quota_error": False,
        "demo_mode": False,
        "focus_value": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ---------------------------------------------------------------------------
# File loading helpers
# ---------------------------------------------------------------------------

MAX_BYTES: int = config.MAX_UPLOAD_MB * 1024 * 1024


def _sha256_prefix(data: bytes, length: int = 16) -> str:
    """Return the first *length* hex chars of a SHA256 digest."""
    return hashlib.sha256(data).hexdigest()[:length]


@st.cache_data(show_spinner=False)
def _parse_csv(raw: bytes, name: str) -> pd.DataFrame:
    """Cached CSV parser — keyed by file bytes hash via *name*."""
    import io
    return pd.read_csv(io.BytesIO(raw))


@st.cache_data(show_spinner=False)
def _parse_xlsx(raw: bytes, name: str) -> pd.DataFrame:
    """Cached XLSX parser."""
    import io
    return pd.read_excel(io.BytesIO(raw))


def _load_uploaded(uploaded) -> tuple[pd.DataFrame | None, bytes]:
    """
    Parse an uploaded Streamlit file into a DataFrame.

    Validates size ≤ MAX_UPLOAD_MB and extension (.csv / .xlsx).
    Returns (DataFrame, raw_bytes) on success, (None, b"") on failure.
    """
    raw: bytes = uploaded.read()

    if len(raw) > MAX_BYTES:
        st.error(
            f"⚠️ File terlalu besar ({len(raw) / 1_048_576:.1f} MB). "
            f"Batas: {config.MAX_UPLOAD_MB} MB."
        )
        return None, b""

    ext = Path(uploaded.name).suffix.lower()
    cache_name = f"{uploaded.name}-{_sha256_prefix(raw)}"
    try:
        if ext == ".csv":
            return _parse_csv(raw, cache_name), raw
        elif ext in (".xlsx", ".xls"):
            return _parse_xlsx(raw, cache_name), raw
        else:
            st.error(
                f"⚠️ Format '{ext}' tidak didukung. "
                "Harap unggah file .csv atau .xlsx."
            )
            return None, b""
    except Exception as exc:
        st.error(f"⚠️ Gagal membaca file: {exc}")
        return None, b""


def _load_sample(path: str) -> tuple[pd.DataFrame | None, bytes]:
    """Load a bundled sample dataset by relative path."""
    p = Path(path)
    if not p.exists():
        st.error(f"⚠️ File sampel tidak ditemukan: {path}")
        return None, b""
    try:
        raw = p.read_bytes()
        ext = p.suffix.lower()
        cache_name = f"{p.name}-{_sha256_prefix(raw)}"
        if ext == ".csv":
            return _parse_csv(raw, cache_name), raw
        elif ext in (".xlsx", ".xls"):
            return _parse_xlsx(raw, cache_name), raw
    except Exception as exc:
        st.error(f"⚠️ Gagal memuat sampel: {exc}")
    return None, b""


def _set_dataframe(df: pd.DataFrame, label: str, raw: bytes) -> None:
    """Store a DataFrame and reset all analysis results."""
    st.session_state.df = df
    st.session_state.file_label = label
    st.session_state.file_hash = _sha256_prefix(raw) if raw else ""
    st.session_state.step_log = []
    st.session_state.report = None
    st.session_state.chart_paths = []
    st.session_state.error = None
    st.session_state.is_quota_error = False


# ---------------------------------------------------------------------------
# Demo report loader
# ---------------------------------------------------------------------------

def _load_demo_report() -> str:
    """Return the pre-written demo Markdown report."""
    p = Path(config.DEMO_REPORT_PATH)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return (
        "# Demo Report\n\n"
        f"File `{config.DEMO_REPORT_PATH}` tidak ditemukan. "
        "Pastikan folder `data/` tersedia."
    )


def _activate_demo() -> None:
    """Load the demo report into session state."""
    demo_md = _load_demo_report()
    st.session_state.report = ReportEvent(
        report_markdown=demo_md,
        steps_taken=0,
        chart_paths=[],
    )
    st.session_state.step_log = []
    st.session_state.error = None
    st.session_state.is_quota_error = False


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar() -> None:
    with st.sidebar:
        # Brand
        st.markdown(
            f"""
            <div style="padding:1rem 0 0.25rem; text-align:center;">
              <div style="font-size:2.4rem;">📊</div>
              <div style="font-size:1.25rem; font-weight:800;
                          color:{config.PRIMARY_COLOR}; line-height:1.2;">
                InsightPilot
              </div>
              <div style="font-size:0.75rem; color:{config.TEXT_MUTED}; margin-top:2px;">
                Auto-Report Generator · IBM AI Builders Challenge
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Demo mode toggle ──────────────────────────────────────────
        demo = st.toggle(
            "🎭 Mode Demo (tanpa API key)",
            value=st.session_state.demo_mode,
            key="demo_toggle",
            help=(
                "Tampilkan laporan contoh tanpa memerlukan GEMINI_API_KEY. "
                "Diaktifkan otomatis jika key tidak ditemukan atau kuota habis."
            ),
        )
        if demo != st.session_state.demo_mode:
            st.session_state.demo_mode = demo

        st.divider()

        # ── File upload ───────────────────────────────────────────────
        st.markdown(
            '<p class="ip-section-title">📂 Unggah Dataset</p>',
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            label="Pilih file CSV atau Excel (maks 5 MB)",
            type=config.ALLOWED_EXTENSIONS,
            help="Format: .csv, .xlsx. Maks 5 MB.",
        )
        if uploaded is not None and uploaded.name != st.session_state.file_label:
            df, raw = _load_uploaded(uploaded)
            if df is not None:
                _set_dataframe(df, uploaded.name, raw)
                st.success(f"✅ **{uploaded.name}** berhasil dimuat.")

        # ── Sample data selector ──────────────────────────────────────
        st.markdown(
            '<p class="ip-section-title" style="margin-top:0.8rem;">'
            "📦 Atau pilih dataset contoh</p>",
            unsafe_allow_html=True,
        )
        sample_labels = list(config.SAMPLE_DATASETS.values())
        sample_paths = list(config.SAMPLE_DATASETS.keys())
        chosen_label = st.selectbox(
            label="Dataset contoh",
            options=["— pilih —"] + sample_labels,
            label_visibility="collapsed",
        )
        if st.button("Muat Dataset Contoh", use_container_width=True):
            if chosen_label == "— pilih —":
                st.warning("Pilih dataset dari dropdown terlebih dahulu.")
            else:
                idx = sample_labels.index(chosen_label)
                df, raw = _load_sample(sample_paths[idx])
                if df is not None:
                    _set_dataframe(df, chosen_label, raw)
                    st.success(f"✅ **{chosen_label}** berhasil dimuat.")

        st.divider()

        # ── Analysis focus ────────────────────────────────────────────
        st.markdown(
            '<p class="ip-section-title">🎯 Fokus Analisis (opsional)</p>',
            unsafe_allow_html=True,
        )
        focus = st.text_area(
            label="Fokus analisis",
            placeholder=(
                "Contoh: Bandingkan total penjualan antar cabang dan "
                "identifikasi produk dengan rating terendah."
            ),
            height=90,
            key="focus_input",
            label_visibility="collapsed",
        )

        st.divider()

        # ── Action buttons ────────────────────────────────────────────
        no_data = st.session_state.df is None
        running = st.session_state.running

        if st.session_state.demo_mode:
            if st.button(
                "🎭 Tampilkan Laporan Demo",
                use_container_width=True,
                type="primary",
            ):
                _activate_demo()
                st.rerun()
        else:
            if st.button(
                "🚀 Buat Laporan",
                use_container_width=True,
                type="primary",
                disabled=no_data or running,
                help=(
                    "Unggah dataset terlebih dahulu."
                    if no_data
                    else "Agen sedang berjalan, harap tunggu."
                    if running
                    else "Jalankan analisis dan hasilkan laporan."
                ),
            ):
                if not config.GEMINI_API_KEY:
                    st.error(
                        "⚠️ GEMINI_API_KEY tidak ditemukan. "
                        "Set environment variable atau aktifkan Mode Demo."
                    )
                else:
                    st.session_state.step_log = []
                    st.session_state.report = None
                    st.session_state.chart_paths = []
                    st.session_state.error = None
                    st.session_state.is_quota_error = False
                    st.session_state.running = True
                    st.session_state.focus_value = focus
                    st.rerun()

            if running:
                st.info("⏳ Agen sedang menganalisis data…")

        st.divider()
        st.caption(
            f"Model: `{config.GEMINI_MODEL}` · Maks {config.MAX_AGENT_STEPS} langkah"
        )
        if not DOCX_AVAILABLE:
            st.caption("⚠️ python-docx tidak terinstal — unduhan .docx dinonaktifkan.")
        if not config.GEMINI_API_KEY and not st.session_state.demo_mode:
            st.warning(
                "GEMINI_API_KEY tidak ditemukan. "
                "Aktifkan **Mode Demo** untuk mencoba aplikasi."
            )


# ---------------------------------------------------------------------------
# Data panel — 4 KPI cards + 10-row preview
# ---------------------------------------------------------------------------

def _render_data_panel(df: pd.DataFrame) -> None:
    """Show 4 KPI metric cards and a 10-row preview table."""
    total_missing = int(df.isnull().sum().sum())
    total_dup = int(df.duplicated().sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baris", f"{len(df):,}")
    c2.metric("Kolom", len(df.columns))
    c3.metric(
        "Nilai Hilang",
        f"{total_missing:,}",
        delta=f"-{total_missing}" if total_missing else None,
        delta_color="inverse",
        help="Total sel kosong (NaN) di seluruh dataset.",
    )
    c4.metric(
        "Baris Duplikat",
        f"{total_dup:,}",
        delta=f"-{total_dup}" if total_dup else None,
        delta_color="inverse",
        help="Baris yang identik dengan baris lain.",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<p class="ip-section-title">📋 Pratinjau Data '
        f'<span class="badge">{len(df):,} baris · {len(df.columns)} kolom</span></p>',
        unsafe_allow_html=True,
    )
    st.dataframe(df.head(10), use_container_width=True, height=240)


# ---------------------------------------------------------------------------
# Tab: Laporan
# ---------------------------------------------------------------------------

def _render_tab_laporan() -> None:
    report: ReportEvent | None = st.session_state.report

    if report is None:
        st.info("Laporan belum tersedia. Jalankan analisis di sidebar.")
        return

    # Demo / cache banners
    is_demo = st.session_state.demo_mode and report.steps_taken == 0
    if is_demo or st.session_state.is_quota_error:
        banner_msg = (
            "🎭 <b>Mode Demo</b> — Laporan ini adalah contoh statis. "
            "Set GEMINI_API_KEY untuk analisis nyata."
            if is_demo
            else (
                "⚠️ <b>Kuota Gemini habis</b> — Menampilkan laporan demo. "
                "Coba lagi beberapa menit kemudian."
            )
        )
        st.markdown(
            f'<div class="demo-banner">{banner_msg}</div>',
            unsafe_allow_html=True,
        )

    if report.from_cache:
        st.markdown(
            '<div class="quota-banner">'
            "⚡ Laporan ini diambil dari cache (dataset + fokus yang sama)."
            "</div>",
            unsafe_allow_html=True,
        )

    # Word count badge
    wc = word_count(report.report_markdown)
    badge_color = config.PRIMARY_COLOR if wc <= config.REPORT_MAX_WORDS else "#EF4444"
    st.markdown(
        f'<p class="ip-section-title">📄 Laporan Analisis '
        f'<span class="badge" style="background:{badge_color};">'
        f"{wc} kata · {report.steps_taken} langkah</span></p>",
        unsafe_allow_html=True,
    )

    # Report body
    st.markdown('<div class="report-box">', unsafe_allow_html=True)
    st.markdown(report.report_markdown, unsafe_allow_html=False)
    st.markdown("</div>", unsafe_allow_html=True)

    # Download buttons
    st.markdown("<br>", unsafe_allow_html=True)
    dl1, dl2 = st.columns(2)
    dl1.download_button(
        label="⬇️ Unduh sebagai .md",
        data=report.report_markdown.encode("utf-8"),
        file_name="laporan_insightpilot.md",
        mime="text/markdown",
        use_container_width=True,
    )
    if DOCX_AVAILABLE:
        docx_bytes = markdown_to_docx(
            report.report_markdown,
            chart_paths=report.chart_paths,
        )
        dl2.download_button(
            label="⬇️ Unduh sebagai .docx",
            data=docx_bytes,
            file_name="laporan_insightpilot.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            use_container_width=True,
        )
    else:
        dl2.info("Install `python-docx` untuk unduhan .docx.")


# ---------------------------------------------------------------------------
# Tab: Grafik
# ---------------------------------------------------------------------------

def _render_tab_grafik() -> None:
    paths = st.session_state.chart_paths
    if not paths:
        st.info("Belum ada grafik yang dihasilkan.")
        return

    st.markdown(
        f'<p class="ip-section-title">📉 Grafik yang Dihasilkan '
        f'<span class="badge">{len(paths)} grafik</span></p>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for idx, path_str in enumerate(paths):
        p = Path(path_str)
        if p.exists():
            cols[idx % 2].image(
                str(p),
                caption=p.stem.replace("_", " ").title(),
                use_container_width=True,
            )
        else:
            cols[idx % 2].warning(f"Grafik tidak ditemukan: {p.name}")


# ---------------------------------------------------------------------------
# Tab: Log Agen
# ---------------------------------------------------------------------------

def _render_tab_log() -> None:
    log: list[StepEvent] = st.session_state.step_log
    if not log:
        st.info("Log kosong. Jalankan analisis untuk melihat timeline agen.")
        return

    st.markdown(
        f'<p class="ip-section-title">🔍 Timeline Agen '
        f'<span class="badge">{len(log)} langkah</span></p>',
        unsafe_allow_html=True,
    )

    tool_icons: dict[str, str] = {
        "get_overview": "🔬",
        "get_correlations": "📐",
        "group_summary": "📊",
        "detect_outliers": "🚨",
        "make_chart": "📈",
    }

    for evt in log:
        icon = tool_icons.get(evt.tool_name, "🔧")
        with st.expander(
            f"{icon} Langkah {evt.step} — `{evt.tool_name}`",
            expanded=False,
        ):
            if evt.tool_args:
                st.markdown("**Argumen:**")
                st.code(
                    json.dumps(evt.tool_args, ensure_ascii=False, indent=2),
                    language="json",
                )

            try:
                parsed = json.loads(evt.tool_result)
                preview = json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                preview = str(evt.tool_result)

            if len(preview) > 900:
                preview = preview[:900] + "\n…(dipotong untuk tampilan)"

            st.markdown("**Hasil:**")
            st.code(preview, language="json")

            if evt.chart_path and Path(evt.chart_path).exists():
                st.image(
                    evt.chart_path,
                    caption=Path(evt.chart_path).name,
                    use_container_width=True,
                )


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

def _run_agent_if_needed() -> None:
    """Execute the agent loop when session_state.running is True."""
    if not st.session_state.running:
        return

    df: pd.DataFrame = st.session_state.df
    focus: str = st.session_state.focus_value
    file_hash: str = st.session_state.file_hash

    placeholder = st.empty()
    placeholder.info("⏳ Agen Gemini sedang menganalisis data… Harap tunggu.")

    try:
        for event in run_agent(df, focus=focus, file_hash=file_hash):
            if isinstance(event, StepEvent):
                st.session_state.step_log.append(event)
                if event.chart_path and event.chart_path not in st.session_state.chart_paths:
                    st.session_state.chart_paths.append(event.chart_path)

            elif isinstance(event, ReportEvent):
                st.session_state.report = event
                for cp in event.chart_paths:
                    if cp not in st.session_state.chart_paths:
                        st.session_state.chart_paths.append(cp)

            elif isinstance(event, ErrorEvent):
                st.session_state.error = event.message
                st.session_state.is_quota_error = event.is_quota_error
                # Auto-fallback to demo mode on quota / missing key
                if event.is_quota_error:
                    _activate_demo()

    except Exception as exc:
        st.session_state.error = f"Kesalahan tak terduga: {exc}"

    finally:
        st.session_state.running = False
        placeholder.empty()
        st.rerun()


# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------

def _render_main() -> None:
    # Header
    st.markdown(
        f"""
        <div style="margin-bottom:1rem;">
          <h1 style="color:{config.PRIMARY_COLOR}; margin:0; font-size:1.8rem;">
            📊 InsightPilot
          </h1>
          <p style="color:{config.TEXT_MUTED}; margin:2px 0 0; font-size:0.9rem;">
            Auto-Report Generator · IBM AI Builders Challenge
            <span style="font-size:0.78rem; margin-left:6px; color:#3B82F6;">
              Powered by Gemini (Free Tier)
            </span>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df: pd.DataFrame | None = st.session_state.df

    # Empty state
    if df is None and not st.session_state.demo_mode:
        st.markdown(
            f"""
            <div style="text-align:center; padding:4rem 1rem;
                        color:{config.TEXT_MUTED};">
              <div style="font-size:4rem; margin-bottom:0.5rem;">📂</div>
              <h3 style="color:{config.PRIMARY_COLOR};">Belum Ada Data</h3>
              <p style="max-width:440px; margin:0 auto;">
                Unggah file CSV/Excel atau pilih dataset contoh di sidebar,
                lalu klik <b>Buat Laporan</b>.<br><br>
                Tidak punya API key? Aktifkan <b>Mode Demo</b> di sidebar.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # KPI + preview (only when data loaded)
    if df is not None:
        _render_data_panel(df)

    # Error banner (non-quota errors)
    if st.session_state.error and not st.session_state.is_quota_error:
        st.error(f"⚠️ {st.session_state.error}")

    # Tabs
    tab_laporan, tab_grafik, tab_log = st.tabs(
        ["📄 Laporan", "📉 Grafik", "🔍 Log Agen"]
    )
    with tab_laporan:
        _render_tab_laporan()
    with tab_grafik:
        _render_tab_grafik()
    with tab_log:
        _render_tab_log()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _render_sidebar()
    _run_agent_if_needed()
    _render_main()


if __name__ == "__main__":
    main()
