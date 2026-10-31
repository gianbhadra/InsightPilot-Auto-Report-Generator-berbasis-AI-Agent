"""
tools.py
--------
Data-analysis tools for InsightPilot v2.

Five tools exposed to the Anthropic agent via tool_use:
  1. get_overview       – shape, dtypes, missing values, duplicates, descriptive stats
  2. get_correlations   – pairwise Pearson/Spearman/Kendall correlations
  3. group_summary      – groupby aggregation
  4. detect_outliers    – IQR-based outlier detection
  5. make_chart         – bar / line / hist PNG generation

Each function returns a JSON-serialisable dict.
Tool errors are returned AS data (not raised) so the agent can self-correct.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import matplotlib
matplotlib.use("Agg")  # must precede pyplot import — non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CHART_DIR, CHART_DPI, CHART_PALETTE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_json(obj: Any) -> Any:
    """Recursively convert numpy / NaN / inf to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_json(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _safe_json(obj.tolist())
    return obj


def _ensure_chart_dir() -> None:
    """Create the charts output directory if it does not exist."""
    os.makedirs(CHART_DIR, exist_ok=True)


def _validate_column(df: pd.DataFrame, col: str, label: str = "kolom") -> str | None:
    """
    Return an error string if *col* is not in *df*, else None.

    Parameters
    ----------
    df : pd.DataFrame
    col : str
    label : str
        Human-readable label for error messages.
    """
    if col not in df.columns:
        available = ", ".join(f"'{c}'" for c in df.columns)
        return (
            f"{label} '{col}' tidak ditemukan. "
            f"Kolom yang tersedia: {available}."
        )
    return None


# ---------------------------------------------------------------------------
# Tool 1 – get_overview
# ---------------------------------------------------------------------------

def get_overview(df: pd.DataFrame) -> dict[str, Any]:
    """
    Return a high-level statistical overview of *df*.

    Covers shape, column types, missing values per column, duplicate rows,
    and descriptive statistics for numeric columns.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    dict  JSON-serialisable overview.
    """
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()

    # Descriptive stats for numeric columns
    desc: dict[str, Any] = {}
    if numeric_cols:
        stats_df = df[numeric_cols].describe().round(4)
        desc = _safe_json(stats_df.to_dict())

    # Per-column missing info
    missing_series = df.isnull().sum()
    missing_pct = (missing_series / len(df) * 100).round(2)
    missing_info = {
        col: {
            "count": int(missing_series[col]),
            "pct": float(missing_pct[col]),
        }
        for col in df.columns
        if missing_series[col] > 0
    }

    # Unique counts for categorical columns
    unique_counts = {col: int(df[col].nunique()) for col in categorical_cols}

    return _safe_json({
        "shape": {"rows": int(len(df)), "columns": int(len(df.columns))},
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "missing_values": missing_info,
        "total_missing_cells": int(df.isnull().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "descriptive_stats": desc,
        "unique_counts": unique_counts,
    })


# ---------------------------------------------------------------------------
# Tool 2 – get_correlations
# ---------------------------------------------------------------------------

def get_correlations(
    df: pd.DataFrame,
    method: str = "pearson",
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Compute pairwise correlations between all numeric columns.

    Parameters
    ----------
    df : pd.DataFrame
    method : str   'pearson' | 'spearman' | 'kendall'
    top_n : int    Return only the top-N strongest pairs (by |r|).

    Returns
    -------
    dict  Correlation matrix + ranked top pairs.
    """
    # Validate method
    allowed_methods = {"pearson", "spearman", "kendall"}
    if method not in allowed_methods:
        return {
            "error": (
                f"method '{method}' tidak valid. "
                f"Gunakan salah satu dari: {', '.join(sorted(allowed_methods))}."
            )
        }

    # Need at least 2 numeric columns
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return {
            "error": (
                "Dibutuhkan minimal 2 kolom numerik untuk menghitung korelasi. "
                f"Dataset hanya memiliki {numeric_df.shape[1]} kolom numerik."
            )
        }

    # Validate top_n
    top_n = max(1, min(int(top_n), 50))

    corr_matrix = numeric_df.corr(method=method).round(4)

    # Build ranked pair list
    pairs: list[dict[str, Any]] = []
    cols = corr_matrix.columns.tolist()
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            val = corr_matrix.loc[c1, c2]
            if not np.isnan(val):
                pairs.append({
                    "col_a": c1,
                    "col_b": c2,
                    "correlation": round(float(val), 4),
                })

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return _safe_json({
        "method": method,
        "numeric_columns": cols,
        "matrix": corr_matrix.to_dict(),
        "top_pairs": pairs[:top_n],
    })


# ---------------------------------------------------------------------------
# Tool 3 – group_summary
# ---------------------------------------------------------------------------

def group_summary(
    df: pd.DataFrame,
    group_col: str,
    agg_col: str,
    agg_func: str = "sum",
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Aggregate *agg_col* by *group_col* using *agg_func*.

    Parameters
    ----------
    df : pd.DataFrame
    group_col : str   Column to group by (usually categorical).
    agg_col : str     Numeric column to aggregate.
    agg_func : str    sum | mean | count | min | max | median
    top_n : int       Return only top-N groups (descending by value).

    Returns
    -------
    dict  Aggregated results sorted descending.
    """
    # Column validation
    err = _validate_column(df, group_col, "group_col")
    if err:
        return {"error": err}
    err = _validate_column(df, agg_col, "agg_col")
    if err:
        return {"error": err}

    allowed_funcs = {"sum", "mean", "count", "min", "max", "median"}
    if agg_func not in allowed_funcs:
        return {
            "error": (
                f"agg_func '{agg_func}' tidak valid. "
                f"Pilihan: {', '.join(sorted(allowed_funcs))}."
            )
        }

    top_n = max(1, min(int(top_n), 100))

    grouped = (
        df.groupby(group_col, dropna=False)[agg_col]
        .agg(agg_func)
        .reset_index()
    )
    agg_col_name = f"{agg_func}_{agg_col}"
    grouped.columns = [group_col, agg_col_name]
    grouped = grouped.sort_values(agg_col_name, ascending=False)
    top_rows = grouped.head(top_n).to_dict(orient="records")

    return _safe_json({
        "group_col": group_col,
        "agg_col": agg_col,
        "agg_func": agg_func,
        "total_groups": int(df[group_col].nunique(dropna=False)),
        "shown_top_n": len(top_rows),
        "results": top_rows,
    })


# ---------------------------------------------------------------------------
# Tool 4 – detect_outliers (IQR method)
# ---------------------------------------------------------------------------

def detect_outliers(
    df: pd.DataFrame,
    column: str,
    iqr_multiplier: float = 1.5,
) -> dict[str, Any]:
    """
    Detect outliers in a numeric column using the IQR (Tukey fence) method.

    An observation is an outlier if it falls below
    Q1 − iqr_multiplier × IQR  or above  Q3 + iqr_multiplier × IQR.

    Parameters
    ----------
    df : pd.DataFrame
    column : str             Numeric column to analyse.
    iqr_multiplier : float   Typically 1.5 (mild) or 3.0 (extreme).

    Returns
    -------
    dict  Summary statistics, fence bounds, outlier count, and outlier values.
    """
    err = _validate_column(df, column, "column")
    if err:
        return {"error": err}

    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        return {"error": f"Kolom '{column}' tidak memiliki nilai numerik valid."}

    if iqr_multiplier <= 0:
        iqr_multiplier = 1.5

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    lower_fence = q1 - iqr_multiplier * iqr
    upper_fence = q3 + iqr_multiplier * iqr

    outlier_mask = (series < lower_fence) | (series > upper_fence)
    outlier_values = series[outlier_mask].tolist()

    return _safe_json({
        "column": column,
        "iqr_multiplier": iqr_multiplier,
        "statistics": {
            "count": int(series.count()),
            "mean": round(float(series.mean()), 4),
            "std": round(float(series.std()), 4),
            "min": round(float(series.min()), 4),
            "q1": round(q1, 4),
            "median": round(float(series.median()), 4),
            "q3": round(q3, 4),
            "max": round(float(series.max()), 4),
            "iqr": round(iqr, 4),
        },
        "lower_fence": round(lower_fence, 4),
        "upper_fence": round(upper_fence, 4),
        "outlier_count": int(outlier_mask.sum()),
        "outlier_pct": round(float(outlier_mask.sum() / len(series) * 100), 2),
        "outlier_values": sorted(outlier_values),
    })


# ---------------------------------------------------------------------------
# Tool 5 – make_chart
# ---------------------------------------------------------------------------

def make_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str,
    title: str = "",
    top_n: int = 15,
) -> dict[str, Any]:
    """
    Create a chart and save it as a PNG file to CHART_DIR.

    Supported types
    ---------------
    bar       – grouped bar (x=category, y=numeric, aggregated with sum)
    line      – line chart (x sorted ascending)
    hist      – histogram of a single numeric column (pass x_col; set y_col=x_col)

    Parameters
    ----------
    df : pd.DataFrame
    chart_type : str   'bar' | 'line' | 'hist'
    x_col : str        Category (bar/line) or numeric column (hist).
    y_col : str        Numeric column (bar/line) or same as x_col (hist).
    title : str        Chart title (auto-generated if empty).
    top_n : int        For bar charts: limit to top-N categories.

    Returns
    -------
    dict  Contains 'file_path' on success, 'error' on failure.
    """
    _ensure_chart_dir()

    # Validate chart_type
    allowed_types = {"bar", "line", "hist"}
    if chart_type not in allowed_types:
        return {
            "error": (
                f"chart_type '{chart_type}' tidak valid. "
                f"Pilihan: {', '.join(sorted(allowed_types))}."
            )
        }

    # Validate columns (y_col == x_col is allowed for hist)
    err = _validate_column(df, x_col, "x_col")
    if err:
        return {"error": err}
    if y_col != x_col:
        err = _validate_column(df, y_col, "y_col")
        if err:
            return {"error": err}

    top_n = max(1, min(int(top_n), 50))
    filename = f"{CHART_DIR}/chart_{uuid.uuid4().hex[:8]}.png"

    # Apply consistent theme
    primary = CHART_PALETTE[0]
    palette = CHART_PALETTE

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#FFFFFF")

    try:
        if chart_type == "bar":
            # Aggregate y by x then take top_n
            plot_df = (
                df.groupby(x_col)[y_col]
                .sum()
                .reset_index()
                .sort_values(y_col, ascending=False)
                .head(top_n)
            )
            bar_colors = (palette * ((len(plot_df) // len(palette)) + 1))[
                : len(plot_df)
            ]
            ax.bar(
                plot_df[x_col].astype(str),
                plot_df[y_col],
                color=bar_colors,
                edgecolor="white",
                linewidth=0.8,
            )
            ax.set_xlabel(x_col, fontsize=10, color="#64748B")
            ax.set_ylabel(y_col, fontsize=10, color="#64748B")
            plt.xticks(rotation=38, ha="right", fontsize=8)

        elif chart_type == "line":
            plot_df = df[[x_col, y_col]].dropna().sort_values(x_col)
            ax.plot(
                plot_df[x_col].astype(str),
                plot_df[y_col],
                color=primary,
                linewidth=2.2,
                marker="o",
                markersize=4.5,
                markerfacecolor="#F59E0B",
                markeredgecolor="white",
            )
            ax.fill_between(
                range(len(plot_df)),
                plot_df[y_col],
                alpha=0.08,
                color=primary,
            )
            ax.set_xlabel(x_col, fontsize=10, color="#64748B")
            ax.set_ylabel(y_col, fontsize=10, color="#64748B")
            plt.xticks(rotation=38, ha="right", fontsize=8)

        elif chart_type == "hist":
            col = x_col  # y_col may equal x_col for histogram
            ax.hist(
                df[col].dropna(),
                bins=20,
                color=primary,
                edgecolor="white",
                linewidth=0.7,
                alpha=0.85,
            )
            ax.set_xlabel(col, fontsize=10, color="#64748B")
            ax.set_ylabel("Frekuensi", fontsize=10, color="#64748B")

        # Common formatting
        auto_title = title or f"{chart_type.title()}: {y_col} per {x_col}"
        ax.set_title(auto_title, fontsize=13, pad=12, color="#1E293B", fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines["left"].set_color("#E2E8F0")
        ax.spines["bottom"].set_color("#E2E8F0")
        ax.tick_params(colors="#64748B")
        ax.grid(axis="y", color="#F1F5F9", linewidth=0.8, linestyle="--")

        plt.tight_layout()
        plt.savefig(filename, dpi=CHART_DPI, bbox_inches="tight")
        plt.close(fig)

    except Exception as exc:
        plt.close(fig)
        return {"error": f"Gagal membuat grafik: {exc}"}

    return {
        "chart_type": chart_type,
        "file_path": filename,
        "x_col": x_col,
        "y_col": y_col,
        "title": auto_title,
        "status": "saved",
    }


# ---------------------------------------------------------------------------
# Tool dispatcher  (called by agent.py)
# ---------------------------------------------------------------------------

def dispatch_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    df: pd.DataFrame,
) -> str:
    """
    Route a tool-use call from the agent to the correct function.

    All errors (including unexpected exceptions) are returned as JSON
    so the agent can read and self-correct — no stack traces leak to the UI.

    Parameters
    ----------
    tool_name : str
    tool_input : dict   Arguments from the agent's tool_use block.
    df : pd.DataFrame   Currently loaded dataset.

    Returns
    -------
    str  JSON string (result dict or {"error": ...}).
    """
    try:
        if tool_name == "get_overview":
            result = get_overview(df)

        elif tool_name == "get_correlations":
            result = get_correlations(
                df,
                method=str(tool_input.get("method", "pearson")),
                top_n=int(tool_input.get("top_n", 10)),
            )

        elif tool_name == "group_summary":
            if "group_col" not in tool_input:
                result = {"error": "Parameter 'group_col' wajib diisi."}
            elif "agg_col" not in tool_input:
                result = {"error": "Parameter 'agg_col' wajib diisi."}
            else:
                result = group_summary(
                    df,
                    group_col=str(tool_input["group_col"]),
                    agg_col=str(tool_input["agg_col"]),
                    agg_func=str(tool_input.get("agg_func", "sum")),
                    top_n=int(tool_input.get("top_n", 10)),
                )

        elif tool_name == "detect_outliers":
            if "column" not in tool_input:
                result = {"error": "Parameter 'column' wajib diisi."}
            else:
                result = detect_outliers(
                    df,
                    column=str(tool_input["column"]),
                    iqr_multiplier=float(tool_input.get("iqr_multiplier", 1.5)),
                )

        elif tool_name == "make_chart":
            required = ["chart_type", "x_col", "y_col"]
            missing_params = [p for p in required if p not in tool_input]
            if missing_params:
                result = {
                    "error": (
                        f"Parameter wajib tidak ada: {', '.join(missing_params)}. "
                        "Diperlukan: chart_type, x_col, y_col."
                    )
                }
            else:
                result = make_chart(
                    df,
                    chart_type=str(tool_input["chart_type"]),
                    x_col=str(tool_input["x_col"]),
                    y_col=str(tool_input["y_col"]),
                    title=str(tool_input.get("title", "")),
                    top_n=int(tool_input.get("top_n", 15)),
                )

        else:
            available = "get_overview, get_correlations, group_summary, detect_outliers, make_chart"
            result = {
                "error": (
                    f"Tool '{tool_name}' tidak dikenal. "
                    f"Tools yang tersedia: {available}."
                )
            }

    except Exception as exc:
        result = {"error": f"Tool '{tool_name}' mengalami kesalahan tak terduga: {exc}"}

    return json.dumps(_safe_json(result), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_overview",
        "description": (
            "Kembalikan ringkasan statistik dataset: shape, tipe data kolom, "
            "jumlah nilai hilang per kolom, total nilai hilang, baris duplikat, "
            "statistik deskriptif kolom numerik, dan jumlah nilai unik kolom kategori. "
            "Selalu panggil tool ini pertama kali."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_correlations",
        "description": (
            "Hitung korelasi antar semua pasangan kolom numerik. "
            "Kembalikan matriks korelasi dan daftar pasangan terkuat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["pearson", "spearman", "kendall"],
                    "description": "Metode korelasi. Default: 'pearson'.",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Jumlah pasangan teratas. Default: 10.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "group_summary",
        "description": (
            "Agregasi kolom numerik berdasarkan kolom kategori. "
            "Berguna untuk membandingkan segmen (misal: penjualan per cabang)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_col": {
                    "type": "string",
                    "description": "Nama kolom kategori untuk dikelompokkan.",
                },
                "agg_col": {
                    "type": "string",
                    "description": "Nama kolom numerik yang diagregasi.",
                },
                "agg_func": {
                    "type": "string",
                    "enum": ["sum", "mean", "count", "min", "max", "median"],
                    "description": "Fungsi agregasi. Default: 'sum'.",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Jumlah grup teratas yang dikembalikan. Default: 10.",
                },
            },
            "required": ["group_col", "agg_col"],
        },
    },
    {
        "name": "detect_outliers",
        "description": (
            "Deteksi outlier pada kolom numerik menggunakan metode IQR (Tukey fence). "
            "Kembalikan batas bawah/atas, jumlah outlier, dan nilai-nilai outlier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "Nama kolom numerik yang akan dianalisis.",
                },
                "iqr_multiplier": {
                    "type": "number",
                    "description": (
                        "Pengali IQR untuk menentukan batas. "
                        "1.5 = outlier ringan, 3.0 = outlier ekstrem. Default: 1.5."
                    ),
                },
            },
            "required": ["column"],
        },
    },
    {
        "name": "make_chart",
        "description": (
            "Buat grafik dan simpan sebagai file PNG. "
            "Jenis: 'bar' (batang per kategori), 'line' (tren waktu), "
            "'hist' (distribusi kolom numerik; set y_col=x_col). "
            "Selalu buat minimal 2 grafik."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "hist"],
                    "description": "Jenis grafik.",
                },
                "x_col": {
                    "type": "string",
                    "description": "Kolom sumbu-X atau kolom kategori.",
                },
                "y_col": {
                    "type": "string",
                    "description": (
                        "Kolom sumbu-Y / nilai numerik. "
                        "Untuk hist, gunakan nama kolom yang sama dengan x_col."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Judul grafik (opsional).",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Untuk bar: batasi N kategori teratas. Default: 15.",
                },
            },
            "required": ["chart_type", "x_col", "y_col"],
        },
    },
]
