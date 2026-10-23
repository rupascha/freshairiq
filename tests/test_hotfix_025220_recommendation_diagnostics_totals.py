from pathlib import Path
from tests._source import module_source
ROOT=Path(__file__).parents[1]
def test_explicit_recommendation_outcome_totals_are_transported():
    d=module_source("diagnostics")
    t=module_source("diagnostic_transport")
    for key in ('recommendation_followed','recommendation_missed','recommendation_pending'):
        assert f'"{key}"' in d
    for key in ('recommendation_followed_count','recommendation_missed_count','recommendation_pending_count'):
        assert key in d and key in t
