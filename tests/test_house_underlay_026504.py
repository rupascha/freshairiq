"""House map floor plan template (0.26.5.4): only real pictures, sane scale, calibration and separator lines."""
from __future__ import annotations

import base64

import pytest

from custom_components.freshairiq import house_layout as hl
from custom_components.freshairiq import house_underlay as hu

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 32).decode()
JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\0" * 32).decode()
WEBP = base64.b64encode(b"RIFF\x10\0\0\0WEBPVP8 " + b"\0" * 32).decode()


def _raw(**changes):
    raw = {"floor_id": "f_eg", "mime": "image/jpeg", "data": JPEG, "width": 800, "height": 600}
    raw.update(changes)
    return raw


@pytest.mark.parametrize(("mime", "data"), [("image/png", PNG), ("image/jpeg", JPEG), ("image/webp", WEBP)])
def test_real_pictures_are_accepted_with_defaults(mime, data) -> None:
    clean, code = hu.validate(_raw(mime=mime, data=data))
    assert code is None
    assert clean == {"floor_id": "f_eg", "mime": mime, "data": data, "width": 800, "height": 600, "scale_m_per_px": None,
                     "calibration": None, "walls": [], "close_px": 0, "opacity": 0.55}


def test_scale_calibration_walls_gap_and_opacity_are_kept_and_clamped() -> None:
    clean, code = hu.validate(_raw(scale_m_per_px=0.02, calibration={"a": [40, 580], "b": [760, 580], "meters": 14.4},
                                   walls=[[402, 140, 402.5, 175]], close_px=12, opacity=3, floor_id="x" * 200))
    assert code is None
    assert clean["scale_m_per_px"] == 0.02 and clean["calibration"] == {"a": [40.0, 580.0], "b": [760.0, 580.0], "meters": 14.4}
    assert clean["walls"] == [[402.0, 140.0, 402.5, 175.0]] and clean["close_px"] == 8 and clean["opacity"] == 1.0
    assert len(clean["floor_id"]) == 120
    low, _ = hu.validate(_raw(close_px=-3, opacity=0, walls="not a list"))
    assert low["close_px"] == 0 and low["opacity"] == 0.1 and low["walls"] == []


@pytest.mark.parametrize(("raw", "code"), [
    ("text", "E_UNDERLAY_SCHEMA"),
    (_raw(mime="application/pdf"), "E_UNDERLAY_TYPE"),
    (_raw(data=""), "E_UNDERLAY_TYPE"),
    (_raw(data=7), "E_UNDERLAY_TYPE"),
    (_raw(data="A" * (hu.MAX_DATA_CHARS + 4)), "E_UNDERLAY_TOO_LARGE"),
    (_raw(data="not base64!"), "E_UNDERLAY_DATA"),
    (_raw(mime="image/png", data=JPEG), "E_UNDERLAY_DATA"),                       # the stated type must match the bytes
    (_raw(mime="image/webp", data=base64.b64encode(b"RIFF\0\0\0\0AVI " + b"\0" * 8).decode()), "E_UNDERLAY_DATA"),
    (_raw(data=base64.b64encode(b"%PDF-1.7 " + b"\0" * 8).decode()), "E_UNDERLAY_DATA"),
    (_raw(width=None), "E_UNDERLAY_SIZE"),
    (_raw(height=8), "E_UNDERLAY_SIZE"),
    (_raw(width=hu.MAX_SIDE_PX + 1), "E_UNDERLAY_SIZE"),
    (_raw(width=True), "E_UNDERLAY_SIZE"),
    (_raw(height=float("nan")), "E_UNDERLAY_SIZE"),
    (_raw(scale_m_per_px=0), "E_UNDERLAY_SCALE"),
    (_raw(scale_m_per_px=1.5), "E_UNDERLAY_SCALE"),
    (_raw(calibration={"a": [0, 0], "b": [1, 0], "meters": 3}), "E_UNDERLAY_CALIBRATION"),
    (_raw(calibration={"a": [0, 0], "b": [100, 0], "meters": 0}), "E_UNDERLAY_CALIBRATION"),
    (_raw(calibration={"a": [0], "b": [100, 0], "meters": 3}), "E_UNDERLAY_CALIBRATION"),
    (_raw(calibration={"a": "x", "b": [100, 0], "meters": 3}), "E_UNDERLAY_CALIBRATION"),
    (_raw(calibration={"a": [0, "y"], "b": [100, 0], "meters": 3}), "E_UNDERLAY_CALIBRATION"),
    (_raw(walls=[[0, 0, 1]]), "E_UNDERLAY_WALLS"),
    (_raw(walls=[[0, 0, 1, "x"]]), "E_UNDERLAY_WALLS"),
    (_raw(walls=[[0, 0, 1, 1]] * (hu.MAX_WALLS + 1)), "E_UNDERLAY_WALLS"),
])
def test_anything_else_is_refused_with_a_reason(raw, code) -> None:
    assert hu.validate(raw) == (None, code)


def test_summary_tells_which_floors_have_a_template_without_the_picture() -> None:
    clean, _ = hu.validate(_raw(scale_m_per_px=0.02))
    assert hu.summary({"f_eg": clean, "f_og": {"width": 10, "height": 20}, "bad": "x"}) == {
        "f_eg": {"width": 800, "height": 600, "calibrated": True}, "f_og": {"width": 10, "height": 20, "calibrated": False}}


def test_traced_rooms_are_a_known_origin_of_the_layout() -> None:
    layout = hl.normalise({"schema_version": 1, "building": {}, "floors": [{"id": "f"}],
                           "rooms": [{"id": "r", "room_key": "a", "floor_id": "f", "polygon": [[0, 0], [4, 0], [4, 4], [0, 4]], "provenance": "traced"}]})
    assert layout["rooms"][0]["provenance"] == "traced"
