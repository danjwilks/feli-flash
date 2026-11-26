"""feli-flash: Evidence-Based Shareable Anki (.apkg) deck builder, auditor, and previewer."""

from feli_flash.audit import AuditFinding, AuditReport, audit_deck_spec
from feli_flash.builder import BuildResult, build_apkg, export_tsv
from feli_flash.inspect_apkg import ApkgInspection, inspect_apkg
from feli_flash.preview import generate_preview_html
from feli_flash.schema import CardSpec, DeckSpec, SpecValidationError, load_deck_spec

__version__ = "0.2.0"

__all__ = [
    "ApkgInspection",
    "AuditFinding",
    "AuditReport",
    "BuildResult",
    "CardSpec",
    "DeckSpec",
    "SpecValidationError",
    "audit_deck_spec",
    "build_apkg",
    "export_tsv",
    "generate_preview_html",
    "inspect_apkg",
    "load_deck_spec",
]
