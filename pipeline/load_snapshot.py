"""Clean and transactionally load the pinned DataHive snapshot into PostgreSQL.

Prerequisites: source CSVs in data/raw/, PostgreSQL running, and psql installed.
From the repository root: python3 pipeline/load_snapshot.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PRODUCTS = ROOT / "data/raw/products.csv"
RAW_REVIEWS = ROOT / "data/raw/reviews.csv"
REPORT = ROOT / "docs/cleaning-report.json"


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in (RAW_PRODUCTS, RAW_REVIEWS) if not path.is_file()]
    if missing:
        print(f"Missing source files: {', '.join(missing)}. See docs/data-audit.md for pinned download commands.", file=sys.stderr)
        return 2
    psql = shutil.which("psql")
    if not psql:
        print("psql is required. Install the PostgreSQL client (libpq) and add it to PATH.", file=sys.stderr)
        return 2

    subprocess.run(
        [
            sys.executable, str(ROOT / "pipeline/clean_dataset.py"),
            "--products", str(RAW_PRODUCTS),
            "--reviews", str(RAW_REVIEWS),
            "--output-dir", str(ROOT / "data/processed"),
            "--report", str(REPORT),
        ],
        check=True,
        cwd=ROOT,
    )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if any(key.startswith("rejected_") for name in ("products", "reviews") for key in report[name]):
        print("Cleaning rejected source rows; inspect docs/cleaning-report.json before loading.", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("PGHOST", "127.0.0.1")
    env.setdefault("PGPORT", env.get("POSTGRES_PORT", "5433"))
    env.setdefault("PGUSER", env.get("POSTGRES_USER", "reviewtrust"))
    env.setdefault("PGDATABASE", env.get("POSTGRES_DB", "reviewtrust"))
    env.setdefault("PGPASSWORD", env.get("POSTGRES_PASSWORD", "reviewtrust_dev"))
    command = [
        psql, "-X", "-v", "ON_ERROR_STOP=1", "-1",
        "-f", "database/schema.sql", "-f", "database/load_snapshot.sql",
    ]
    try:
        subprocess.run(command, check=True, cwd=ROOT, env=env)
    except subprocess.CalledProcessError as error:
        print("PostgreSQL import failed; the transaction was rolled back.", file=sys.stderr)
        return error.returncode
    print("Snapshot import complete. Re-running this command will not duplicate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
