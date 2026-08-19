"""Structured report export utility supporting JSON, CSV, and formatted TXT formats.

Exports storage analysis, cleanup scan results, pre-cleanup previews, disk health,
and history records without exposing sensitive file contents or tokens.
"""

import csv
import io
import json
from typing import Any

from crapcleaner.utils.format import format_size


def export_report(
    data: Any,
    report_type: str = "scan",
    export_format: str = "json",
    output_path: str | None = None,
) -> str:
    """Format and export structured report data to JSON, CSV, or TXT."""
    fmt = export_format.lower()
    if fmt == "json":
        formatted = _export_json(data)
    elif fmt == "csv":
        formatted = _export_csv(data, report_type)
    elif fmt in ("txt", "text"):
        formatted = _export_txt(data, report_type)
    else:
        raise ValueError(f"Unsupported export format: {export_format!r}")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(formatted)

    return formatted


def _to_plain_dict(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, list):
        return [_to_plain_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain_dict(v) for k, v in obj.items()}
    return obj


def _export_json(data: Any) -> str:
    plain = _to_plain_dict(data)
    return json.dumps(plain, indent=2, default=str)


def _export_csv(data: Any, report_type: str) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    plain = _to_plain_dict(data)

    if report_type in ("scan", "cleanup_scan"):
        writer.writerow(
            ["Category ID", "Name", "Group", "Safety", "Reclaimable Bytes", "Files", "Errors"]
        )
        categories = plain.get("categories", []) if isinstance(plain, dict) else plain
        for cat in categories:
            writer.writerow(
                [
                    cat.get("category_id", ""),
                    cat.get("name", ""),
                    cat.get("group", ""),
                    cat.get("safety_level", ""),
                    cat.get("size", cat.get("estimated_size", 0)),
                    cat.get("item_count", 0),
                    "; ".join(cat.get("errors", [])),
                ]
            )

    elif report_type == "storage":
        writer.writerow(
            ["Name", "Path", "Size Bytes", "File Count", "Dir Count", "Parent Percentage"]
        )

        def _write_node(node: dict):
            writer.writerow(
                [
                    node.get("name", ""),
                    node.get("path", ""),
                    node.get("size", 0),
                    node.get("file_count", 0),
                    node.get("dir_count", 0),
                    node.get("percentage_of_parent", 0.0),
                ]
            )
            for child in node.get("children", []):
                _write_node(child)

        if isinstance(plain, dict):
            _write_node(plain)
        elif isinstance(plain, list):
            for item in plain:
                if isinstance(item, dict):
                    _write_node(item)

    elif report_type == "disk_health":
        writer.writerow(
            [
                "Device ID",
                "Model",
                "Media Type",
                "Bus Type",
                "Capacity Bytes",
                "Free Bytes",
                "Filesystem",
                "TRIM Supported",
                "TRIM Enabled",
                "Health Status",
            ]
        )
        items = plain if isinstance(plain, list) else [plain]
        for d in items:
            writer.writerow(
                [
                    d.get("device_id", ""),
                    d.get("model", ""),
                    d.get("media_type", ""),
                    d.get("bus_type", ""),
                    d.get("capacity", 0),
                    d.get("free_space", 0),
                    d.get("filesystem", ""),
                    d.get("trim_supported", ""),
                    d.get("trim_enabled", ""),
                    d.get("health_status", ""),
                ]
            )

    elif report_type == "history":
        writer.writerow(
            [
                "Timestamp",
                "Kind",
                "Files Deleted",
                "Space Recovered Bytes",
                "Skipped",
                "Dry Run",
                "Recycle Bin",
                "Categories",
            ]
        )
        items = plain if isinstance(plain, list) else [plain]
        for h in items:
            writer.writerow(
                [
                    h.get("started", ""),
                    h.get("kind", ""),
                    h.get("files_removed", 0),
                    h.get("space_recovered", 0),
                    h.get("skipped", 0),
                    h.get("dry_run", False),
                    h.get("use_recycle_bin", False),
                    "; ".join(h.get("categories", [])),
                ]
            )

    else:
        # Generic dict list fallback
        if isinstance(plain, list) and plain and isinstance(plain[0], dict):
            keys = list(plain[0].keys())
            writer.writerow(keys)
            for row in plain:
                writer.writerow([row.get(k, "") for k in keys])
        elif isinstance(plain, dict):
            writer.writerow(["Key", "Value"])
            for k, v in plain.items():
                writer.writerow([k, str(v)])

    return output.getvalue()


def _export_txt(data: Any, report_type: str) -> str:
    plain = _to_plain_dict(data)
    lines = []
    lines.append("=" * 70)
    lines.append(f" CRAPCLEANER EXPORT REPORT: {report_type.upper()}")
    lines.append("=" * 70)

    if isinstance(plain, dict):
        for key, value in plain.items():
            if isinstance(value, list):
                lines.append(f"\n[{key.upper()}] ({len(value)} items):")
                for item in value[:50]:
                    if isinstance(item, dict):
                        name = (
                            item.get("name")
                            or item.get("category_name")
                            or item.get("path")
                            or str(item)
                        )
                        sz = (
                            item.get("size") or item.get("total_size") or item.get("estimated_size")
                        )
                        sz_str = f" - {format_size(sz)}" if sz is not None else ""
                        lines.append(f"  • {name}{sz_str}")
                    else:
                        lines.append(f"  • {item}")
            else:
                lines.append(f"{key:<24}: {value}")
    elif isinstance(plain, list):
        for idx, item in enumerate(plain):
            lines.append(f"[{idx + 1}] {item}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines) + "\n"
