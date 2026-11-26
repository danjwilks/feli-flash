"""Media preparation and optional HEIC->JPEG conversion for shareable .apkg decks."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PreparedMedia:
    """Represents a media file ready to be bundled into an .apkg package."""

    original_path: Path
    packaged_path: Path
    anki_filename: str


class MediaBundler:
    """Resolves, normalizes, and deduplicates media files for an Anki package."""

    def __init__(self, base_dir: Path, staging_dir: Path, max_dimension: int = 1400) -> None:
        self.base_dir = base_dir
        self.staging_dir = staging_dir
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.max_dimension = max_dimension
        self._cache: dict[Path, PreparedMedia] = {}

    def resolve(self, raw_path: str) -> PreparedMedia:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = (self.base_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not candidate.exists():
            raise FileNotFoundError(f"Card media file not found: {candidate}")

        if candidate in self._cache:
            return self._cache[candidate]

        content_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()[:10]
        safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in candidate.stem)[:40]
        suffix = candidate.suffix.lower()

        if suffix in (".heic", ".heif"):
            anki_filename = f"ff_{content_hash}_{safe_stem}.jpg"
            dest = self.staging_dir / anki_filename
            self._convert_heic_to_jpeg(candidate, dest)
        else:
            anki_filename = f"ff_{content_hash}_{safe_stem}{suffix}"
            dest = self.staging_dir / anki_filename
            shutil.copy2(candidate, dest)

        prepared = PreparedMedia(
            original_path=candidate,
            packaged_path=dest,
            anki_filename=anki_filename,
        )
        self._cache[candidate] = prepared
        return prepared

    def _convert_heic_to_jpeg(self, source: Path, dest: Path) -> None:
        sips = shutil.which("sips")
        if not sips:
            raise RuntimeError(
                f"Cannot convert HEIC image '{source.name}': macOS 'sips' tool not found. "
                "Please convert the image to JPEG/PNG first."
            )
        cmd = [
            sips,
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            "80",
            "-Z",
            str(self.max_dimension),
            str(source),
            "--out",
            str(dest),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not dest.exists():
            raise RuntimeError(f"Failed converting HEIC '{source}' via sips: {result.stderr.strip()}")

    @property
    def packaged_files(self) -> list[str]:
        return [str(item.packaged_path) for item in self._cache.values()]
