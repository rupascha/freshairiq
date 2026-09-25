from pathlib import Path

from custom_components.freshairiq.forecast import horizon_forecast

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")


def test_details_dialog_owns_scrolling_and_backdrop_cannot_scroll_behind_header():
    assert '.modal{position:fixed' in JS
    assert 'display:flex;align-items:flex-start;justify-content:center' in JS
    assert 'overflow:hidden;touch-action:pan-y' in JS
    assert '.dialog{width:calc(100vw - 28px)' in JS
    assert 'display:flex;flex-direction:column;overflow:hidden' in JS
    assert '.dialog-head{' in JS and 'position:relative;flex:0 0 auto' in JS
    assert '.dialog-scroll{min-height:0;height:0;flex:1 1 auto;overflow-y:scroll' in JS
    assert 'const oldDialog = this.shadowRoot.querySelector(".dialog-scroll")' in JS
    assert 'const newDialog = this.shadowRoot.querySelector(".dialog-scroll")' in JS
    assert '.dialog-scroll,.dialog-scroll *{touch-action:pan-y}' in JS


def test_forecast_keeps_decision_target_cap_but_exposes_horizon_dependent_physical_effect():
    common = dict(
        current_ah=12.0, source_ah=6.0, current_temp_c=21.0, source_temp_c=10.0,
        volume_m3=100.0, rate_per_min=0.05, airflow_bonus=1.0,
        target_ah=11.0, cap_positive_to_target=True,
    )
    f15 = horizon_forecast(horizon_min=15, **common)
    f60 = horizon_forecast(horizon_min=60, **common)
    assert f15["moisture_effect_ml"] == f60["moisture_effect_ml"] == 100
    assert f60["uncapped_physical_moisture_effect_ml"] > f15["uncapped_physical_moisture_effect_ml"]
    assert f15["target_limited"] and f60["target_limited"]


def test_uncapped_forecast_transport_reaches_dashboard_without_changing_decision_value():
    assert 'forecast_uncapped_moisture_effect_ml' in COORD
    assert 'forecast_target_limited' in COORD
    assert '"forecast_uncapped_moisture_effect_ml"' in SENSOR
    assert '"forecast_target_limited"' in SENSOR
    assert 'forecastUncappedEffect' in JS
    assert 'const forecastDisplayEffect = forecastEffect' in JS
    assert 'forecastLiveAdapted' in JS
    assert 'Live-Messverlauf berücksichtigt' in JS
    assert 'am Feuchteziel begrenzt' in JS


def test_frontend_hot_path_avoids_object_spread_and_dom_collection_iteration_for_older_webviews():
    # Object spread is a parse-time failure on older embedded WebViews. The card
    # keeps array spread where harmless, but no executable object-spread remains.
    assert '{ ...' not in JS
    patch = JS[JS.index('_patchLiveNode(current, fresh) {'):JS.index('_refreshOpenViewsLive() {')]
    assert 'Array.prototype.slice.call(current.attributes || [])' in patch
    assert 'Array.prototype.slice.call(current.childNodes || [])' in patch
    assert 'instanceof HTMLInputElement' not in patch
    assert 'Node.TEXT_NODE' not in patch
