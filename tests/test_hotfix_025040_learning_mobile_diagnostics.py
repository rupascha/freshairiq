from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; COMP=ROOT/'custom_components'/'freshairiq'
def test_release_version_is_025040():
 assert json.loads((COMP/'manifest.json').read_text())['version']=='0.25.1.8'; assert 'VERSION = "0.25.1.8"' in (COMP/'const.py').read_text()
def test_time_evidence_migration_is_proof_only_and_one_time():
 t=(COMP/'storage.py').read_text(); assert 'time_evidence_migration_v025040' in t; assert 'session_days' in t and 'routine_source_buckets' in t and 'seasonal_source_profiles' in t
def test_coordinator_forwards_time_evidence_into_learning_snapshot():
 t=(COMP/'coordinator.py').read_text()
 for f in ('learning_observation_dates','routine_observation_dates','strategy_observation_dates','personal_context_observation_dates','seasonal_observation_days'): assert f'"{f}":' in t
 assert 'build_learning_components_status(\n            results,' in t
def test_partial_seasonality_is_visible_without_weakening_optimized_gate():
 t=(COMP/'learning_components.py').read_text(); assert 'seasonal_evidence_days' in t and 'seasonal_progress_percent' in t and '60 and near_start and near_end' in t and '365' in t and 'wird gelernt' in t
def test_forecast_accuracy_has_sample_depth_label():
 t=(COMP/'learning_components.py').read_text()
 for label in ('Erste Daten','Vorläufig','Lernphase','Zunehmend belastbar','Belastbarer'): assert label in t
def test_android_native_scroll_and_global_viewport_restore():
 t=(COMP/'frontend'/'freshairiq-card.js').read_text(); assert 'touch-action:pan-y pinch-zoom' in t and 'overflow-y:auto' in t; assert '_installAndroidTouchScroll' in t; assert '_captureOverlayViewport()' in t and '_restoreOverlayViewport()' in t and '_closeOverlayToCard()' in t
def test_feedback_has_privacy_minimised_client_context():
 card=(COMP/'frontend'/'freshairiq-card.js').read_text(); api=(COMP/'settings_api.py').read_text(); tel=(COMP/'telemetry.py').read_text(); assert 'client_context:this._fieldTestClientContext()' in card and 'payload.get("client_context")' in api; frag=tel[tel.index('safe_client = {}'):tel.index('headers = {',tel.index('safe_client = {}'))]; assert 'device_model' not in frag and 'platform_family' in frag and 'webview_engine_version' in frag
def test_transport_observability_fields_present():
 t=(COMP/'telemetry.py').read_text()
 for f in ('registered','initial_snapshot_received','daily_upload_received','last_successful_upload','next_scheduled_upload'): assert f'"{f}"' in t
def test_quality_and_start_measurement_are_explainable():
 d=(COMP/'diagnostics.py').read_text(); c=(COMP/'coordinator.py').read_text()
 for f in ('measurement_frame_reason','measurement_frame_max_age_s','measurement_frame_skew_s'): assert f in d
 for x in ('fresh','held_plausible','uncertain','start_measurement_in_session_gate_passed'): assert x in c
