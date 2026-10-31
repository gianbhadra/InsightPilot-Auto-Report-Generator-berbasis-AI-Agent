"""
agent.py
--------
Anthropic-powered agent loop for InsightPilot v2.

The agent receives a DataFrame and an optional analysis focus, then
iteratively calls the five analysis tools (get_overview, get_correlations,
group_summary, detect_outliers, make_chart) until it either produces a
final Markdown report or hits the MAX_AGENT_STEPS cap.

Usage
-----
    from agent import run_agent, StepEvent, ReportEvent, ErrorEvent

    for event in run_agent(df, focus="Analisis penjualan per cabang"):
        if isinstance(event, StepEvent):
            print(f"Step {event.step}: {event.tool_name}")
        elif isinstance(event, ReportEvent):
            print(event.report_markdown)
        elif isinstance(event, ErrorEvent):
            print("Error:", event.message)
"""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import anthropic
import pandas as pd

import config
from tools import TOOL_SCHEMAS, dispatch_tool


# ---------------------------------------------------------------------------
# Event dataclasses emitted by the generator
# ---------------------------------------------------------------------------

@dataclass
class StepEvent:
    """Emitted once for each tool call made by the agent."""
    step: int
    tool_name: str
    tool_input: dict[str, Any]
    tool_result: str        # raw JSON string returned by dispatch_tool
    chart_path: str | None = None  # populated when tool == "make_chart"


@dataclass
class ReportEvent:
    """Emitted once when the agent produces its final Markdown report."""
    report_markdown: str
    steps_taken: int
    chart_paths: list[str] = field(default_factory=list)


@dataclass
class ErrorEvent:
    """Emitted when an unrecoverable error prevents report generation."""
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_initial_message(df: pd.DataFrame, focus: str) -> str:
    """
    Compose the opening user message sent to the agent.

    Parameters
    ----------
    df : pd.DataFrame
    focus : str   Optional analysis focus from the user.

    Returns
    -------
    str
    """
    cols = ", ".join(df.columns.tolist())
    shape = f"{len(df):,} baris × {len(df.columns)} kolom"

    msg = (
        f"Saya memiliki dataset dengan {shape}.\n"
        f"Kolom: {cols}.\n"
    )
    if focus:
        msg += f"\nFokus analisis yang diminta: {focus}\n"

    msg += (
        "\nLakukan analisis menyeluruh dengan tools yang tersedia. "
        "Mulai dengan get_overview, lalu gunakan tools lain sesuai temuan. "
        "Buat minimal 2 grafik. "
        "Terakhir, tulis laporan akhir dalam Bahasa Indonesia dengan bagian:\n"
        "## Ringkasan Eksekutif\n"
        "## Kualitas Data\n"
        "## Temuan Utama\n"
        "## Rekomendasi\n"
        f"Laporan harus di bawah {config.REPORT_MAX_WORDS} kata "
        "dan hanya menggunakan angka dari hasil tool."
    )
    return msg


def _extract_text(content: list) -> str:
    """Join all text blocks from an Anthropic response content list."""
    return "\n\n".join(
        block.text
        for block in content
        if hasattr(block, "text") and block.text.strip()
    ).strip()


def _extract_chart_path(raw_json: str) -> str | None:
    """Parse make_chart result JSON and return the file_path, or None."""
    try:
        data = json.loads(raw_json)
        if isinstance(data, dict):
            return data.get("file_path") or None
    except (json.JSONDecodeError, TypeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run_agent(
    df: pd.DataFrame,
    focus: str = "",
) -> Generator[StepEvent | ReportEvent | ErrorEvent, None, None]:
    """
    Run the InsightPilot agent loop against *df*.

    This is a **generator**: call ``next()`` or iterate with ``for``
    to process one event at a time.  Each event is one of:

    * :class:`StepEvent`   – a tool was called (yielded per tool call)
    * :class:`ReportEvent` – the agent finished; contains the markdown report
    * :class:`ErrorEvent`  – an unrecoverable failure occurred

    The generator always terminates (it never hangs).

    Parameters
    ----------
    df : pd.DataFrame
    focus : str   Optional user-specified analysis focus.

    Yields
    ------
    StepEvent | ReportEvent | ErrorEvent
    """
    if not config.ANTHROPIC_API_KEY:
        yield ErrorEvent(
            "ANTHROPIC_API_KEY tidak ditemukan. "
            "Harap set environment variable ANTHROPIC_API_KEY."
        )
        return

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": _build_initial_message(df, focus)}
    ]

    step: int = 0
    chart_paths: list[str] = []

    # -----------------------------------------------------------------------
    # Main agent loop
    # -----------------------------------------------------------------------
    while step < config.MAX_AGENT_STEPS:

        # --- Call the model ------------------------------------------------
        try:
            response = client.messages.create(
                model=config.MODEL_NAME,
                max_tokens=config.MAX_TOKENS,
                system=config.SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except anthropic.AuthenticationError:
            yield ErrorEvent(
                "API key tidak valid. Periksa nilai ANTHROPIC_API_KEY Anda."
            )
            return
        except anthropic.RateLimitError:
            yield ErrorEvent(
                "Rate limit Anthropic tercapai. Tunggu beberapa detik lalu coba lagi."
            )
            return
        except anthropic.BadRequestError as exc:
            yield ErrorEvent(f"Permintaan tidak valid ke API: {exc}")
            return
        except anthropic.APIConnectionError:
            yield ErrorEvent(
                "Tidak dapat terhubung ke API Anthropic. Periksa koneksi internet."
            )
            return
        except anthropic.APIError as exc:
            yield ErrorEvent(f"Kesalahan API Anthropic: {exc}")
            return

        # --- Append assistant message to history ---------------------------
        messages.append({"role": "assistant", "content": response.content})

        # --- Check stop_reason: end_turn means no more tool calls ----------
        if response.stop_reason == "end_turn":
            report_text = _extract_text(response.content)
            if report_text:
                yield ReportEvent(
                    report_markdown=report_text,
                    steps_taken=step,
                    chart_paths=chart_paths,
                )
            else:
                yield ErrorEvent(
                    "Agen berhenti tanpa menghasilkan teks laporan. "
                    "Coba jalankan ulang dengan fokus analisis yang lebih spesifik."
                )
            return

        # --- Process each tool_use block in the response ------------------
        tool_results_content: list[dict[str, Any]] = []
        any_tool_called = False

        for block in response.content:
            if block.type != "tool_use":
                continue

            any_tool_called = True
            step += 1

            tool_name: str = block.name
            tool_input: dict[str, Any] = block.input or {}

            # Execute the tool – always returns a JSON string
            raw_result: str = dispatch_tool(tool_name, tool_input, df)

            # Track chart file paths
            chart_path = _extract_chart_path(raw_result)
            if chart_path and chart_path not in chart_paths:
                chart_paths.append(chart_path)

            # Emit step event to UI
            yield StepEvent(
                step=step,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_result=raw_result,
                chart_path=chart_path,
            )

            # Prepare tool result for next API call
            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": raw_result,
            })

            # Honour the step cap even within a multi-tool response
            if step >= config.MAX_AGENT_STEPS:
                break

        # --- If no tool was called (unexpected), try to salvage text ------
        if not any_tool_called:
            report_text = _extract_text(response.content)
            if report_text:
                yield ReportEvent(
                    report_markdown=report_text,
                    steps_taken=step,
                    chart_paths=chart_paths,
                )
            else:
                yield ErrorEvent(
                    "Agen tidak memanggil tool apapun dan tidak menghasilkan laporan."
                )
            return

        # --- Feed tool results back into the conversation -----------------
        if tool_results_content:
            messages.append({"role": "user", "content": tool_results_content})

        # --- If step cap reached, request forced final report -------------
        if step >= config.MAX_AGENT_STEPS:
            messages.append({
                "role": "user",
                "content": (
                    f"Anda telah mencapai batas maksimum {config.MAX_AGENT_STEPS} langkah. "
                    "SEKARANG tulis laporan akhir dalam Bahasa Indonesia dengan TEPAT "
                    "empat bagian berikut:\n"
                    "## Ringkasan Eksekutif\n"
                    "## Kualitas Data\n"
                    "## Temuan Utama\n"
                    "## Rekomendasi\n\n"
                    f"Batas kata: {config.REPORT_MAX_WORDS}. "
                    "Gunakan HANYA angka yang sudah Anda dapatkan dari tool results. "
                    "JANGAN memanggil tool lagi."
                ),
            })
            try:
                final_resp = client.messages.create(
                    model=config.MODEL_NAME,
                    max_tokens=config.MAX_TOKENS,
                    system=config.SYSTEM_PROMPT,
                    messages=messages,
                    # No tools passed → forces text-only response
                )
                report_text = _extract_text(final_resp.content)
                yield ReportEvent(
                    report_markdown=report_text or "Laporan tidak dapat dihasilkan.",
                    steps_taken=step,
                    chart_paths=chart_paths,
                )
            except anthropic.APIError as exc:
                yield ErrorEvent(f"Gagal menghasilkan laporan akhir: {exc}")
            return

    # Should not be reached, but safety net
    yield ErrorEvent(
        "Loop agen selesai tanpa menghasilkan laporan. "
        "Coba jalankan ulang."
    )
