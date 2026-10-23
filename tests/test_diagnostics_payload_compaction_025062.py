from pathlib import Path
from tests._source import module_source
ROOT=Path(__file__).resolve().parents[1]
SRC=module_source("diagnostics")
def test_event_payload_is_bounded():
    event=SRC[SRC.index("    def _build_record("):SRC.index("    def _build_trend_record(")]
    assert '"post_close_stabilization_history": _json_safe' not in event
    assert '"forecast_backtest": _json_safe' not in event
    assert '"diagnostic_history_summary"' in event
    assert '_latest_evidence(data.get("forecast_validation"))' in event
def test_learning_evidence_survives():
    event=SRC[SRC.index("    def _build_record("):SRC.index("    def _build_trend_record(")]
    assert '"learning_effectiveness"' in event
    assert '_compact_learning_components' in event
