"""Output-language layer for backend-generated texts (0.26.4.5).

FreshAirIQ computes every recommendation, reason and notification in German. The
decision logic must stay untouched, so English is produced at the output boundary:
after a coordinator cycle the published payload is translated, and push
notifications are translated right before they are sent.

Home Assistant itself falls back to English for every language it has no
translation for, so FreshAirIQ does the same: German stays German, every other
language gets English.

Translation is table driven (``text_en``): exact sentences first, then templates
whose interpolated values are translated recursively (unless they are protected
user data such as room names), then a split into sentences / `` · `` segments.
Anything that cannot be translated is returned unchanged – never half-replaced.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .text_en import EXACT, TEMPLATES

# User data and machine values: never translated, even if they look German.
_SKIP_KEYS = frozenset({
    "name", "names", "room_name", "room_names", "key", "room_key", "room_keys",
    "floor", "entity_id", "entity_ids", "id", "unique_id", "entry_id", "unit",
    "icon", "kind", "status", "state", "event", "source", "mode", "version",
    "addressed_name", "resident_names", "adult_resident_names", "child_resident_names",
})
# Some machine keys hold display text in a few nested objects.
_TEXT_STATUS_PARENTS = frozenset({"components"})

_GERMAN_WORDS = re.compile(
    r"(?<![\w])(und|oder|nicht|ist|sind|wird|werden|der|die|das|den|dem|des|mit|für|bei|"
    r"noch|kein|keine|keinen|zu|im|ein|eine|einen|auf|aus|von|vor|nach|seit|über|etwa|"
    r"aktuell|jetzt|lüften|schließen|wurde|kann|bleibt)(?![\w])",
    re.IGNORECASE,
)
_HAS_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{3}")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")
_SEGMENT_SEPARATORS = (" · ", "; ", " – ")
_MAX_DEPTH = 4
_CACHE_LIMIT = 8192


_GERMAN_SHAPES = re.compile(
    r"\b\w*[äöüßÄÖÜ]\w*|\b\w{4,}(?:ung|ungen|keit|heit|lich|isch)\b|\b(?:voraussichtlich|etwa|ca\.|Uhr|Tage|Minuten|Fenster|Raum)\b"
)


def _german_score(text: str, protected: Iterable[str] = ()) -> int:
    for name in protected:
        if name and name in text:
            text = text.replace(name, " ")
    return len(_GERMAN_WORDS.findall(text)) + len(_GERMAN_SHAPES.findall(text))


def is_german(language: Any) -> bool:
    """Home Assistant language codes such as ``de``, ``de-CH`` -> German."""
    return str(language or "de").strip().lower().startswith("de")


_EDGE = " ·;"


def _template_variants(literals: tuple[str, ...], en: str) -> list[tuple[tuple[str, ...], str]]:
    """Fragments such as `` · noch ca. {0} min`` also occur as a stand-alone segment."""
    variants = [(literals, en)]
    if len(literals) > 1 and (literals[0] != literals[0].lstrip() or literals[-1] != literals[-1].rstrip()):
        # Sentences that are concatenated with spaces arrive here already stripped.
        variants.append(((literals[0].lstrip(), *literals[1:-1], literals[-1].rstrip()), en.strip()))
    head, tail = literals[0], literals[-1]
    if len(literals) == 1 or not head.strip(_EDGE) or (len(literals) > 1 and not tail.strip(_EDGE) and tail.strip()):
        return variants
    trimmed = (head.lstrip(_EDGE), *literals[1:-1], tail.rstrip(_EDGE))
    if trimmed != literals:
        variants.append((trimmed, en.strip(_EDGE)))
    return variants


def _compile() -> tuple[dict[str, str], list[tuple[re.Pattern[str], str, int]], list[tuple[re.Pattern[str], str, int]]]:
    lower: dict[str, str] = {}
    # Normal sentence case wins over ALL-CAPS labels with the same words.
    for de, en in sorted(EXACT.items(), key=lambda item: item[0].isupper()):
        lower.setdefault(de.lower(), en)
        lower.setdefault(de.strip(_EDGE).lower(), en.strip(_EDGE))
    compiled: list[tuple[re.Pattern[str], str, int]] = []
    embedded: list[tuple[re.Pattern[str], str, int]] = []
    for literals_raw, en_raw in TEMPLATES:
        for literals, en in _template_variants(literals_raw, en_raw):
            weight = sum(len(part.strip()) for part in literals)
            pattern = "(.+?)".join(re.escape(part) for part in literals)
            compiled.append((re.compile(f"^{pattern}$", re.DOTALL), en, weight))
            if weight >= 18 and literals[0].strip():
                inner = r"([^·;]+?)".join(re.escape(part) for part in literals)
                if literals[-1].strip():
                    embedded.append((re.compile(inner), en, weight))
    # Long, complete German sentences can be replaced wherever they occur.
    for de, en in EXACT.items():
        key = de.strip()
        if len(key) >= 25:
            embedded.append((re.compile(re.escape(key)), en.strip(), len(key)))
    # Most specific (longest literal text) first.
    compiled.sort(key=lambda item: -item[2])
    embedded.sort(key=lambda item: -item[2])
    return lower, compiled, embedded


_LOWER_EXACT, _COMPILED, _EMBEDDED = _compile()


class Translator:
    """German -> English translator with protected user data and a bounded cache."""

    def __init__(self, protected: Iterable[str] = ()) -> None:
        self._protected = {str(p).strip() for p in protected if str(p or "").strip()}
        self._cache: dict[str, str] = {}

    def _is_protected(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped or stripped in self._protected:
            return True
        parts = [p.strip() for p in re.split(r"\s*(?:\+|,|/)\s*", stripped) if p.strip()]
        return bool(parts) and all(p in self._protected for p in parts)

    def _value(self, text: str, depth: int) -> str | None:
        """Translate an interpolated value; None if it is untranslatable German."""
        if self._is_protected(text) or not _HAS_WORD.search(text):
            return text
        translated = self._translate(text, depth + 1)
        if _german_score(translated, self._protected):
            return None
        return translated

    def _exact(self, text: str) -> str | None:
        if text in EXACT:
            return EXACT[text]
        found = _LOWER_EXACT.get(text.lower())
        if found is None:
            if text.endswith(".") and not text.endswith("..") and text[:-1] in EXACT:
                return EXACT[text[:-1]].rstrip(".") + "."
            return None
        if text.isupper():
            return found.upper()
        if text[:1].islower():
            return found[:1].lower() + found[1:]
        return found[:1].upper() + found[1:]

    def _template(self, text: str, depth: int) -> str | None:
        for pattern, en, _weight in _COMPILED:
            match = pattern.match(text)
            if match is None:
                continue
            values: list[str] = []
            for group in match.groups():
                value = self._value(group, depth)
                if value is None:
                    break
                values.append(value)
            else:
                return en.format(*values)
        return None

    def _split(self, text: str, depth: int) -> str | None:
        for splitter in (_SENTENCE_SPLIT, *_SEGMENT_SEPARATORS):
            if isinstance(splitter, str):
                if splitter not in text:
                    continue
                pieces, joiner = text.split(splitter), splitter
            else:
                pieces = splitter.split(text)
                if len(pieces) < 2:
                    continue
                joiner = " "
            translated = [self._translate(piece, depth + 1) for piece in pieces]
            if translated != pieces:
                return joiner.join(translated)
        return None

    def _embedded(self, text: str, depth: int) -> str | None:
        """Replace known sentences/templates that were glued into a longer text."""
        result = text
        for pattern, en, _weight in _EMBEDDED:
            if pattern.groups == 0:
                result = pattern.sub(lambda _m, en=en: en, result)
                continue

            def _replace(match: re.Match[str], en: str = en) -> str:
                values = [self._value(group, depth) for group in match.groups()]
                if any(value is None for value in values):
                    return match.group(0)
                return en.format(*values)

            result = pattern.sub(_replace, result)
        return result if result != text else None

    def _translate(self, text: str, depth: int) -> str:
        if depth > _MAX_DEPTH or not text or not _HAS_WORD.search(text):
            return text
        exact = self._exact(text)
        if exact is not None:
            return exact
        stripped = text.strip()
        if stripped != text:
            inner = self._translate(stripped, depth)
            if inner != stripped:
                start = text.index(stripped[0])
                return text[:start] + inner + text[start + len(stripped):]
            return text
        best = text
        best_score = _german_score(text, self._protected)
        for candidate in (self._template, self._split, self._embedded):
            result = candidate(text, depth)
            if result is None or result == text:
                continue
            score = _german_score(result, self._protected)
            if score == 0:
                return result
            if score < best_score:
                best, best_score = result, score
        return best

    def text(self, text: str) -> str:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        result = self._translate(text, 0)
        if len(self._cache) >= _CACHE_LIMIT:
            self._cache.clear()
        self._cache[text] = result
        return result

    def payload(self, value: Any, key: str | None = None, parent: str | None = None) -> Any:
        """Return a translated copy of a coordinator payload; inputs are not mutated."""
        if isinstance(value, Mapping):
            return {k: self._payload_item(k, v, key) for k, v in value.items()}
        if isinstance(value, list):
            return [self.payload(item, key, parent) for item in value]
        if isinstance(value, tuple):
            return tuple(self.payload(item, key, parent) for item in value)
        if isinstance(value, str):
            return self.text(value)
        return value

    def _payload_item(self, key: Any, value: Any, parent: str | None) -> Any:
        name = str(key)
        if name in _SKIP_KEYS and not (name == "status" and parent in _TEXT_STATUS_PARENTS):
            return value
        return self.payload(value, name, parent)


def protected_names(entry_data: Mapping[str, Any] | None, options: Mapping[str, Any] | None = None) -> set[str]:
    """Room, floor and resident names entered by the user."""
    names: set[str] = set()
    data = entry_data if isinstance(entry_data, Mapping) else {}
    for room in data.get("rooms", []) or []:
        if isinstance(room, Mapping):
            for field in ("name", "key", "floor"):
                if room.get(field):
                    names.add(str(room[field]))
    for level in data.get("levels", []) or []:
        names.add(str(level))
    opts = options if isinstance(options, Mapping) else {}
    for field in ("adult_resident_names", "child_resident_names"):
        raw = opts.get(field)
        items = raw if isinstance(raw, list) else str(raw or "").replace(";", ",").replace("\n", ",").split(",")
        names.update(str(item).strip() for item in items if str(item).strip())
    # Legacy floor codes are displayed as translated labels, so do not protect them.
    return {n for n in names if n and n not in {"ground_floor", "upper_floor", "basement", "attic", "other", "Unzugeordnet"}}


def to_english(text: str, protected: Iterable[str] = ()) -> str:
    """Translate one German text (convenience wrapper for notifications/APIs)."""
    return Translator(protected).text(text)
