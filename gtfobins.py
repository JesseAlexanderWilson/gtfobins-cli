#!/usr/bin/env python3
# GTFOBins CLI Tool
# Author: Jesse
# License: MIT
# Description: Checks SUID binaries against GTFOBins database

import sys
import os
import stat
import json
import argparse
import urllib.error
import urllib.request
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).resolve().parent / "API"
JSON_PATH = SCRIPT_DIR / "gtfobins.json"
API_URL = "https://gtfobins.org/api.json"
KEYWORDS = ["NOPASSWD", "SUID", "SETUID"]

DEFAULT_SUID = {
    "ping", "ping6", "umount", "mount", "su", "sudo",
    "gpasswd", "newgrp", "chfn", "chsh", "passwd",
    "dbus-daemon-launch-helper", "ssh-keysign", "snap-confine",
    "pppd", "fusermount", "polkit-agent-helper-1", "dmcrypt-get-device"
}

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def show_last_updated() -> str:
    """Return a human-readable string indicating when the database was last updated."""
    try:
        mtime = JSON_PATH.stat().st_mtime
        modified = datetime.fromtimestamp(mtime)
        days_ago = (datetime.now() - modified).days
        if days_ago == 0:
            return "API updated today."
        elif days_ago == 1:
            return "API updated 1 day ago."
        else:
            return f"API updated {days_ago} days ago."
    except FileNotFoundError:
        return "API database not found. Run --update to download it."


def show_version() -> None:
    """Print version and database update info."""
    print(f"GTFOBins CLI v{VERSION}")
    print(show_last_updated())


def load_database() -> dict[str, Any]:
    """Load and return the GTFOBins JSON database."""
    try:
        with open(JSON_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        log.error(f"Database not found at {JSON_PATH}. Run --update to download it.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log.error(f"Database file is corrupted ({e}). Run --update to re-download it.")
        sys.exit(1)


def download_api() -> dict[str, Any]:
    """Fetch the latest GTFOBins data from the API and return it as a dict."""
    try:
        with urllib.request.urlopen(API_URL, timeout=10) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Could not reach GTFOBins API: {e.reason}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"API returned invalid JSON: {e}") from e

    if "executables" not in data:
        raise ValueError("API response is missing 'executables' key — unexpected format.")

    return data


def update_gtfobins() -> None:
    """Download the latest GTFOBins database and save it to disk."""
    log.info(f"Fetching latest GTFOBins data from {API_URL}...")
    try:
        data = download_api()
        with open(JSON_PATH, "w") as f:
            json.dump(data, f, indent=2)
        log.info(f"Updated successfully. {len(data['executables'])} executables in database.")
    except (ConnectionError, ValueError) as e:
        log.error(str(e))
        sys.exit(1)


def fetch_programs_from_file(path: str) -> list[str]:
    """Read a file and return a list of program names."""
    try:
        with open(path) as f:
            return [line.strip().split("/")[-1] for line in f if line.strip()]
    except FileNotFoundError:
        log.error(f"File not found: {path}")
        sys.exit(1)


def fetch_programs_from_stdin() -> list[str]:
    """Read program names from stdin, filtering by keywords."""
    programs = []
    for line in sys.stdin:
        line = line.strip()
        if any(keyword in line for keyword in KEYWORDS):
            programs.append(line.split("/")[-1])
    return programs


def find_suid() -> list[str]:
    """
    Find all SUID binaries on the system using pure Python.
    Walks the filesystem and checks the SUID bit via os.stat(),
    avoiding a shell subprocess call.
    """
    programs = []
    for root, dirs, files in os.walk("/"):
        dirs[:] = [d for d in dirs if d not in ("proc", "sys", "dev", "run")]
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                st = os.stat(filepath)
                if st.st_mode & stat.S_ISUID:
                    programs.append(filename)
            except (PermissionError, FileNotFoundError, OSError):
                continue
    return programs


def check_programs(programs: list[str], executables: dict[str, Any]) -> None:
    """
    Check a list of program names against the GTFOBins database and print results.
    Splits output into three tiers:
      1. Found in GTFOBins — exploitable
      2. Known default SUID — expected, not interesting
      3. Unknown — not in GTFOBins and not a known default, worth investigating
    """
    unique_programs = sorted(set(programs))
    default = []
    unknown = []
    found = []

    for program in unique_programs:
        if program in executables:
            found.append(program)
        elif program in DEFAULT_SUID:
            default.append(program)
        else:
            unknown.append(program)

    if found:
        print("\nFOUND IN GTFOBINS\n")
        for program in found:
            print(f"  {program}:")
            for function, entries in executables[program]["functions"].items():
                for entry in entries:
                    code = entry.get("code", "")
                    if code:
                        formatted = code.replace("\n", "\n        ")
                        print(f"    - {function}\n        {formatted}\n")

    if default:
        print("\nDEFAULT SUID (expected, not interesting)\n")
        for program in default:
            print(f"  {program}")

    if unknown:
        print("\nUNKNOWN SUID (not in GTFOBins, worth investigating)\n")
        for program in unknown:
            print(f"  {program}")


def parse_args() -> argparse.Namespace:
    """Build and return the argument parser with mutually exclusive action flags."""
    parser = argparse.ArgumentParser(
        prog="gtfobins",
        description="Check SUID binaries against the GTFOBins database."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--version", action="store_true", help="Show version and API update info")
    group.add_argument("--update", action="store_true", help="Fetch the latest GTFOBins API data")
    group.add_argument("--file", metavar="FILE", help="File containing list of binaries to check")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.version:
        show_version()
        return

    print(show_last_updated())

    if args.update:
        update_gtfobins()
        return

    data = load_database()
    executables = data["executables"]

    if args.file:
        programs = fetch_programs_from_file(args.file)
    elif not sys.stdin.isatty():
        programs = fetch_programs_from_stdin()
    else:
        programs = find_suid()

    check_programs(programs, executables)


if __name__ == "__main__":
    main()