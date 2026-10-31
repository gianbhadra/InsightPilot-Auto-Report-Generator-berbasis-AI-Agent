"""
agent.py
--------
Gemini-powered function-calling agent loop for InsightPilot v3.

Key design decisions for the free tier:
  • Only column names + 5 sample rows are sent to the model (never full data).
  • Each tool result is truncated to TOOL_RESULT_MAX_CHARS before being sent back.
  • HTTP 429 / ResourceExhausted → retry up to 3×  with 2 s / 4 s / 8 s backoff,
    then fall back to demo mode with an ErrorEvent.
  • Missing API key → immediate ErrorEvent (demo mode in app.py).
  • Report results are cached by (file_hash, focus) so re-running the same dataset
    with the same focus does not consume quota.

Usage
-----
    from agent import run_agent, StepEvent, ReportEvent, ErrorEvent

    for event in run_agent(df, focus="Analisis penjualan per cabang",
                           file_hash="abc123"):
        if isinstance(event, StepEvent):
            print(f"Step {event.step}: {event.tool_name}")
        elif isinstance(event, ReportEvent):
            print(event.report_markdown)
        elif isinstance(event, ErrorEvent):
            print("Error:", event.message)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

import config
from tools import FUNCTION_DECLARATIONS, dispatch_tool

# ---------------------------------------------------------------------------
# Lazy Gemini SDK import — so the app can boot even without google-genai
# installed (demo mode still works).
# ---------------------------------------------------------------------------
try:
    import google.genai as genai
    import google.genai.types as genai_types
    GENAI_AVAILABLE: bool = True
except ImportError:
    GENAI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Module-level report cache  {cache_key: ReportEvent}
# This persists for the lifetime of the Streamlit process, across reruns.
# ---------------------------------------------------------------------------
_REPORT_CACHE: dict[str, "ReportEvent"] = {}


# ---------------------------------------------------------------------------
# Event dataclasses emitted by the generator
# ---------------------------------------------------------------------------

@dataclass
class StepEvent:
    """Emitted once for each function call made by the agent."""
    step: int
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: str        # raw JSON string returned by dispatch_tool
    chart_path: str | None = None


@dataclass
class ReportEvent:
    """Emitted once when the agent produces its final Markdown report."""
    report_markdown: str
    steps_taken: int
    chart_paths: list[str] = field(default_factory=list)
    from_cache: bool = False


@dataclass
class ErrorEvent:
    """Emitted on quota exhaustion, missing key, or unrecoverable errors."""
    message: str
    is_quota_error: bool = False   # True → caller should show demo mode


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_cache_key(file_hash: str, focus: str) -> str:
    """Stable cache key from file hash + normalised focus text."""
    combined = f"{file_hash}|{focus.strip().lower()}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _build_initial_prompt(df: pd.DataFrame, focus: str) -> str:
    """
    Compose the opening user message to send to Gemini.

    Only column names and PROMPT_SAMPLE_ROWS sample rows are included —
    never the full dataset — to stay within free-tier token limits.
    """
    cols = ", ".join(df.columns.tolist())
    shape = f"{len(df):,} baris × {len(df.columns)} kolom"
    sample_md = df.head(config.PROMPT_SAMPLE_ROWS).to_markdown(index=False)

    msg = (
        f"Saya memiliki dataset dengan {shape}.\n"
        f"Nama kolom: {cols}.\n\n"
        f"Contoh {config.PROMPT_SAMPLE_ROWS} baris pertama:\n"
        f"```\n{sample_md}\n```\n"
    )
    if focus:
        msg += f"\nFokus analisis: {focus}\n"

    msg += (
        "\nLakukan analisis menyeluruh menggunakan tools yang tersedia. "
        "Mulai dengan get_overview. Buat minimal 2 grafik. "
        "Setelah selesai, tulis laporan akhir Bahasa Indonesia dengan bagian:\n"
        "## Ringkasan Eksekutif\n"
        "## Kualitas Data\n"
        "## Temuan Utama\n"
        "## Rekomendasi\n"
        f"Batas laporan: {config.REPORT_MAX_WORDS} kata. "
        "Gunakan HANYA angka dari hasil tool."
    )
    return msg


def _truncate(text: str, max_chars: int = config.TOOL_RESULT_MAX_CHARS) -> str:
    """Truncate a string to *max_chars* with a suffix if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…(hasil dipotong untuk efisiensi)"


def _extract_chart_path(raw_json: str) -> str | None:
    """Return file_path from a make_chart JSON result, or None."""
    try:
        data = json.loads(raw_json)
        if isinstance(data, dict):
            return data.get("file_path") or None
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _is_quota_error(exc: Exception) -> bool:
    """Return True if *exc* looks like a 429 / ResourceExhausted error."""
    msg = str(exc).lower()
    return (
        "429" in msg
        or "quota" in msg
        or "resource_exhausted" in msg
        or "resourceexhausted" in msg
        or "rate" in msg
    )


def _call_with_retry(
    fn,
    *args,
    attempts: int = config.RETRY_ATTEMPTS,
    backoff: list[int] = config.RETRY_BACKOFF_SECONDS,
    **kwargs,
) -> tuple[Any, str | None]:
    """
    Call *fn(*args, **kwargs)* with exponential backoff on quota errors.

    Returns
    -------
    (result, error_message)
      error_message is None on success, a human-readable string on failure.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs), None
        except Exception as exc:
            last_exc = exc
            if _is_quota_error(exc):
                if attempt < attempts - 1:
                    wait = backoff[attempt] if attempt < len(backoff) else backoff[-1]
                    time.sleep(wait)
                    continue
                # All retries exhausted
                return None, (
                    f"Kuota Gemini API habis setelah {attempts} percobaan. "
                    "Laporan demo ditampilkan. Coba lagi dalam beberapa menit."
                )
            else:
                # Non-quota error — don't retry
                return None, f"Kesalahan API Gemini: {exc}"

    return None, f"Gagal memanggil API setelah {attempts} percobaan: {last_exc}"


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run_agent(
    df: pd.DataFrame,
    focus: str = "",
    file_hash: str = "",
) -> Generator[StepEvent | ReportEvent | ErrorEvent, None, None]:
    """
    Run the InsightPilot Gemini function-calling agent loop against *df*.

    This is a **generator** — iterate with ``for`` to receive events one at a time.
    Events:
      * :class:`StepEvent`   – a tool was called; yields after each call
      * :class:`ReportEvent` – the agent finished; contains the Markdown report
      * :class:`ErrorEvent`  – quota / key / network failure (is_quota_error=True
                               means app should fall back to demo mode)

    Free-tier safeguards:
      - Only column names + 5 sample rows are sent to the model.
      - Tool results truncated to TOOL_RESULT_MAX_CHARS.
      - 429 retried 3× with 2 s / 4 s / 8 s backoff.
      - Results cached per (file_hash, focus).

    Parameters
    ----------
    df        : pd.DataFrame   Dataset to analyse.
    focus     : str            Optional user-specified analysis focus.
    file_hash : str            SHA256 hex prefix of the uploaded file bytes,
                               used for caching.  Pass "" to disable caching.
    """
    # ------------------------------------------------------------------
    # 0. Cache check
    # ------------------------------------------------------------------
    cache_key = _make_cache_key(file_hash, focus) if file_hash else ""
    if cache_key and cache_key in _REPORT_CACHE:
        cached = _REPORT_CACHE[cache_key]
        yield ReportEvent(
            report_markdown=cached.report_markdown,
            steps_taken=cached.steps_taken,
            chart_paths=cached.chart_paths,
            from_cache=True,
        )
        return

    # ------------------------------------------------------------------
    # 1. API key / SDK check
    # ------------------------------------------------------------------
    if not config.GEMINI_API_KEY:
        yield ErrorEvent(
            "GEMINI_API_KEY tidak ditemukan. Set environment variable atau "
            "aktifkan Mode Demo di sidebar.",
            is_quota_error=True,
        )
        return

    if not GENAI_AVAILABLE:
        yield ErrorEvent(
            "Paket 'google-genai' tidak terinstal. "
            "Jalankan: pip install google-genai",
            is_quota_error=False,
        )
        return

    # ------------------------------------------------------------------
    # 2. Build Gemini client + tool config
    # ------------------------------------------------------------------
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Build Tool object from our plain-dict declarations
    tools = [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(**fd)
                for fd in FUNCTION_DECLARATIONS
            ]
        )
    ]

    gen_config = genai_types.GenerateContentConfig(
        system_instruction=config.SYSTEM_PROMPT,
        tools=tools,
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
        temperature=0.2,    # low temp for factual, consistent reports
    )

    # ------------------------------------------------------------------
    # 3. Conversation history (list of Content objects)
    # ------------------------------------------------------------------
    history: list[genai_types.Content] = [
        genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=_build_initial_prompt(df, focus))],
        )
    ]

    step: int = 0
    chart_paths: list[str] = []

    # ------------------------------------------------------------------
    # 4. Main function-calling loop
    # ------------------------------------------------------------------
    while step < config.MAX_AGENT_STEPS:

        # ---- Call the model -------------------------------------------
        response, err_msg = _call_with_retry(
            client.models.generate_content,
            model=config.GEMINI_MODEL,
            contents=history,
            config=gen_config,
        )

        if err_msg:
            is_quota = _is_quota_error(Exception(err_msg))
            yield ErrorEvent(message=err_msg, is_quota_error=is_quota)
            return

        if response is None or not response.candidates:
            yield ErrorEvent(
                "Tidak ada respons dari Gemini. Coba jalankan ulang.",
                is_quota_error=False,
            )
            return

        candidate = response.candidates[0]

        # Append model response to history
        history.append(candidate.content)

        # ---- Collect function calls in this response ------------------
        function_calls = [
            part for part in candidate.content.parts
            if part.function_call is not None
        ]

        # ---- If no function calls → model produced final text ---------
        if not function_calls:
            # Gather all text parts as the report
            report_text = "\n\n".join(
                part.text
                for part in candidate.content.parts
                if hasattr(part, "text") and part.text and part.text.strip()
            ).strip()

            if report_text:
                report_event = ReportEvent(
                    report_markdown=report_text,
                    steps_taken=step,
                    chart_paths=chart_paths,
                )
                if cache_key:
                    _REPORT_CACHE[cache_key] = report_event
                yield report_event
            else:
                yield ErrorEvent(
                    "Model berhenti tanpa menghasilkan laporan. "
                    "Coba tambahkan fokus analisis yang lebih spesifik.",
                    is_quota_error=False,
                )
            return

        # ---- Execute each function call and collect results -----------
        function_response_parts: list[genai_types.Part] = []

        for fc_part in function_calls:
            fc = fc_part.function_call
            step += 1

            tool_name: str = fc.name
            # fc.args is a Struct-like mapping; convert to plain dict
            tool_args: dict[str, Any] = dict(fc.args) if fc.args else {}

            # Execute the tool (never raises — always returns JSON str)
            raw_result: str = dispatch_tool(tool_name, tool_args, df)

            # Truncate before sending back to model
            truncated: str = _truncate(raw_result)

            # Track chart paths
            chart_path = _extract_chart_path(raw_result)
            if chart_path and chart_path not in chart_paths:
                chart_paths.append(chart_path)

            # Emit to UI
            yield StepEvent(
                step=step,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=raw_result,
                chart_path=chart_path,
            )

            # Build FunctionResponse part for Gemini
            try:
                result_data = json.loads(truncated)
            except json.JSONDecodeError:
                result_data = {"raw": truncated}

            function_response_parts.append(
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name=tool_name,
                        response={"result": result_data},
                    )
                )
            )

            if step >= config.MAX_AGENT_STEPS:
                break

        # ---- Feed all function responses back in one Content ----------
        if function_response_parts:
            history.append(
                genai_types.Content(
                    role="function",
                    parts=function_response_parts,
                )
            )

        # ---- If step cap hit, force a final text-only response --------
        if step >= config.MAX_AGENT_STEPS:
            history.append(
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part(
                            text=(
                                f"Anda telah mencapai batas {config.MAX_AGENT_STEPS} "
                                "langkah. SEKARANG tulis laporan akhir Bahasa Indonesia "
                                "dengan TEPAT empat bagian:\n"
                                "## Ringkasan Eksekutif\n"
                                "## Kualitas Data\n"
                                "## Temuan Utama\n"
                                "## Rekomendasi\n\n"
                                f"Maks {config.REPORT_MAX_WORDS} kata. "
                                "Angka dari tool results saja. "
                                "JANGAN panggil tool lagi."
                            )
                        )
                    ],
                )
            )

            # Final call — no tools
            final_config = genai_types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
                max_output_tokens=config.MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )
            final_resp, err_msg = _call_with_retry(
                client.models.generate_content,
                model=config.GEMINI_MODEL,
                contents=history,
                config=final_config,
            )

            if err_msg:
                yield ErrorEvent(
                    message=err_msg,
                    is_quota_error=_is_quota_error(Exception(err_msg)),
                )
                return

            if final_resp and final_resp.candidates:
                report_text = "\n\n".join(
                    part.text
                    for part in final_resp.candidates[0].content.parts
                    if hasattr(part, "text") and part.text and part.text.strip()
                ).strip()
                report_event = ReportEvent(
                    report_markdown=report_text or "Laporan tidak dapat dihasilkan.",
                    steps_taken=step,
                    chart_paths=chart_paths,
                )
                if cache_key:
                    _REPORT_CACHE[cache_key] = report_event
                yield report_event
            else:
                yield ErrorEvent(
                    "Tidak ada respons dari Gemini untuk laporan akhir.",
                    is_quota_error=False,
                )
            return

    # Safety net — should never be reached
    yield ErrorEvent(
        "Loop agen selesai tanpa menghasilkan laporan. Coba jalankan ulang.",
        is_quota_error=False,
    )
