"""Cross-ventilation room pairs: one resolution for every reader (v0.26.6.1, issue #25).

The options "cross_ventilation_pairs" and "cross_zone_connections" are free text
("a+b, c+d"). Users write room names ("Schlafzimmer+Wohnzimmer") where only
internal room keys ("schlafzimmer+wohnzimmer") were understood, so the pairs were
silently ignored. A room is now found by its exact key first, then by its unique
name – case and umlauts as in the room-key convention (``_slug``: "Küche" ->
"kuche"). Only canonical keys are stored; what cannot be resolved is named.

Pure logic: no Home Assistant imports.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

PAIR_OPTIONS = ("cross_ventilation_pairs", "cross_zone_connections")
_SEPARATORS = re.compile(r"[,;\n]")
_FOLD = {0xE4: "a", 0xF6: "o", 0xFC: "u", 0xDF: "s"}   # the umlauts as in the room-key convention


def slug(name: Any) -> str:
    """The room-key convention of the config flow (``config_flow_fields._slug``)."""
    value = str(name or "").lower().strip().translate(_FOLD)
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def resolve_room(token: str, rooms: Iterable[dict[str, Any]]) -> tuple[str | None, str | None]:
    """(key, None) for a known room, else (None, "unknown" | "ambiguous")."""
    rooms = [r for r in rooms if isinstance(r, dict) and r.get("key")]
    keys = [str(r["key"]) for r in rooms]
    if token in keys:
        return token, None
    wanted = slug(token)
    by_name = sorted({str(r["key"]) for r in rooms if wanted and slug(r.get("name")) == wanted})
    if len(by_name) > 1:
        return None, "ambiguous"
    if by_name:
        return by_name[0], None
    by_key = [k for k in keys if wanted and k == wanted]
    return (by_key[0], None) if by_key else (None, "unknown")


def parse(raw: Any, rooms: Iterable[dict[str, Any]]) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
    """Resolved pairs (in the given order) and the problems: malformed, unknown, ambiguous, same, duplicate
    (texts for the user: ``config_flow_options_settings``)."""
    rooms = list(rooms)
    pairs: list[tuple[str, str]] = []
    problems: list[dict[str, str]] = []
    seen: set[frozenset[str]] = set()
    for item in _SEPARATORS.split(str(raw or "")):
        text = item.strip()
        if not text:
            continue
        parts = [p.strip() for p in text.split("+")]
        if len(parts) > 2 and all(parts):
            # 0.26.7.0 (support case): "Wohnzimmer+Flur+Schlafzimmer" is an air path, not a pair. It stays malformed
            # (never guessed into pairs), but the message names the two window rooms and the room in between.
            problems.append({"code": "malformed", "item": text, "chain": True, "ends": f"{parts[0]}+{parts[-1]}",
                             "middle": ", ".join(parts[1:-1])})
            continue
        if len(parts) != 2 or not all(parts):
            problems.append({"code": "malformed", "item": text})
            continue
        resolved = []
        for part in parts:
            key, error = resolve_room(part, rooms)
            if error:
                problems.append({"code": error, "item": text, "room": part})
            resolved.append(key)
        if None in resolved:
            continue
        a, b = resolved
        if a == b:
            problems.append({"code": "same", "item": text})
        elif frozenset((a, b)) in seen:
            problems.append({"code": "duplicate", "item": text})
        else:
            seen.add(frozenset((a, b)))
            pairs.append((a, b))
    return pairs, problems


TEXT = {
    "de": {"malformed": "„{item}“ ist kein Raumpaar (Form: Raum+Raum)",
           "chain": ("„{item}“ nennt mehr als zwei Räume. Querlüftung verbindet immer genau zwei Räume mit eigenem "
                     "Fenster – hier z. B. {ends}. Ein Raum dazwischen ohne eigenes Fenster ({middle}) wird unter "
                     "„Offene Verbindungen“ bzw. im Grundriss als Durchgang oder Innentür eingetragen"),
           "unknown": "„{room}“ in „{item}“ ist kein bekannter Raum",
           "ambiguous": "„{room}“ in „{item}“ passt auf mehrere Räume – bitte den Raumschlüssel verwenden",
           "same": "„{item}“ nennt zweimal denselben Raum",
           "duplicate": "„{item}“ ist doppelt angegeben"},
    "en": {"malformed": "\"{item}\" is not a room pair (form: room+room)",
           "chain": ("\"{item}\" names more than two rooms. Cross ventilation always links exactly two rooms with their "
                     "own windows – here e.g. {ends}. A room in between without a window of its own ({middle}) is entered "
                     "under \"Open connections\" or as a passage or inside door in the floor plan"),
           "unknown": "\"{room}\" in \"{item}\" is not a known room",
           "ambiguous": "\"{room}\" in \"{item}\" matches several rooms – please use the room key",
           "same": "\"{item}\" names the same room twice",
           "duplicate": "\"{item}\" is listed twice"},
}


def describe(problems: Iterable[dict[str, Any]], language: str) -> str:
    """What is wrong, in the user's language (options flow and repair notice use the same words)."""
    texts = TEXT["de" if str(language).lower().startswith("de") else "en"]
    return "; ".join(
        texts["chain" if p.get("chain") else p["code"]].format(
            item=p.get("item", ""), room=p.get("room", ""), ends=p.get("ends", ""), middle=p.get("middle", ""))
        for p in problems)


def unusable(options: dict[str, Any], rooms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stored entries the runtime cannot use (shown as a repair notice, never dropped silently)."""
    rooms = list(rooms)
    found: list[dict[str, Any]] = []
    for option in PAIR_OPTIONS:
        found.extend(p for p in parse(options.get(option), rooms)[1] if p["code"] != "duplicate")
    return found


def canonical(pairs: Iterable[tuple[str, str]]) -> str:
    """The stored form: keys only, "a+b,c+d"."""
    return ",".join(f"{a}+{b}" for a, b in pairs)


def migrate(options: dict[str, Any], rooms: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Stored pairs written with room names -> keys, once and idempotently.

    Pairs that resolve are stored as keys (already valid key pairs stay exactly as they are); what cannot be
    resolved stays in the text unchanged and is returned so the caller can log it once – never dropped silently.
    """
    rooms = list(rooms)
    updated = dict(options)
    unresolved: list[str] = []
    for option in PAIR_OPTIONS:
        raw = str(options.get(option) or "")
        if not raw.strip():
            continue
        pairs, problems = parse(raw, rooms)
        if not problems:
            text = canonical(pairs)
            if text != raw:
                updated[option] = text
            continue
        kept = [p["item"] for p in problems if p["code"] != "duplicate"]   # a repeated pair is the same pair
        unresolved.extend(f"{option}: {item}" for item in dict.fromkeys(kept))
        text = ",".join([canonical(pairs)] * bool(pairs) + list(dict.fromkeys(kept)))
        if text != raw:
            updated[option] = text
    return updated, unresolved


def key_pairs(raw: Any, rooms: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    """The resolved pairs of a stored option (runtime readers: recommendation, sessions, house)."""
    return parse(raw, rooms)[0]


def linked(raw: Any, rooms: Iterable[dict[str, Any]], a: str, b: str) -> bool:
    """True when the option links the two rooms (either order)."""
    return frozenset((a, b)) in {frozenset(p) for p in key_pairs(raw, rooms)}
