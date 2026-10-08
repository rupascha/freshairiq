from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_iq_dark_surface_text_and_footer_alignment_are_theme_independent():
 t=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
 assert '.iq-variant .brand,.iq-variant .details-btn,.iq-variant .decision-room-disclosure>summary,.iq-variant .decision-room-disclosure>summary span{color:#e9f1f5}' in t
 assert '.compact-actions{margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.055);justify-content:flex-start}' in t
 assert '<div class="card ${dashboardVariant === "iq" ? "iq-variant" : "classic-variant"}">' in t
