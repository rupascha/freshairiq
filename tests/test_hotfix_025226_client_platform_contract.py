from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"custom_components"/"freshairiq"
def test_feedback_reuses_diagnostic_platform_detection():
 # Testvermerk 0.26.7.1 (U03): _sendFeedback moved unchanged into freshairiq-card-data.js
 js=(ROOT/"frontend"/"freshairiq-card.js").read_text()+(ROOT/"frontend"/"freshairiq-card-data.js").read_text()
 # 0.26.4.10: the unused _feedbackClientContext wrapper was removed; feedback sends
 # the shared diagnostic platform context directly.
 assert "client_context:this._fieldTestClientContext()" in js
 assert 'platform_family: android ?' not in js
 assert 'platformFamily = "Windows"' in js and 'platformFamily = "macOS"' in js and 'platformFamily = "Linux"' in js
