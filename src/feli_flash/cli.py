"""Command-line interface for feli-flash."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feli_flash.audit import audit_deck_spec
from feli_flash.builder import build_apkg, export_tsv
from feli_flash.inspect_apkg import inspect_apkg
from feli_flash.preview import generate_preview_html
from feli_flash.schema import SpecValidationError, load_deck_spec

STARTER_TEMPLATE = """\
# Evidence-Based Anki Deck Specification (feli-flash)
# Flat deck + rich hierarchical '::' tags + atomic Q&A and tight Cloze cards.
# Build & audit:
#   uv run feli-flash build deck.yaml -o dist/deck.apkg --preview dist/deck.html

deck:
  name: "Sample Study Deck"
  description: "Shareable Evidence-Based Anki deck (enable FSRS-6 at 0.85-0.90 DR, all 3 sibling-burying options ON)."
  tags:
    - sample

cards:
  - id: sample-qa-definition
    type: qa
    context: "Spaced Repetition · Core Formats"
    front: "What self-contained file format lets recipients import a shared Anki deck with styling and media in one click?"
    back: "An **`.apkg`** (Anki Package) archive."
    why_extra: "Works across Anki Desktop, AnkiMobile (iOS), and AnkiDroid (Android); deterministic note GUIDs update existing cards in place on re-import."
    source_date: "feli-flash Starter · 2026-11-25"
    add_reverse: false
    tags:
      - topic::spaced_repetition::packaging
      - lens::definition

  - id: sample-qa-contrast
    type: qa
    context: "Spaced Repetition · Deck Architecture"
    front: "Why should an evidence-based Anki deck use one flat broad deck with hierarchical `::` tags instead of chapter subdecks?"
    back: "To preserve **cross-topic interleaving** and prevent narrow subdeck names from giving away answers."
    why_extra: "Use Filtered Decks only for temporary pre-exam review or backlog recovery; reviewed cards automatically return to their home deck."
    source_date: "Evidence-Based Spec · Stage 3"
    tags:
      - topic::spaced_repetition::packaging
      - lens::mechanism

  - id: sample-cloze-fsrs
    type: cloze
    context: "Spaced Repetition · FSRS-6 Grading"
    text: "Under FSRS-6, pressing **Hard** counts as a {{c1::passing grade}}, so any forgotten or partial recall must be graded {{c2::Again}}."
    why_extra: "Using Hard as a soft fail corrupts FSRS optimization and generates overly long intervals."
    source_date: "Evidence-Based Spec · Stage 5"
    tags:
      - topic::spaced_repetition::packaging
      - lens::boundary
"""


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _print_audit(spec_path: Path, *, strict: bool = False) -> int:
    spec = load_deck_spec(spec_path)
    report = audit_deck_spec(spec)
    status = "PASS" if report.passed and (not strict or not report.warnings) else "FAIL"
    print(f"QA Audit [{status}]: {spec.name}")
    print(
        f"  Notes:    {report.note_count} (Q&A: {report.qa_count}, Reverse: {report.reverse_count}, Cloze: {report.cloze_count})"
    )
    print(f"  Transfer: {report.transfer_prompt_count} elaborative/contrast prompt(s)")
    if report.topic_clusters:
        print(f"  Clusters: {len(report.topic_clusters)} topic cluster(s)")
    for f in report.findings:
        stream = sys.stderr if f.severity == "error" else sys.stdout
        print(f"  [{f.severity.upper()}] ({f.gate}) {f.card_ref}: {f.message}", file=stream)
    if not report.passed:
        return 1
    if strict and report.warnings:
        return 1
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).expanduser().resolve()
    spec = load_deck_spec(spec_path)

    if not args.no_audit:
        audit = audit_deck_spec(spec)
        if not audit.passed or (args.strict and audit.warnings):
            print("QA Acceptance Gate audit failed:", file=sys.stderr)
            for f in audit.findings:
                print(f"  [{f.severity.upper()}] ({f.gate}) {f.card_ref}: {f.message}", file=sys.stderr)
            return 1
        print(
            f"QA Audit: PASS ({audit.note_count} notes, {len(audit.topic_clusters)} topic clusters, "
            f"{audit.transfer_prompt_count} transfer prompts, {len(audit.warnings)} warnings)"
        )
        for w in audit.warnings:
            print(f"  [WARN] ({w.gate}) {w.card_ref}: {w.message}")

    output_apkg = Path(args.output) if args.output else Path("dist") / f"{spec_path.stem}.apkg"
    result = build_apkg(spec, output_apkg, max_image_dimension=args.max_image_dim)

    print(f"Built Anki package: {result.output_path}")
    print(f"  Size:   {_format_size(result.size_bytes)}")
    print(f"  Decks:  {', '.join(result.deck_names)}")
    print(f"  Notes:  {result.note_count} ({result.card_count} cards)")
    if result.media_count:
        print(f"  Media:  {result.media_count} file(s) bundled")

    if not args.no_verify:
        report = inspect_apkg(result.output_path)
        if not report.ok:
            print("Verification FAILED:", file=sys.stderr)
            for err in report.errors:
                print(f"  ERROR: {err}", file=sys.stderr)
            return 1
        print(f"  Verify: OK ({report.card_count} cards verified in SQLite)")

    if args.preview:
        preview_out = Path(args.preview).expanduser().resolve()
        apkg_href = result.output_path.name if preview_out.parent == result.output_path.parent else None
        preview_path = generate_preview_html(spec, preview_out, apkg_href=apkg_href)
        print(f"  Preview: {preview_path}")

    if args.tsv:
        tsv_path = export_tsv(spec, args.tsv)
        print(f"  TSV:    {tsv_path}")

    for warning in result.warnings:
        print(f"  WARN:   {warning}", file=sys.stderr)

    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    return _print_audit(Path(args.spec).expanduser().resolve(), strict=args.strict)


def _cmd_inspect(args: argparse.Namespace) -> int:
    report = inspect_apkg(args.apkg)
    status = "OK" if report.ok else "FAILED"
    print(f"Inspection [{status}]: {report.path}")
    print(f"  Size:   {_format_size(report.size_bytes)}")
    print(f"  Decks:  {', '.join(report.decks) or '(none)'}")
    print(f"  Models: {', '.join(report.models) or '(none)'}")
    print(f"  Notes:  {report.note_count}")
    print(f"  Cards:  {report.card_count}")
    print(f"  Tags:   {len(report.tags)} unique tag(s)")
    print(f"  Media:  {len(report.media_files)} file(s)")
    for warning in report.warnings:
        print(f"  WARN:   {warning}")
    for err in report.errors:
        print(f"  ERROR:  {err}", file=sys.stderr)
    return 0 if report.ok else 1


def _cmd_preview(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).expanduser().resolve()
    spec = load_deck_spec(spec_path)
    out = Path(args.output) if args.output else Path("dist") / f"{spec_path.stem}-preview.html"
    written = generate_preview_html(spec, out)
    print(f"Generated browser preview: {written}")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.output).expanduser().resolve()
    if out.exists() and not args.force:
        print(f"File already exists: {out} (use --force to overwrite)", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(STARTER_TEMPLATE, encoding="utf-8")
    print(f"Created starter deck spec: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feli-flash",
        description="Build, audit, preview, and validate shareable Evidence-Based Anki (.apkg) decks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_build = subparsers.add_parser("build", help="Compile a YAML/JSON deck spec into a shareable .apkg file.")
    p_build.add_argument("spec", help="Path to deck spec (.yaml, .yml, or .json)")
    p_build.add_argument("-o", "--output", help="Output .apkg path (default: dist/<spec-name>.apkg)")
    p_build.add_argument("--preview", help="Also generate a standalone HTML preview at this path")
    p_build.add_argument("--tsv", help="Also export a tab-separated (.tsv) fallback file at this path")
    p_build.add_argument(
        "--max-image-dim",
        type=int,
        default=1400,
        help="Maximum width/height in pixels when converting HEIC images (default: 1400)",
    )
    p_build.add_argument("--no-verify", action="store_true", help="Skip post-build .apkg SQLite verification")
    p_build.add_argument("--no-audit", action="store_true", help="Skip Evidence-Based QA Acceptance Gate audit")
    p_build.add_argument("--strict", action="store_true", help="Fail build on QA audit warnings as well as errors")
    p_build.set_defaults(func=_cmd_build)

    p_audit = subparsers.add_parser("audit", help="Run Evidence-Based QA Acceptance Gate checks on a deck spec.")
    p_audit.add_argument("spec", help="Path to deck spec (.yaml, .yml, or .json)")
    p_audit.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    p_audit.set_defaults(func=_cmd_audit)

    p_inspect = subparsers.add_parser("inspect", help="Validate and inspect an existing .apkg package.")
    p_inspect.add_argument("apkg", help="Path to .apkg file")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_preview = subparsers.add_parser("preview", help="Generate a browser HTML preview from a deck spec.")
    p_preview.add_argument("spec", help="Path to deck spec (.yaml, .yml, or .json)")
    p_preview.add_argument("-o", "--output", help="Output HTML path (default: dist/<spec-name>-preview.html)")
    p_preview.set_defaults(func=_cmd_preview)

    p_init = subparsers.add_parser("init", help="Create a documented starter deck YAML template.")
    p_init.add_argument("output", nargs="?", default="decks/sample.yaml", help="Target YAML file path")
    p_init.add_argument("-f", "--force", action="store_true", help="Overwrite if file exists")
    p_init.set_defaults(func=_cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, SpecValidationError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
