"""Core Anki (.apkg) deck builder and optional TSV exporter."""

from __future__ import annotations

import csv
import html
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import genanki

from feli_flash.media import MediaBundler
from feli_flash.rendering import render_markdown, stable_int_id
from feli_flash.schema import CLOZE_PATTERN, CardSpec, DeckSpec
from feli_flash.templates import build_cloze_model, build_qa_model

EMAIL_RECOMMENDED_LIMIT_BYTES = 20 * 1024 * 1024  # 20 MB (safe for email attachments)


@dataclass
class BuildResult:
    """Summary metadata returned after building an .apkg package."""

    output_path: Path
    size_bytes: int
    deck_names: list[str]
    note_count: int
    card_count: int
    media_count: int
    warnings: list[str] = field(default_factory=list)


def _merge_tags(default_tags: list[str], card_tags: list[str]) -> list[str]:
    merged: list[str] = []
    for tag in [*default_tags, *card_tags]:
        if tag and tag not in merged:
            merged.append(tag)
    return merged


def _note_guid(deck_name: str, card: CardSpec, index: int) -> str:
    """Create a deterministic Anki note GUID so re-sharing updates cards in place."""
    if card.id:
        return genanki.guid_for("feli-flash", deck_name, card.id)
    key_parts = [
        "feli-flash",
        deck_name,
        card.context,
        card.card_type,
        card.front or card.text or str(index),
    ]
    return genanki.guid_for(*key_parts)


def _estimate_cards_for_note(card: CardSpec) -> int:
    if card.card_type == "qa":
        return 2 if card.add_reverse else 1
    indices = {match.group(1) for match in CLOZE_PATTERN.finditer(card.text)}
    return max(1, len(indices))


def _img_tag(bundler: MediaBundler, raw_path: str | None) -> str:
    if not raw_path:
        return ""
    prepared = bundler.resolve(raw_path)
    return f'<img src="{html.escape(prepared.anki_filename, quote=True)}">'


def build_apkg(
    spec: DeckSpec,
    output_path: str | Path,
    *,
    max_image_dimension: int = 1400,
) -> BuildResult:
    """Compile a validated DeckSpec into a shareable Anki .apkg package."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    namespace = spec.name
    qa_model = build_qa_model(namespace, spec.css)
    cloze_model = build_cloze_model(namespace, spec.css)

    decks_by_name: dict[str, genanki.Deck] = {}

    def get_deck(subdeck: str | None) -> genanki.Deck:
        full_name = f"{spec.name}::{subdeck}" if subdeck else spec.name
        if full_name not in decks_by_name:
            deck_obj = genanki.Deck(
                stable_int_id("feli-flash-deck", full_name),
                full_name,
                description=spec.description if full_name == spec.name else "",
            )
            decks_by_name[full_name] = deck_obj
        return decks_by_name[full_name]

    get_deck(None)

    total_cards = 0
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="feli_flash_media_") as tmpdir:
        bundler = MediaBundler(spec.base_dir, Path(tmpdir), max_dimension=max_image_dimension)

        for idx, card in enumerate(spec.cards, start=1):
            target_deck = get_deck(card.subdeck)
            tags = _merge_tags(spec.default_tags, card.tags)
            guid = _note_guid(spec.name, card, idx)
            context_html = html.escape(card.context)
            source_html = html.escape(card.source_date)
            visual_html = _img_tag(bundler, card.visual)

            if card.card_type == "qa":
                fields = [
                    context_html,
                    render_markdown(card.front),
                    render_markdown(card.back),
                    render_markdown(card.why_extra),
                    visual_html,
                    source_html,
                    "y" if card.add_reverse else "",
                ]
                note = genanki.Note(model=qa_model, fields=fields, tags=tags, guid=guid)
            elif card.card_type == "cloze":
                fields = [
                    context_html,
                    render_markdown(card.text, preserve_cloze=True),
                    render_markdown(card.why_extra),
                    visual_html,
                    source_html,
                ]
                note = genanki.Note(model=cloze_model, fields=fields, tags=tags, guid=guid)
            else:
                raise ValueError(f"Unsupported card type: {card.card_type}")

            target_deck.add_note(note)
            total_cards += _estimate_cards_for_note(card)

        active_decks = [
            deck for deck in decks_by_name.values() if deck.notes or (deck.name == spec.name and spec.description)
        ]
        if not active_decks:
            active_decks = list(decks_by_name.values())

        package = genanki.Package(active_decks)
        package.media_files = bundler.packaged_files
        package.write_to_file(str(out))
        media_count = len(bundler.packaged_files)

    size_bytes = out.stat().st_size
    if size_bytes > EMAIL_RECOMMENDED_LIMIT_BYTES:
        mb = size_bytes / (1024 * 1024)
        warnings.append(
            f"Package size is {mb:.1f} MB, which may exceed standard email attachment limits (~20-25 MB)."
        )

    return BuildResult(
        output_path=out,
        size_bytes=size_bytes,
        deck_names=[d.name for d in active_decks],
        note_count=len(spec.cards),
        card_count=total_cards,
        media_count=media_count,
        warnings=warnings,
    )


def export_tsv(spec: DeckSpec, output_path: str | Path) -> Path:
    """Export a plain tab-separated file (Anki-compatible fallback format)."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="") as fh:
        fh.write("#separator:tab\n")
        fh.write("#html:true\n")
        fh.write("#tags column:5\n")
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")

        for card in spec.cards:
            tags = " ".join(_merge_tags(spec.default_tags, card.tags))
            if card.card_type == "qa":
                writer.writerow(
                    [
                        html.escape(card.context),
                        render_markdown(card.front),
                        render_markdown(card.back),
                        render_markdown(card.why_extra),
                        tags,
                    ]
                )
            else:
                writer.writerow(
                    [
                        html.escape(card.context),
                        render_markdown(card.text, preserve_cloze=True),
                        "",
                        render_markdown(card.why_extra),
                        tags,
                    ]
                )

    return out
