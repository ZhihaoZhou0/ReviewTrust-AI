"""Verify the exact DataHive snapshot audited by A1 before processing it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/data-audit.json"
RAW = ROOT / "data/raw"


def snapshot_manifest() -> dict:
    """Read A1's committed source revision, sizes, and SHA-256 digests."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def expected_counts() -> tuple[int, int]:
    """Return audited source counts, including repeated review rows."""
    manifest = snapshot_manifest()
    return (
        manifest["products"]["rows"],
        manifest["reviews"]["rows"],
    )


def verify_file(path: Path, expected_size: int, expected_sha256: str) -> None:
    """Reject missing, truncated, or changed source files."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing source file: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise ValueError(
            f"Unexpected size for {path.name}: {actual_size}; expected {expected_size}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path.name}; use the pinned revision in docs/data-audit.md"
        )


def verify_source_files(raw_dir: Path = RAW) -> dict[str, Path]:
    """Verify both inputs against the pinned A1 audit before an ETL run."""
    manifest = snapshot_manifest()
    paths = {}
    for kind in ("products", "reviews"):
        record = manifest[kind]
        path = raw_dir / f"{kind}.csv"
        verify_file(path, record["bytes"], record["sha256"])
        paths[kind] = path
    return paths
