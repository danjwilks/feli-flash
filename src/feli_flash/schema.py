"""Schema definitions, loading, and validation for Evidence-Based Anki decks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

CardType = Literal["qa", "cloze"]
CLOZE_PATTERN = re.compile(r"\{\{c(\d+)::(.+?)\}\}", re.DOTALL)


class SpecValidationError(ValueError):
    """Raised when a deck specification YAML/JSON fails validation."""


@dataclass
class CardSpec:
    """Normalized specification for a single Evidence-Based Anki note."""

    card_type: CardType = "qa"
    id: str | None = None
    context: str = ""
    front: str = ""
    back: str = ""
    text: str = ""
    why_extra: str = ""
    visual: str | None = None
    source_date: str = ""
    add_reverse: bool = False
    tags: list[str] = field(default_factory=list)
    subdeck: str | None = None


@dataclass
class DeckSpec:
    """Top-level specification for a flat, richly-tagged Anki deck package."""

    name: str
    description: str = ""
    default_tags: list[str] = field(default_factory=list)
    css: str = ""
    cards: list[CardSpec] = field(default_factory=list)
    base_dir: Path = field(default_factory=Path.cwd)


def _normalize_tags(raw: Any, context: str) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [t for t in raw.split() if t]
    if not isinstance(raw, list):
        raise SpecValidationError(f"{context}: tags must be a list of strings or a space-separated string")
    normalized: list[str] = []
    for item in raw:
        tag = str(item).strip().replace(" ", "_")
        if tag and tag not in normalized:
            normalized.append(tag)
    return normalized


def _normalize_str(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _normalize_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    return str(raw).strip().lower() in {"y", "yes", "true", "1", "on"}


def parse_deck_dict(data: dict[str, Any], base_dir: Path | None = None) -> DeckSpec:
    """Parse and validate a raw dictionary into a DeckSpec."""
    if not isinstance(data, dict):
        raise SpecValidationError("Deck specification root must be a YAML/JSON mapping")

    deck_section = data.get("deck")
    if isinstance(deck_section, dict):
        name = _normalize_str(deck_section.get("name"))
        description = _normalize_str(deck_section.get("description"))
        default_tags = _normalize_tags(deck_section.get("tags") or deck_section.get("default_tags"), "deck")
        css = _normalize_str(deck_section.get("css"))
    else:
        name = _normalize_str(data.get("name") or deck_section)
        description = _normalize_str(data.get("description"))
        default_tags = _normalize_tags(data.get("default_tags") or data.get("tags"), "deck")
        css = _normalize_str(data.get("css"))

    if not name:
        raise SpecValidationError("Deck must specify a non-empty 'name' (or 'deck.name')")

    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise SpecValidationError("Deck must contain a non-empty 'cards' list")

    cards: list[CardSpec] = []
    seen_ids: set[str] = set()

    for idx, raw_card in enumerate(raw_cards, start=1):
        ctx = f"card #{idx}"
        if not isinstance(raw_card, dict):
            raise SpecValidationError(f"{ctx}: must be a mapping")

        raw_type = _normalize_str(raw_card.get("type") or "qa").lower()
        add_reverse = _normalize_bool(raw_card.get("add_reverse"))
        if raw_type in ("qa", "basic"):
            card_type: CardType = "qa"
        elif raw_type == "reversed":
            card_type = "qa"
            add_reverse = True
        elif raw_type == "cloze":
            card_type = "cloze"
        else:
            raise SpecValidationError(
                f"{ctx}: invalid type '{raw_type}' (expected 'qa', 'basic', 'reversed', or 'cloze')"
            )

        card_id = _normalize_str(raw_card.get("id")) or None
        if card_id:
            if card_id in seen_ids:
                raise SpecValidationError(f"{ctx}: duplicate card id '{card_id}'")
            seen_ids.add(card_id)

        card = CardSpec(
            card_type=card_type,
            id=card_id,
            context=_normalize_str(raw_card.get("context") or raw_card.get("category")),
            front=_normalize_str(raw_card.get("front")),
            back=_normalize_str(raw_card.get("back")),
            text=_normalize_str(raw_card.get("text")),
            why_extra=_normalize_str(raw_card.get("why_extra") or raw_card.get("extra")),
            visual=_normalize_str(raw_card.get("visual") or raw_card.get("image")) or None,
            source_date=_normalize_str(raw_card.get("source_date") or raw_card.get("source")),
            add_reverse=add_reverse,
            tags=_normalize_tags(raw_card.get("tags"), ctx),
            subdeck=_normalize_str(raw_card.get("subdeck")) or None,
        )

        if card_type == "qa":
            if not card.front:
                raise SpecValidationError(f"{ctx}: 'qa' card requires a non-empty 'front'")
            if not card.back:
                raise SpecValidationError(f"{ctx}: 'qa' card requires a non-empty 'back'")
        else:
            if not card.text:
                raise SpecValidationError(f"{ctx}: 'cloze' card requires a non-empty 'text'")
            if not CLOZE_PATTERN.search(card.text):
                raise SpecValidationError(
                    f"{ctx}: 'cloze' card 'text' must contain at least one Anki cloze deletion like {{{{c1::...}}}}"
                )

        cards.append(card)

    return DeckSpec(
        name=name,
        description=description,
        default_tags=default_tags,
        css=css,
        cards=cards,
        base_dir=base_dir or Path.cwd(),
    )


def load_deck_spec(path: str | Path) -> DeckSpec:
    """Load and validate a DeckSpec from a YAML (.yaml/.yml) or JSON (.json) file."""
    spec_path = Path(path).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Deck spec file not found: {spec_path}")

    raw_text = spec_path.read_text(encoding="utf-8")
    suffix = spec_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(raw_text)
    else:
        data = yaml.safe_load(raw_text)

    return parse_deck_dict(data, base_dir=spec_path.parent)
