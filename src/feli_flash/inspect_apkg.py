"""Inspect and validate generated Anki (.apkg) packages before sharing."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from feli_flash.builder import EMAIL_RECOMMENDED_LIMIT_BYTES

_IMG_SRC_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)


@dataclass
class ApkgInspection:
    """Validation and summary report for an .apkg archive."""

    path: Path
    size_bytes: int
    decks: list[str]
    models: list[str]
    note_count: int
    card_count: int
    tags: list[str]
    media_files: list[str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def inspect_apkg(path: str | Path) -> ApkgInspection:
    """Open an .apkg archive, validate its SQLite schema & media references, and summarize it."""
    apkg_path = Path(path).expanduser().resolve()
    if not apkg_path.exists():
        raise FileNotFoundError(f".apkg file not found: {apkg_path}")

    size_bytes = apkg_path.stat().st_size
    errors: list[str] = []
    warnings: list[str] = []
    decks: list[str] = []
    models: list[str] = []
    tags_set: set[str] = set()
    media_files: list[str] = []
    note_count = 0
    card_count = 0

    if not zipfile.is_zipfile(apkg_path):
        errors.append("File is not a valid ZIP archive (.apkg must be a ZIP).")
        return ApkgInspection(
            path=apkg_path,
            size_bytes=size_bytes,
            decks=decks,
            models=models,
            note_count=0,
            card_count=0,
            tags=[],
            media_files=[],
            errors=errors,
            warnings=warnings,
        )

    with zipfile.ZipFile(apkg_path, "r") as zf:
        names = set(zf.namelist())
        db_name = None
        for candidate in ("collection.anki21", "collection.anki2"):
            if candidate in names:
                db_name = candidate
                break

        if not db_name:
            errors.append("Missing collection.anki2 / collection.anki21 database inside .apkg.")
            return ApkgInspection(
                path=apkg_path,
                size_bytes=size_bytes,
                decks=decks,
                models=models,
                note_count=0,
                card_count=0,
                tags=[],
                media_files=[],
                errors=errors,
                warnings=warnings,
            )

        media_map: dict[str, str] = {}
        if "media" not in names:
            errors.append("Missing 'media' manifest inside .apkg.")
        else:
            try:
                media_map = json.loads(zf.read("media").decode("utf-8"))
                media_files = sorted(media_map.values())
                for numeric_key, filename in media_map.items():
                    if numeric_key not in names:
                        errors.append(f"Media entry '{filename}' (key {numeric_key}) is missing from archive.")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"Invalid 'media' JSON manifest: {exc}")

        with tempfile.TemporaryDirectory(prefix="feli_flash_inspect_") as tmpdir:
            db_path = Path(tmpdir) / db_name
            db_path.write_bytes(zf.read(db_name))

            conn = sqlite3.connect(str(db_path))
            try:
                cur = conn.cursor()
                row = cur.execute("SELECT decks, models FROM col LIMIT 1").fetchone()
                if not row:
                    errors.append("SQLite 'col' table is empty.")
                else:
                    decks_json = json.loads(row[0])
                    models_json = json.loads(row[1])
                    decks = sorted(d["name"] for d in decks_json.values() if d.get("name") != "Default")
                    if not decks:
                        decks = sorted(d["name"] for d in decks_json.values())
                    models = sorted(m["name"] for m in models_json.values())

                note_rows = cur.execute("SELECT guid, flds, tags FROM notes").fetchall()
                note_count = len(note_rows)
                card_count = int(cur.execute("SELECT COUNT(*) FROM cards").fetchone()[0])

                seen_guids: set[str] = set()
                referenced_media: set[str] = set()
                for guid, flds, raw_tags in note_rows:
                    if guid in seen_guids:
                        errors.append(f"Duplicate note GUID found: {guid}")
                    seen_guids.add(guid)
                    for tag in raw_tags.split():
                        if tag:
                            tags_set.add(tag)
                    for match in _IMG_SRC_RE.finditer(flds):
                        referenced_media.add(match.group(1))

                bundled_media_set = set(media_files)
                for ref in sorted(referenced_media):
                    if ref not in bundled_media_set:
                        errors.append(f"Note references image '{ref}' which is not bundled in .apkg media.")
            finally:
                conn.close()

    if note_count == 0:
        warnings.append("Package contains 0 notes.")
    if card_count == 0:
        errors.append("Package contains 0 cards.")
    if size_bytes > EMAIL_RECOMMENDED_LIMIT_BYTES:
        mb = size_bytes / (1024 * 1024)
        warnings.append(f"Package is {mb:.1f} MB, which may exceed standard email attachment limits (~20-25 MB).")

    return ApkgInspection(
        path=apkg_path,
        size_bytes=size_bytes,
        decks=decks,
        models=models,
        note_count=note_count,
        card_count=card_count,
        tags=sorted(tags_set),
        media_files=media_files,
        errors=errors,
        warnings=warnings,
    )
