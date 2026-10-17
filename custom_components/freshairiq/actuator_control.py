"""Optional automatic control of covers and exhaust fans (0.26.5.1).

FreshAirIQ only switches devices when the user enabled it in the room setup:

* per opening: "open the cover when the window/door opens" – the cover goes
  fully up when the opening is opened and returns to its previous position
  when it is closed again (unless someone moved it in between);
* per room: "close the covers against the sun" – the covers of the sun
  protection plan (summer cooling) are closed and opened again once the sun
  has left their window;
* per room: exhaust fan "after a moisture source" or "following the
  recommendation", with follow-up time and maximum runtime.

A cover of a passage door ("Durchgang") never closes while that door's contact
is not closed; in a room where FreshAirIQ controls covers, a close started by
anyone is stopped and the cover is opened again (lock-out protection).

Pure logic: no Home Assistant imports. Every decision only reads the given
state and the small memory dict that the adapter persists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

FAN_CONTROL_OFF = "off"
FAN_CONTROL_MOISTURE_SOURCE = "moisture_source"
FAN_CONTROL_RECOMMENDATION = "recommendation"
FAN_CONTROL_MODES = [FAN_CONTROL_OFF, FAN_CONTROL_MOISTURE_SOURCE, FAN_CONTROL_RECOMMENDATION]
FAN_RECOMMENDATION_ON = {"ventilate", "continue_ventilating"}
DEFAULT_FAN_FOLLOW_UP_MIN = 10
DEFAULT_FAN_MAX_RUNTIME_MIN = 60

COVER_OPEN = "open"
COVER_CLOSE = "close"
COVER_STOP = "stop"
COVER_POSITION = "position"


@dataclass(frozen=True, slots=True)
class CoverView:
    """What Home Assistant currently reports for one cover."""

    state: str
    position: int | None = None
    supports_position: bool = False
    zero_means_open: bool = False

    @property
    def available(self) -> bool:
        return self.state in {"open", "closed", "opening", "closing"}

    @property
    def open_position(self) -> int:
        return 0 if self.zero_means_open else 100

    @property
    def closed_position(self) -> int:
        return 100 if self.zero_means_open else 0

    @property
    def fully_open(self) -> bool:
        if self.position is not None:
            return self.position == self.open_position
        return self.state == "open"

    @property
    def closed(self) -> bool:
        if self.position is not None:
            return self.position == self.closed_position
        return self.state == "closed"


@dataclass(slots=True)
class CoverSetup:
    """Configured relations of one cover inside a room."""

    contacts: list[str] = field(default_factory=list)
    follow_contacts: list[str] = field(default_factory=list)
    passage_contacts: list[str] = field(default_factory=list)


def contact_is_open(mode: str) -> bool:
    return mode in {"open", "tilted"}


def _not_closed(mode: Any) -> bool:
    return str(mode) != "closed"


def cover_setups(room: dict[str, Any]) -> dict[str, CoverSetup]:
    """Covers of a room with their contacts, follow and passage flags."""
    mapping = room.get("contact_covers") if isinstance(room.get("contact_covers"), dict) else {}
    follow = room.get("contact_cover_follow") if isinstance(room.get("contact_cover_follow"), dict) else {}
    passage = room.get("contact_passage_doors") if isinstance(room.get("contact_passage_doors"), dict) else {}
    setups: dict[str, CoverSetup] = {}
    for contact, raw in mapping.items():
        covers = [raw] if isinstance(raw, str) else list(raw or [])
        for cover in covers:
            if not str(cover).startswith("cover."):
                continue
            setup = setups.setdefault(str(cover), CoverSetup())
            setup.contacts.append(str(contact))
            if follow.get(contact):
                setup.follow_contacts.append(str(contact))
            if passage.get(contact):
                setup.passage_contacts.append(str(contact))
    return setups


def room_controls_covers(room: dict[str, Any]) -> bool:
    """True when FreshAirIQ may move any cover of the room."""
    follow = room.get("contact_cover_follow") if isinstance(room.get("contact_cover_follow"), dict) else {}
    return bool(room.get("auto_sun_protection")) or any(bool(v) for v in follow.values())


def decide_cover(
    *,
    view: CoverView,
    setup: CoverSetup,
    contact_modes: dict[str, str],
    sun_auto: bool,
    sun_wants_close: bool,
    mem: dict[str, Any],
) -> list[tuple[str, int | None]]:
    """Commands for one cover; ``mem`` is updated in place."""
    if not view.available:
        return []
    # an unknown passage contact counts as open: never risk a lock-out
    passage_open = any(_not_closed(contact_modes.get(c)) for c in setup.passage_contacts)
    follow_open = any(contact_is_open(str(contact_modes.get(c))) for c in setup.follow_contacts)
    follow_known = all(str(contact_modes.get(c)) in {"open", "tilted", "closed"} for c in setup.follow_contacts)
    # only called for rooms that let FreshAirIQ control covers
    if passage_open and view.state == "closing":
        return [(COVER_STOP, None), (COVER_OPEN, None)]

    if follow_open:
        if not mem.get("follow_active"):
            mem["follow_active"] = True
            mem["restore_position"] = view.position
            mem["restore_closed"] = view.closed
            if not view.fully_open and view.state != "opening":
                return [(COVER_OPEN, None)]
        return []

    if mem.get("follow_active"):
        if not follow_known or passage_open:
            return []
        mem["follow_active"] = False
        position = mem.pop("restore_position", None)
        was_closed = bool(mem.pop("restore_closed", False))
        if not (view.fully_open or view.state == "opening"):
            # moved by someone while the window was open: keep it as it is
            mem["sun_state"] = "foreign" if sun_auto and sun_wants_close else None
            return []
        if sun_auto and sun_wants_close:
            mem["sun_state"] = "ours"
            return [(COVER_CLOSE, None)]
        if position is not None and position != view.open_position:
            if view.supports_position:
                return [(COVER_POSITION, int(position))]
            return [(COVER_CLOSE, None)] if position == view.closed_position else []
        return [(COVER_CLOSE, None)] if was_closed else []

    if not sun_auto:
        mem.pop("sun_state", None)
        return []
    if sun_wants_close:
        if mem.get("sun_state") is None and not passage_open:
            if view.closed or view.state == "closing":
                mem["sun_state"] = "foreign"
                return []
            mem["sun_state"] = "ours"
            return [(COVER_CLOSE, None)]
        return []
    state = mem.pop("sun_state", None)
    if state == "ours" and view.closed:
        return [(COVER_OPEN, None)]
    return []


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def fan_demand(mode: str, *, source_active: bool, recommendation: str, window_open: bool) -> bool:
    if mode == FAN_CONTROL_MOISTURE_SOURCE:
        return source_active
    if mode == FAN_CONTROL_RECOMMENDATION:
        return recommendation in FAN_RECOMMENDATION_ON and not window_open
    return False


def decide_fan(
    *,
    mode: str,
    fan_on: bool | None,
    demand: bool,
    now: datetime,
    follow_up_min: float,
    max_runtime_min: float,
    mem: dict[str, Any],
) -> str | None:
    """"on", "off" or None for the exhaust fan(s) of one room; ``mem`` is updated.

    FreshAirIQ only switches off what it switched on itself. If someone turns
    such a fan off, it is not switched on again until the demand has ended.
    """
    if fan_on is None:
        return None
    if not demand:
        mem["blocked"] = False
    if mem.get("owned") and not fan_on:
        mem["owned"] = False
        mem["blocked"] = demand
        return None
    if demand:
        mem["last_demand"] = now.isoformat()
    if mem.get("owned"):
        since = _parse(mem.get("since")) or now
        if mode == FAN_CONTROL_OFF:
            mem["owned"] = False
            return "off"
        if now - since >= timedelta(minutes=max_runtime_min):
            mem["owned"] = False
            mem["blocked"] = demand
            return "off"
        if not demand:
            last = _parse(mem.get("last_demand")) or since
            follow_up = follow_up_min if mode == FAN_CONTROL_MOISTURE_SOURCE else 0.0
            if now - last >= timedelta(minutes=follow_up):
                mem["owned"] = False
                return "off"
        return None
    if demand and not mem.get("blocked") and not fan_on:
        mem["owned"] = True
        mem["since"] = now.isoformat()
        return "on"
    return None
