from pathlib import Path

CARD = Path("custom_components/freshairiq/frontend/freshairiq-card.js")


def test_freshy_hero_has_no_visible_tile_or_hard_clip():
    text = CARD.read_text(encoding="utf-8")
    marker = "/* v0.25.1.19: Freshy seamless-hero hotfix."
    assert marker in text
    css = text.split(marker, 1)[1]
    assert ".ai-mascot-wrap{" in css
    assert "overflow:visible" in css
    assert "contain:none" in css
    assert "background:none" in css
    assert ".ai-mascot-wrap::before{content:none!important}" in css


def test_airflow_fades_instead_of_being_hard_clipped():
    text = CARD.read_text(encoding="utf-8")
    css = text.split("/* v0.25.1.19: Freshy seamless-hero hotfix.", 1)[1]
    assert "mask-image:linear-gradient(90deg,transparent" in css
    assert ".ai-copy{position:relative;z-index:4}" in css
