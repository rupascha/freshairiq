from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RAW_PREFIX = "https://raw.githubusercontent.com/rupascha/freshairiq/main/"

def test_readme_images_use_hacs_safe_absolute_urls_and_exist():
    text = README.read_text(encoding="utf-8")
    sources = re.findall(r'<img[^>]+src="([^"]+)"', text)
    assert sources, "README must contain image references"
    for src in sources:
        assert src.startswith(RAW_PREFIX), f"README image is not HACS-safe: {src}"
        rel = src.removeprefix(RAW_PREFIX)
        assert (ROOT / rel).is_file(), f"README image target missing: {rel}"

def test_public_beta_screenshot_gallery_is_complete():
    shots = sorted((ROOT / "docs" / "screenshots").glob("*.jpeg"))
    assert len(shots) == 8
    text = README.read_text(encoding="utf-8")
    for shot in shots:
        assert RAW_PREFIX + shot.relative_to(ROOT).as_posix() in text
