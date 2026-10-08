from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_feedback_error_is_structured_and_reported():
    api=(ROOT/"custom_components/freshairiq/feedback_api.py").read_text(); card=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(); telemetry=(ROOT/"custom_components/freshairiq/telemetry.py").read_text()
    assert "FAIQ-HUB-FEEDBACK-001" in api
    assert "async_report_client_error" in api and "/v1/client-errors" in telemetry
    assert "client_error_queue" in telemetry and "[-50:]" in telemetry
    assert "_formatApiError" in card and "[object Object]" in card
