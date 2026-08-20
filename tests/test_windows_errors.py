"""Tests for Windows error translation and explanation utilities."""

from crapcleaner.utils.windows_errors import (
    explain_windows_error,
    extract_error_code,
)


def test_extract_error_code():
    assert extract_error_code("Exception from HRESULT: 0x80244011") == "0x80244011"
    assert extract_error_code("Error 0x80070422 in wuauserv") == "0x80070422"
    assert extract_error_code("0x8024002e") == "0x8024002e"
    assert extract_error_code("No hex code here") is None
    assert extract_error_code("") is None


def test_explain_hresult_0x80244011():
    raw = "Exception from HRESULT: 0x80244011"
    explained = explain_windows_error(raw)
    assert "0x80244011" in explained
    assert "Update Server Connection Failure" in explained
    assert "SOAP" in explained
    assert "internet connection" in explained.lower() or "proxy" in explained.lower()


def test_explain_hresult_0x8024002e_policy():
    raw = "Exception from HRESULT: 0x8024002E"
    explained = explain_windows_error(raw)
    assert "Policy" in explained
    assert "0x8024002E" in explained


def test_explain_hresult_0x80070422_service_disabled():
    raw = "Exception from HRESULT: 0x80070422"
    explained = explain_windows_error(raw)
    assert "Disabled" in explained or "service" in explained.lower()


def test_explain_hresult_access_denied_0x80070005():
    raw = "Exception from HRESULT: 0x80070005"
    explained = explain_windows_error(raw)
    assert "Access Denied" in explained
    assert "Administrator" in explained


def test_explain_heuristic_categories_for_unlisted_codes():
    exp_server = explain_windows_error("0x80244999")
    assert "Update Server Error" in exp_server

    exp_ds = explain_windows_error("0x80248999")
    assert "Datastore Error" in exp_ds

    exp_net = explain_windows_error("0x80072999")
    assert "Network" in exp_net or "Timeout" in exp_net


def test_explain_text_phrases():
    assert "Access Denied" in explain_windows_error("Access is denied.")
    assert "Service Stopped" in explain_windows_error("wuauserv is not running.")
    assert "Connection Timeout" in explain_windows_error("Connection timed out waiting for server.")


def test_explain_empty_and_passthrough():
    assert explain_windows_error("") == ""
    assert explain_windows_error(None) == ""
    assert explain_windows_error("Some random benign message") == "Some random benign message"
