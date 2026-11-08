"""Branding regression (0.26.7.0): German and English artwork, language-neutral logo and preview, brand set, image links.

The only graphic with embedded text is the branding artwork. The English version
(``docs/freshairiq-branding-official-en.png``) must equal the German original pixel for pixel outside the two
text bands (tagline, four labels) – same design, only the language differs. The logo card and the social
preview are cut from the artwork without any text band, so they are language-neutral. The PNGs are decoded with
the standard library only (CI installs no imaging package).
"""
from __future__ import annotations

import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_install_zip as biz  # noqa: E402

DOCS = ROOT / "docs"
BRAND = ROOT / "custom_components/freshairiq/brand"
DE_ART, EN_ART = DOCS / "freshairiq-branding-official.png", DOCS / "freshairiq-branding-official-en.png"
TEXT_BANDS = ((938, 997), (1097, 1155))      # tagline and label rows of the artwork (inclusive)


def _png(path: Path) -> tuple[int, int, int, list[bytes]]:
    """(width, height, bytes per pixel, rows) of an 8-bit, non-interlaced RGB/RGBA PNG."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    pos, idat, head = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    width, height, depth, colour, _, _, interlace = head
    assert depth == 8 and colour in (2, 6) and interlace == 0, (path, head)
    bpp = 3 if colour == 2 else 4
    raw, stride, rows, prev = zlib.decompress(idat), width * bpp, [], bytearray(width * bpp)
    for y in range(height):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows


def _size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def _in_band(y: int) -> bool:
    return any(lo <= y <= hi for lo, hi in TEXT_BANDS)


def test_english_artwork_is_the_german_design_with_only_the_text_bands_replaced():
    w_de, h_de, _, de = _png(DE_ART)
    w_en, h_en, _, en = _png(EN_ART)
    assert (w_de, h_de) == (w_en, h_en) == (1254, 1254)
    outside = [y for y in range(h_de) if not _in_band(y) and de[y] != en[y]]
    assert outside == []                                                     # brand mark, symbols, layout untouched
    assert all(de[y] != en[y] for lo, hi in TEXT_BANDS for y in (lo + 15, hi - 15))   # the text really is replaced


def test_logo_card_and_social_preview_are_language_neutral():
    _, h_de, _, de = _png(DE_ART)
    w, h, _, logo = _png(DOCS / "freshairiq-logo.png")
    assert (w, h) == (1254, 1020)
    assert logo[:916] == de[:916]                                            # everything above the tagline band
    assert logo[-80:] == de[-80:] and h_de - 80 > TEXT_BANDS[-1][1]          # bottom edge below the label band
    assert _size(DOCS / "freshairiq-social-preview.png") == (1280, 640)      # GitHub's recommended size


def test_brand_set_is_complete_for_light_and_dark_and_ships_in_the_install_zip(tmp_path):
    for name in ("icon", "logo"):
        for prefix in ("", "dark_"):
            assert _size(BRAND / f"{prefix}{name}.png") == (256, 256)
            assert _size(BRAND / f"{prefix}{name}@2x.png") == (512, 512)
    archive = tmp_path / "freshairiq.zip"
    biz.build(ROOT, archive)
    import zipfile
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert len(names) == len(set(names))                                     # no duplicate assets
    assert {f"brand/{p}{n}{s}.png" for p in ("", "dark_") for n in ("icon", "logo") for s in ("", "@2x")} <= set(names)
    assert not any(n.startswith("docs/") or n.endswith("-social-preview.png") for n in names)   # docs art is not installed


IMG = re.compile(r'(?:src="|\]\()([^")\s]+\.(?:png|jpe?g|svg|gif))')
RAW = "https://raw.githubusercontent.com/rupascha/freshairiq/main/"


def _images(readme: str) -> list[str]:
    return IMG.findall((ROOT / readme).read_text(encoding="utf-8"))


def test_readmes_use_the_artwork_of_their_language_and_every_image_exists():
    assert (ROOT / "README.md").read_text(encoding="utf-8") == (ROOT / "README_EN.md").read_text(encoding="utf-8")
    for readme, own, other in (("README_EN.md", "freshairiq-branding-official-en.png", "freshairiq-branding-official.png"),
                               ("README_DE.md", "freshairiq-branding-official.png", "freshairiq-branding-official-en.png")):
        images = _images(readme)
        assert any(i.endswith("/" + own) for i in images) and not any(i.endswith("/" + other) for i in images), readme
        for image in images:
            if image.startswith("http") and not image.startswith(RAW):
                continue                                                     # external badges
            local = ROOT / (image[len(RAW):] if image.startswith(RAW) else image)
            assert local.is_file(), (readme, image)
    de_text = (ROOT / "README_DE.md").read_text(encoding="utf-8")
    assert "Sprache / Language" in de_text and "Language / Sprache" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_branding_guide_names_both_languages_and_the_neutral_assets():
    text = (ROOT / "BRANDING.md").read_text(encoding="utf-8")
    for asset in ("freshairiq-branding-official.png", "freshairiq-branding-official-en.png", "freshairiq-logo.png",
                  "freshairiq-social-preview.png", "custom_components/freshairiq/brand/"):
        assert asset in text, asset
    assert json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))["name"] == "FreshAirIQ"
