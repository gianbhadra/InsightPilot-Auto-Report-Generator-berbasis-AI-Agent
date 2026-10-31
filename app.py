"""
app.py
------
InsightPilot v2 – Streamlit front-end.

Layout
------
  Sidebar  : file uploader (≤5 MB), sample-data selector, analysis focus
             input, "Buat laporan" button, demo-mode toggle
  Main     : 4 KPI cards + 10-row preview
             Tabs: "Laporan" | "Grafik" | "Log Agen"

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
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

# Inject global CSS from config
st.markdown(config.GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------
def _init_state() -> None:
    """Initialise all session-state keys with safe defaults."""
    defaults: dict = {
        "df": None,           # pd.DataFrame | None
        "file_label": "",     # display name for the loaded file
        "step_log": [],       # list[StepEvent]
        "report": None,       # ReportEvent | None
        "chart_paths": [],    # list[str]  (deduplicated)
        "running": False,
        "error": None,        # str | None
        "demo_mode": False,
        "focus_value": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

MAX_BYTES: int = config.MAX_UPLOAD_MB * 1024 * 1024


@st.cache_data(show_spinner=False)
def _load_csv(raw: bytes, name: str) -> pd.DataFrame:
    """Cached CSV loader."""
    import io
    return pd.read_csv(io.BytesIO(raw))


@st.cache_data(show_spinner=False)
def _load_xlsx(raw: bytes, name: str) -> pd.DataFrame:
    """Cached XLSX loader."""
    import io
    return pd.read_excel(io.BytesIO(raw))


def _load_file(uploaded) -> pd.DataFrame | None:
    """
    Parse an uploaded Streamlit file object into a DataFrame.

    Validates size (≤5 MB) and extension (.csv / .xlsx).
    Returns None and shows a friendly error on failure.
    """
    if uploaded.size > MAX_BYTES:
        st.error(
            f"⚠️ File terlalu besar ({uploaded.size / 1_048_576:.1f} MB). "
            f"Batas maksimum adalah {config.MAX_UPLOAD_MB} MB."
        )
        return None

    raw = uploaded.read()
    ext = Path(uploaded.name).suffix.lower()
    try:
        if ext == ".csv":
            return _load_csv(raw, uploaded.name)
        elif ext in (".xlsx", ".xls"):
            return _load_xlsx(raw, uploaded.name)
        else:
            st.error(
                f"⚠️ Format '{ext}' tidak didukung. "
                "Harap unggah file .csv atau .xlsx."
            )
            return None
    except Exception as exc:
        st.error(f"⚠️ Gagal membaca file: {exc}")
        return None


def _load_sample(path: str) -> pd.DataFrame | None:
    """Load a bundled sample dataset by path."""
    p = Path(path)
    if not p.exists():
        st.error(f"⚠️ File sampel tidak ditemukan: {path}")
        return None
    try:
        ext = p.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(p)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(p)
    except Exception as exc:
        st.error(f"⚠️ Gagal memuat dataset sampel: {exc}")
    return None


def _set_dataframe(df: pd.DataFrame, label: str) -> None:
    """Store a DataFrame in session state and reset analysis results."""
    st.session_state.df = df
    st.session_state.file_label = label
    st.session_state.step_log = []
    st.session_state.report = None
    st.session_state.chart_paths = []
    st.session_state.error = None


# ---------------------------------------------------------------------------
# Demo-mode helpers
# ---------------------------------------------------------------------------

DEMO_REPORT_PATH: str = "data/demo_report.md"


def _load_demo_report() -> str:
    """Read the pre-written demo report from disk."""
    p = Path(DEMO_REPORT_PATH)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return (
        "# Demo Report\n\n"
        "File `data/demo_report.md` tidak ditemukan. "
        "Pastikan folder `data/` tersedia."
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar() -> None:
    with st.sidebar:
        # Brand header
        st.markdown(
            f"""
            <div style="padding:1rem 0 0.25rem; text-align:center;">
              <div style="font-size:2.4rem;">📊</div>
              <div style="font-size:1.25rem; font-weight:800;
                          color:{config.PRIMARY_COLOR}; line-height:1.2;">
                InsightPilot
              </div>
              <div style="font-size:0.75rem; color:{config.TEXT_MUTED};
                          margin-top:2px;">
                Auto-Report Generator · AI Agent
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # ── Demo mode toggle ──────────────────────────────────────────────
        demo = st.toggle(
            "🎭 Mode Demo (tanpa API key)",
            value=st.session_state.demo_mode,
            help=(
                "Aktifkan untuk melihat contoh laporan tanpa memerlukan "
                "ANTHROPIC_API_KEY."
            ),
            key="demo_toggle",
        )
        if demo != st.session_state.demo_mode:
            st.session_state.demo_mode = demo

        st.divider()

        # ── File upload ───────────────────────────────────────────────────
        st.markdown(
            '<p class="ip-section-title">📂 Unggah Dataset</p>',
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            label="Pilih file CSV atau Excel (maks 5 MB)",
            type=config.ALLOWED_EXTENSIONS,
            help="Format yang didukung: .csv, .xlsx. Ukuran maksimum: 5 MB.",
        )
        if uploaded is not None and uploaded.name != st.session_state.file_label:
            df = _load_file(uploaded)
            if df is not None:
                _set_dataframe(df, uploaded.name)
                st.success(f"✅ **{uploaded.name}** berhasil dimuat.")

        # ── Sample data selector ──────────────────────────────────────────
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
                df = _load_sample(sample_paths[idx])
                if df is not None:
                    _set_dataframe(df, chosen_label)
                    st.success(f"✅ **{chosen_label}** berhasil dimuat.")

        st.divider()

        # ── Analysis focus ────────────────────────────────────────────────
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

        # ── Run / Demo button ─────────────────────────────────────────────
        no_data = st.session_state.df is None
        running = st.session_state.running

        if st.session_state.demo_mode:
            if st.button(
                "🎭 Tampilkan Laporan Demo",
                use_container_width=True,
                type="primary",
            ):
                # Load the bundled demo report into session state
                demo_md = _load_demo_report()
                st.session_state.report = ReportEvent(
                    report_markdown=demo_md,
                    steps_taken=0,
                    chart_paths=[],
                )
                st.session_state.step_log = []
                st.session_state.error = None
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
                    else "Agen AI sedang berjalan, harap tunggu."
                    if running
                    else "Jalankan analisis dan buat laporan.",
                ),
            ):
                if not config.ANTHROPIC_API_KEY:
                    st.error(
                        "⚠️ ANTHROPIC_API_KEY tidak ditemukan. "
                        "Set environment variable atau aktifkan Mode Demo."
                    )
                else:
                    st.session_state.step_log = []
                    st.session_state.report = None
                    st.session_state.chart_paths = []
                    st.session_state.error = None
                    st.session_state.running = True
                    st.session_state.focus_value = focus
                    st.rerun()

            if running:
                st.info("⏳ Agen sedang menganalisis data…")

        st.divider()
        st.caption(
            f"Model: `{config.MODEL_NAME}` · Maks {config.MAX_AGENT_STEPS} langkah"
        )
        if not DOCX_AVAILABLE:
            st.caption("⚠️ python-docx tidak terinstal — unduhan .docx dinonaktifkan.")


# ---------------------------------------------------------------------------
# KPI cards + data preview
# ---------------------------------------------------------------------------

def _render_data_panel(df: pd.DataFrame) -> None:
    """Show 4 KPI metric cards and a 10-row data preview."""
    total_missing = int(df.isnull().sum().sum())
    total_dup = int(df.duplicated().sum())

    # ── 4 KPI cards ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        label="Baris",
        value=f"{len(df):,}",
        help="Jumlah total baris dalam dataset.",
    )
    c2.metric(
        label="Kolom",
        value=len(df.columns),
        help="Jumlah total kolom.",
    )
    c3.metric(
        label="Nilai Hilang",
        value=f"{total_missing:,}",
        delta=f"-{total_missing}" if total_missing else None,
        delta_color="inverse",
        help="Total sel kosong (NaN) di seluruh dataset.",
    )
    c4.metric(
        label="Baris Duplikat",
        value=f"{total_dup:,}",
        delta=f"-{total_dup}" if total_dup else None,
        delta_color="inverse",
        help="Baris yang persis sama dengan baris lain.",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 10-row preview ────────────────────────────────────────────────────
    st.markdown(
        f'<p class="ip-section-title">📋 Pratinjau Data '
        f'<span class="badge">{len(df):,} baris · {len(df.columns)} kolom</span></p>',
        unsafe_allow_html=True,
    )
    st.dataframe(df.head(10), use_container_width=True, height=240)


# ---------------------------------------------------------------------------
# Tab content renderers
# ---------------------------------------------------------------------------

def _render_tab_laporan() -> None:
    """Render the 'Laporan' tab: report markdown + download buttons."""
    report: ReportEvent | None = st.session_state.report

    if report is None:
        st.info("Laporan belum tersedia. Jalankan analisis di sidebar untuk memulai.")
        return

    # Demo banner
    if st.session_state.demo_mode and report.steps_taken == 0:
        st.markdown(
            '<div class="demo-banner">'
            "🎭 <b>Mode Demo</b> — Laporan ini adalah contoh statis. "
            "Nonaktifkan Mode Demo dan set ANTHROPIC_API_KEY untuk analisis nyata."
            "</div>",
            unsafe_allow_html=True,
        )

    # Word count badge
    wc = word_count(report.report_markdown)
    badge_color = (
        config.PRIMARY_COLOR if wc <= config.REPORT_MAX_WORDS else "#EF4444"
    )
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
        dl2.info("Install `python-docx` untuk mengaktifkan unduhan .docx.")


def _render_tab_grafik() -> None:
    """Render the 'Grafik' tab: display all generated chart images."""
    paths = st.session_state.chart_paths
    if not paths:
        st.info("Belum ada grafik yang dihasilkan.")
        return

    st.markdown(
        f'<p class="ip-section-title">📉 Grafik yang Dihasilkan '
        f'<span class="badge">{len(paths)} grafik</span></p>',
        unsafe_allow_html=True,
    )

    # Two-column grid
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


def _render_tab_log() -> None:
    """Render the 'Log Agen' tab: live timeline of tool calls."""
    log: list[StepEvent] = st.session_state.step_log

    if not log:
        st.info("Log kosong. Jalankan analisis untuk melihat langkah-langkah agen.")
        return

    st.markdown(
        f'<p class="ip-section-title">🔍 Timeline Agen '
        f'<span class="badge">{len(log)} langkah</span></p>',
        unsafe_allow_html=True,
    )

    # Tool icon mapping
    tool_icons: dict[str, str] = {
        "get_overview": "🔬",
        "get_correlations": "📐",
        "group_summary": "📊",
        "detect_outliers": "🚨",
        "make_chart": "📈",
    }

    for evt in log:
        icon = tool_icons.get(evt.tool_name, "🔧")
        label = f"{icon} Langkah {evt.step} — `{evt.tool_name}`"

        with st.expander(label, expanded=False):
            # Input arguments
            if evt.tool_input:
                st.markdown("**Argumen:**")
                st.code(
                    json.dumps(evt.tool_input, ensure_ascii=False, indent=2),
                    language="json",
                )

            # Result preview (truncate long results)
            try:
                parsed_result = json.loads(evt.tool_result)
                preview = json.dumps(parsed_result, ensure_ascii=False, indent=2)
            except Exception:
                preview = str(evt.tool_result)

            if len(preview) > 800:
                preview = preview[:800] + "\n…(dipotong untuk tampilan)"

            st.markdown("**Hasil:**")
            st.code(preview, language="json")

            # Inline chart thumbnail
            if evt.chart_path and Path(evt.chart_path).exists():
                st.image(
                    evt.chart_path,
                    caption=f"Grafik: {Path(evt.chart_path).name}",
                    use_container_width=True,
                )


# ---------------------------------------------------------------------------
# Agent runner (called when running == True)
# ---------------------------------------------------------------------------

def _run_agent_if_needed() -> None:
    """
    If session_state.running is True, execute the agent loop synchronously.

    Collects all StepEvents and the ReportEvent, then reruns Streamlit
    to display the results.
    """
    if not st.session_state.running:
        return

    df = st.session_state.df
    focus = st.session_state.focus_value

    placeholder = st.empty()
    placeholder.info("⏳ Agen AI sedang menganalisis data… Harap tunggu.")

    try:
        for event in run_agent(df, focus=focus):
            if isinstance(event, StepEvent):
                st.session_state.step_log.append(event)
                if event.chart_path and event.chart_path not in st.session_state.chart_paths:
                    st.session_state.chart_paths.append(event.chart_path)

            elif isinstance(event, ReportEvent):
                st.session_state.report = event
                # Merge chart paths from ReportEvent
                for cp in event.chart_paths:
                    if cp not in st.session_state.chart_paths:
                        st.session_state.chart_paths.append(cp)

            elif isinstance(event, ErrorEvent):
                st.session_state.error = event.message

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
    """Render the main content: header, data panel, tabs."""
    # ── Page header ────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="margin-bottom:1rem;">
          <h1 style="color:{config.PRIMARY_COLOR}; margin:0; font-size:1.8rem;">
            📊 InsightPilot
          </h1>
          <p style="color:{config.TEXT_MUTED}; margin:2px 0 0; font-size:0.9rem;">
            Auto-Report Generator · IBM AI Builders Challenge
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df: pd.DataFrame | None = st.session_state.df

    # ── Demo / API key notice when no data loaded ─────────────────────────
    if df is None and not st.session_state.demo_mode:
        st.markdown(
            f"""
            <div style="text-align:center; padding:4rem 1rem; color:{config.TEXT_MUTED};">
              <div style="font-size:4rem; margin-bottom:0.5rem;">📂</div>
              <h3 style="color:{config.PRIMARY_COLOR};">Belum Ada Data</h3>
              <p style="max-width:420px; margin:0 auto;">
                Unggah file CSV/Excel atau pilih dataset contoh di sidebar,
                lalu klik <b>Buat Laporan</b>.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # ── KPI cards + preview (only when data is loaded) ────────────────────
    if df is not None:
        _render_data_panel(df)

    # ── Error banner ──────────────────────────────────────────────────────
    if st.session_state.error:
        st.error(f"⚠️ {st.session_state.error}")

    # ── Three-tab panel ───────────────────────────────────────────────────
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
