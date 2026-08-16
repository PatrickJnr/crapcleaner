"""Unit tests for the report exporter utility."""

import json

from crapcleaner.reports import export_report


def test_export_report_json():
    data = {"category_id": "test", "total_size": 1024, "files": 5}
    out = export_report(data, report_type="scan", export_format="json")
    parsed = json.loads(out)
    assert parsed["category_id"] == "test"
    assert parsed["total_size"] == 1024


def test_export_report_csv():
    data = {
        "categories": [
            {
                "category_id": "temp",
                "name": "Temp Files",
                "group": "Windows",
                "safety_level": "SAFE",
                "size": 2048,
                "item_count": 10,
                "errors": [],
            }
        ]
    }
    out = export_report(data, report_type="scan", export_format="csv")
    assert "Category ID" in out
    assert "Temp Files" in out
    assert "2048" in out


def test_export_report_txt():
    data = {"system_status": "Healthy", "reclaimable_bytes": 1048576}
    out = export_report(data, report_type="scan", export_format="txt")
    assert "CRAPCLEANER EXPORT REPORT" in out
    assert "system_status" in out


def test_export_report_file_writing(tmp_path):
    out_file = tmp_path / "report.json"
    data = {"status": "ok"}
    export_report(data, report_type="scan", export_format="json", output_path=str(out_file))
    assert out_file.is_file()
    assert "ok" in out_file.read_text()
