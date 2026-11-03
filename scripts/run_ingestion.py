"""CLI entry point for the ingestion pipeline.

Usage:
    python scripts/run_ingestion.py                 # process INCOMING_DIR
    python scripts/run_ingestion.py --dir some/path
    python scripts/run_ingestion.py --file report.xlsx

Intended to be run by a scheduler (Windows Task Scheduler / SQL Agent /
cron) each morning after the reports land. Exit code is non-zero if any
file failed, so the scheduler can alert.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hkn_asset.config import get_settings
from hkn_asset.ingestion.pipeline import process_directory, process_file
from hkn_asset.logging_setup import setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, help="directory of .xlsx reports")
    parser.add_argument("--file", type=Path, help="a single report file")
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    if args.file:
        results = [process_file(args.file)]
    else:
        results = process_directory(args.dir or settings.incoming_dir)

    failed = [r for r in results if r.status == "FAILED"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
