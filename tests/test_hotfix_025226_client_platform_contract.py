from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"custom_components"/"freshairiq"
def test_feedback_reuses_diagnostic_platform_detection():
 js=(ROOT/"frontend"/"freshairiq-card.js").read_text()
 frag=js[js.index("_feedbackClientContext()"):js.index("_ensureStaticStyle()") ]
 assert "this._fieldTestClientContext()" in frag
 assert 'platform_family: android ?' not in frag
 assert 'platformFamily = "Windows"' in js and 'platformFamily = "macOS"' in js and 'platformFamily = "Linux"' in js
