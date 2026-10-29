"""Interactive data visualization analysis and metadata generation.

Analyzes query results to determine chart suitability, optimal chart type,
axis assignments, labels, and formatted datasets for Chart.js.
"""

from decimal import Decimal
import re
from typing import Any


def _is_numeric(value: Any) -> bool:
    """Return True if value can be treated as a numerical metric."""
    if value is None:
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return False
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def _to_float(value: Any) -> float | None:
    """Safely convert a numeric value or numeric string to float."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _format_metric_name(col: str) -> str:
    """Format raw SQL column names (e.g. 'AVG(marks)', 'avg_marks', 'student_count') into clean labels."""
    if not col:
        return ""
    agg_match = re.match(r"^([a-zA-Z]+)\((.*?)\)$", col.strip())
    if agg_match:
        agg = agg_match.group(1).upper()
        inner = agg_match.group(2).strip()
        agg_names = {
            "AVG": "Average",
            "AVERAGE": "Average",
            "SUM": "Total",
            "TOTAL": "Total",
            "COUNT": "Count of",
            "MIN": "Min",
            "MAX": "Max",
        }
        prefix = agg_names.get(agg, agg.capitalize())
        if inner == "*":
            return "Total Count" if prefix == "Count of" else f"{prefix} Total"
        inner_formatted = " ".join(w.capitalize() for w in re.split(r"[_\s]+", inner) if w)
        return f"{prefix} {inner_formatted}".strip()

    parts = [w for w in re.split(r"[_\s]+", col) if w]
    word_map = {
        "avg": "Average",
        "cnt": "Count",
        "min": "Min",
        "max": "Max",
    }
    formatted = [word_map.get(w.lower(), w.capitalize()) for w in parts]
    return " ".join(formatted).strip() or col


def _detect_user_chart_preference(question: str) -> str | None:
    """Detect if the user explicitly requested a specific chart type in the question."""
    q = question.lower()
    if "horizontal bar" in q:
        return "horizontalBar"
    if "pie" in q:
        return "pie"
    if "doughnut" in q or "donut" in q:
        return "doughnut"
    if "scatter" in q:
        return "scatter"
    if "line" in q:
        return "line"
    if "bar" in q or "column" in q:
        return "bar"
    return None


def build_chart_metadata(question: str, columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Inspect query results and generate structured Chart.js metadata if suitable."""
    fallback_result = {
        "suitable": False,
        "chart_type": None,
        "available_types": [],
        "title": None,
        "x_field": None,
        "y_fields": [],
        "labels": [],
        "datasets": [],
        "reason": None,
    }

    # 1. Edge Case: Empty data
    if not rows or not columns:
        fallback_result["reason"] = "No data returned to visualize."
        return fallback_result

    # 2. Edge Case: Single scalar value (e.g. SELECT COUNT(*) FROM students)
    if len(rows) == 1 and len(columns) == 1:
        fallback_result["reason"] = "Query returned a single scalar value. Best displayed as a direct metric."
        return fallback_result

    # 3. Classify columns by inspecting data types across rows
    col_stats: dict[str, dict[str, Any]] = {}
    for col in columns:
        vals = [row.get(col) for row in rows]
        non_null_vals = [v for v in vals if v is not None]
        numeric_count = sum(1 for v in non_null_vals if _is_numeric(v))
        total_non_null = len(non_null_vals)
        is_num = total_non_null > 0 and (numeric_count / total_non_null >= 0.8)
        col_stats[col] = {
            "is_numeric": is_num,
            "non_null_count": total_non_null,
            "sample_val": non_null_vals[0] if non_null_vals else None,
        }

    numeric_cols = [col for col in columns if col_stats[col]["is_numeric"]]
    categorical_cols = [col for col in columns if not col_stats[col]["is_numeric"]]

    # 4. Check if any numeric metric exists
    if not numeric_cols:
        fallback_result["reason"] = "Query contains no numeric metrics to plot on a chart axis."
        return fallback_result

    # 5. Determine X-axis and Y-axis
    x_field: str | None = None
    y_fields: list[str] = []

    if categorical_cols:
        # Choose the first categorical column as X-axis
        x_field = categorical_cols[0]
        y_fields = numeric_cols
    else:
        # All columns are numeric!
        if len(numeric_cols) == 1:
            # Single numeric column with multiple rows (e.g. list of marks)
            x_field = None
            y_fields = numeric_cols
        else:
            # If there's an 'id' or order-like column, make it X, otherwise first numeric is X
            id_col = next((c for c in numeric_cols if c.lower() in {"id", "rank", "index", "order_id"}), None)
            if id_col:
                x_field = id_col
                y_fields = [c for c in numeric_cols if c != id_col]
            else:
                x_field = numeric_cols[0]
                y_fields = numeric_cols[1:]

    if not y_fields:
        fallback_result["reason"] = "Could not identify distinct numerical measures for the Y-axis."
        return fallback_result

    # 6. Extract Labels
    if x_field:
        labels = [str(row.get(x_field) if row.get(x_field) is not None else "(empty)") for row in rows]
    else:
        labels = [f"Item {i + 1}" for i in range(len(rows))]

    # 7. Extract Datasets
    datasets = []
    for y_col in y_fields:
        series_data = [_to_float(row.get(y_col)) for row in rows]
        datasets.append({
            "field": y_col,
            "label": _format_metric_name(y_col),
            "data": series_data,
        })

    # 8. Determine Default Chart Type and Available Alternatives
    preferred_type = _detect_user_chart_preference(question)
    row_count = len(rows)
    all_positive = all(
        (v is not None and v >= 0) for ds in datasets for v in ds["data"]
    )

    available_types = ["bar", "horizontalBar", "line"]
    if len(y_fields) == 1 and all_positive and 2 <= row_count <= 10:
        available_types.extend(["pie", "doughnut"])

    # Determine default chart type
    if preferred_type and preferred_type in available_types:
        chart_type = preferred_type
    elif preferred_type == "pie" and all_positive and len(y_fields) == 1:
        chart_type = "pie"
    elif preferred_type == "doughnut" and all_positive and len(y_fields) == 1:
        chart_type = "doughnut"
    elif row_count > 8 or (labels and max(len(l) for l in labels) > 14):
        chart_type = "horizontalBar"
    elif len(y_fields) == 1 and all_positive and 2 <= row_count <= 6 and any(w in question.lower() for w in ["distribution", "share", "proportion", "breakdown"]):
        chart_type = "pie"
    else:
        chart_type = "bar"

    # 9. Formulate Chart Title
    y_label_str = ", ".join(ds["label"] for ds in datasets)
    x_label_str = _format_metric_name(x_field) if x_field else "Categories"
    title = f"{y_label_str} by {x_label_str}"

    return {
        "suitable": True,
        "chart_type": chart_type,
        "available_types": available_types,
        "title": title,
        "x_field": x_field,
        "y_fields": y_fields,
        "labels": labels,
        "datasets": datasets,
        "reason": None,
    }
