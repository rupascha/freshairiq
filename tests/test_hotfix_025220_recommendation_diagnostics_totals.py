from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_explicit_recommendation_outcome_totals_are_transported():
    d=(ROOT/'custom_components/freshairiq/diagnostics.py').read_text()
    t=(ROOT/'custom_components/freshairiq/diagnostic_transport.py').read_text()
    for key in ('recommendation_followed','recommendation_missed','recommendation_pending'):
        assert f'"{key}"' in d
    for key in ('recommendation_followed_count','recommendation_missed_count','recommendation_pending_count'):
        assert key in d and key in t
