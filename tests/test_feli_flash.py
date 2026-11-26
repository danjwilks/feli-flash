"""Unit and integration tests for Evidence-Based feli-flash tooling."""

from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

from feli_flash.audit import audit_deck_spec
from feli_flash.builder import build_apkg, export_tsv
from feli_flash.cli import main as cli_main
from feli_flash.inspect_apkg import inspect_apkg
from feli_flash.preview import generate_preview_html
from feli_flash.rendering import render_markdown
from feli_flash.schema import SpecValidationError, load_deck_spec, parse_deck_dict


def _sample_spec_dict(image_path: str | None = None) -> dict:
    return {
        "deck": {
            "name": "Canadian Tort Law",
            "description": "Evidence-based Tort Law deck",
            "tags": ["torts"],
        },
        "cards": [
            {
                "id": "battery-definition",
                "type": "qa",
                "context": "Torts · Intentional Torts (Person)",
                "front": "What is the legal definition of **battery**?",
                "back": "The actual infliction of **unlawful force** on another person.",
                "why_extra": "Unlike assault (apprehension of contact), battery requires actual physical contact with P's body.",
                "source_date": "IMG_4051.HEIC · 2026-11-25",
                "add_reverse": True,
                "tags": ["topic::torts::battery", "lens::definition"],
                **({"visual": image_path} if image_path else {}),
            },
            {
                "id": "battery-burden",
                "type": "qa",
                "context": "Torts · Battery",
                "front": "How does proving physical contact affect the **burden of proof** in battery?",
                "back": "Battery is a **per se** tort (no proof of harm required), so the burden shifts to D to prove a defense.",
                "why_extra": "Compare with IIMS, where P must prove visible and provable injury.",
                "source_date": "IMG_4051.HEIC · 2026-11-25",
                "tags": ["topic::torts::battery", "lens::mechanism"],
            },
            {
                "id": "battery-standard-cloze",
                "type": "cloze",
                "context": "Torts · Battery",
                "text": "Whether contact is harmful or offensive in battery is assessed {{c1::objectively}} as conduct beyond {{c2::ordinary social intercourse}}.",
                "why_extra": "Everyday incidental brushing in a crowd does not constitute battery.",
                "source_date": "IMG_4051.HEIC · 2026-11-25",
                "tags": ["topic::torts::battery", "lens::boundary"],
            },
        ],
    }


def _extract_guids(apkg_path: Path) -> set[str]:
    with zipfile.ZipFile(apkg_path, "r") as zf, tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "collection.anki2"
        db.write_bytes(zf.read("collection.anki2"))
        conn = sqlite3.connect(str(db))
        try:
            return {row[0] for row in conn.execute("SELECT guid FROM notes").fetchall()}
        finally:
            conn.close()


def test_render_markdown_preserves_cloze() -> None:
    rendered = render_markdown(
        "A **key** rule is {{c1::reasonable_person::standard}} in {{c2::BC}}.",
        preserve_cloze=True,
    )
    assert "<strong>key</strong>" in rendered
    assert "{{c1::reasonable_person::standard}}" in rendered
    assert "{{c2::BC}}" in rendered


def test_build_audit_and_inspect_apkg(tmp_path: Path) -> None:
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img_file = tmp_path / "diagram.png"
    img_file.write_bytes(png_bytes)

    spec = parse_deck_dict(_sample_spec_dict(image_path="diagram.png"), base_dir=tmp_path)
    audit = audit_deck_spec(spec)
    assert audit.passed, f"Unexpected audit errors: {audit.errors}"
    assert audit.warnings == []
    assert audit.reverse_count == 1
    assert audit.topic_clusters == {"topic::torts::battery": 3}

    out_apkg = tmp_path / "tort_law.apkg"
    result = build_apkg(spec, out_apkg)
    assert result.note_count == 3
    # 2 cards from reversed battery-definition + 1 from battery-burden + 2 from cloze (c1, c2) = 5 cards
    assert result.card_count == 5
    assert result.media_count == 1
    assert result.deck_names == ["Canadian Tort Law"]

    report = inspect_apkg(out_apkg)
    assert report.ok, f"Unexpected inspection errors: {report.errors}"
    assert report.note_count == 3
    assert report.card_count == 5
    assert len(report.media_files) == 1
    assert "topic::torts::battery" in report.tags


def test_deterministic_guids_across_rebuilds(tmp_path: Path) -> None:
    spec = parse_deck_dict(_sample_spec_dict(), base_dir=tmp_path)
    apkg_v1 = tmp_path / "v1.apkg"
    apkg_v2 = tmp_path / "v2.apkg"

    build_apkg(spec, apkg_v1)
    spec.cards[1].back = "Updated explanation for battery burden shift."
    build_apkg(spec, apkg_v2)

    assert _extract_guids(apkg_v1) == _extract_guids(apkg_v2)


def test_audit_catches_spec_violations() -> None:
    bad_spec = parse_deck_dict(
        {
            "name": "Bad Deck",
            "cards": [
                {
                    "id": "binary-card",
                    "type": "qa",
                    "front": "Is proof of harm required for battery?",
                    "back": "No.",
                    "tags": ["topic::orphan"],
                },
                {
                    "id": "list-all-card",
                    "type": "qa",
                    "context": "Torts",
                    "front": "List all 8 elements of inducing breach of contract.",
                    "back": "1, 2, 3, 4, 5, 6, 7, 8.",
                    "tags": ["topic::orphan"],
                },
                {
                    "id": "leaking-reverse",
                    "type": "qa",
                    "context": "Torts · Battery",
                    "front": "What is **battery**?",
                    "back": "Unlawful force.",
                    "add_reverse": True,
                    "tags": ["topic::orphan_two"],
                },
            ],
        }
    )
    report = audit_deck_spec(bad_spec)
    assert not report.passed
    gates = {f.gate for f in report.errors}
    assert "Cue Hygiene" in gates
    assert "Anti-Pattern-Matching" in gates
    assert "Atomicity" in gates
    assert "Reverse Hygiene" in gates
    assert any(f.gate == "Transfer & Cluster" for f in report.warnings)


def test_preview_and_tsv_export(tmp_path: Path) -> None:
    spec = parse_deck_dict(_sample_spec_dict(), base_dir=tmp_path)

    preview_file = generate_preview_html(spec, tmp_path / "preview.html")
    html_text = preview_file.read_text(encoding="utf-8")
    assert "Canadian Tort Law" in html_text
    assert "Recommended Anki FSRS-6 Settings" in html_text
    assert "+ Reverse" in html_text
    assert "Study Mode" in html_text
    assert "Dark Mode" in html_text

    tsv_file = export_tsv(spec, tmp_path / "deck.tsv")
    tsv_lines = tsv_file.read_text(encoding="utf-8").splitlines()
    assert tsv_lines[0] == "#separator:tab"
    assert len(tsv_lines) == 3 + 3


def test_validation_errors() -> None:
    with pytest.raises(SpecValidationError, match="cloze"):
        parse_deck_dict({"name": "Test", "cards": [{"type": "cloze", "text": "No cloze markers here"}]})

    with pytest.raises(SpecValidationError, match="duplicate card id"):
        parse_deck_dict(
            {
                "name": "Test",
                "cards": [
                    {"id": "dup", "front": "Q1", "back": "A1"},
                    {"id": "dup", "front": "Q2", "back": "A2"},
                ],
            }
        )


def test_inspect_catches_invalid_zip(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_zip.apkg"
    bad.write_text("hello world", encoding="utf-8")
    report = inspect_apkg(bad)
    assert not report.ok
    assert any("ZIP" in e for e in report.errors)


def test_cli_end_to_end(tmp_path: Path) -> None:
    spec_file = tmp_path / "starter.yaml"
    apkg_file = tmp_path / "starter.apkg"
    preview_file = tmp_path / "starter.html"
    tsv_file = tmp_path / "starter.tsv"

    assert cli_main(["init", str(spec_file)]) == 0
    assert load_deck_spec(spec_file).name == "Sample Study Deck"
    assert cli_main(["audit", str(spec_file), "--strict"]) == 0
    assert (
        cli_main(
            [
                "build",
                str(spec_file),
                "-o",
                str(apkg_file),
                "--preview",
                str(preview_file),
                "--tsv",
                str(tsv_file),
                "--strict",
            ]
        )
        == 0
    )
    assert cli_main(["inspect", str(apkg_file)]) == 0
