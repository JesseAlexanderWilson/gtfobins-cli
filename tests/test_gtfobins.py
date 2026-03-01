#!/usr/bin/env python3
# GTFOBins CLI Tool - Unit Tests
# Author: Jesse

import json
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# ---------------------------------------------------------------------------
# Minimal stubs so the module can be imported without a real gtfobins.json
# ---------------------------------------------------------------------------
import importlib, types

# We'll import functions directly to avoid running main()
sys.path.insert(0, "/usr/local/bin/gtfobins")

# Patch open and Path.stat at import time so the module doesn't crash
_fake_db = json.dumps({"executables": {"vim": {"functions": {"shell": [{"code": "vim -c ':!/bin/sh'"}]}}}})

with patch("builtins.open", mock_open(read_data=_fake_db)), \
     patch("pathlib.Path.stat", return_value=MagicMock(st_mtime=datetime.now().timestamp())):
    import gtfobins as gtfo


# ---------------------------------------------------------------------------
# Fake data used across tests
# ---------------------------------------------------------------------------
FAKE_EXECUTABLES = {
    "vim": {
        "functions": {
            "shell": [{"code": "vim -c ':!/bin/sh'"}],
            "file-read": [{"code": "vim /path/to/file"}],
        }
    },
    "python3": {
        "functions": {
            "shell": [{"code": "python3 -c 'import os; os.system(\"/bin/sh\")'"}],
        }
    },
}


# ---------------------------------------------------------------------------
# show_last_updated()
# ---------------------------------------------------------------------------
class TestShowLastUpdated(unittest.TestCase):

    def test_updated_today(self):
        mock_stat = MagicMock(st_mtime=datetime.now().timestamp())
        with patch("pathlib.Path.stat", return_value=mock_stat):
            result = gtfo.show_last_updated()
        self.assertEqual(result, "API updated today.")

    def test_updated_one_day_ago(self):
        yesterday = (datetime.now() - timedelta(days=1)).timestamp()
        mock_stat = MagicMock(st_mtime=yesterday)
        with patch("pathlib.Path.stat", return_value=mock_stat):
            result = gtfo.show_last_updated()
        self.assertEqual(result, "API updated 1 day ago.")

    def test_updated_n_days_ago(self):
        five_days_ago = (datetime.now() - timedelta(days=5)).timestamp()
        mock_stat = MagicMock(st_mtime=five_days_ago)
        with patch("pathlib.Path.stat", return_value=mock_stat):
            result = gtfo.show_last_updated()
        self.assertEqual(result, "API updated 5 days ago.")

    def test_file_not_found(self):
        with patch("pathlib.Path.stat", side_effect=FileNotFoundError):
            result = gtfo.show_last_updated()
        self.assertIn("not found", result)


# ---------------------------------------------------------------------------
# check_programs()
# ---------------------------------------------------------------------------
class TestCheckPrograms(unittest.TestCase):

    def test_found_program_prints_output(self):
        with patch("builtins.print") as mock_print:
            gtfo.check_programs(["vim"], FAKE_EXECUTABLES)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("vim", printed)
        self.assertIn("FOUND IN GTFOBINS", printed)

    def test_not_found_program(self):
        with patch("builtins.print") as mock_print:
            gtfo.check_programs(["notarealprogram"], FAKE_EXECUTABLES)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("notarealprogram", printed)
        self.assertIn("NOT FOUND", printed)

    def test_deduplicates_programs(self):
        with patch("builtins.print") as mock_print:
            gtfo.check_programs(["vim", "vim", "vim"], FAKE_EXECUTABLES)
        found_count = sum(1 for c in mock_print.call_args_list if "FOUND IN GTFOBINS" in str(c))
        self.assertEqual(found_count, 1)

    def test_empty_list(self):
        with patch("builtins.print") as mock_print:
            gtfo.check_programs([], FAKE_EXECUTABLES)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("NOT FOUND", printed)


# ---------------------------------------------------------------------------
# parse_args()
# ---------------------------------------------------------------------------
class TestParseArgs(unittest.TestCase):

    def test_version_flag(self):
        with patch("sys.argv", ["gtfobins", "--version"]):
            args = gtfo.parse_args()
        self.assertTrue(args.version)

    def test_update_flag(self):
        with patch("sys.argv", ["gtfobins", "--update"]):
            args = gtfo.parse_args()
        self.assertTrue(args.update)

    def test_file_flag(self):
        with patch("sys.argv", ["gtfobins", "--file", "somefile.txt"]):
            args = gtfo.parse_args()
        self.assertEqual(args.file, "somefile.txt")

    def test_mutually_exclusive_flags(self):
        with patch("sys.argv", ["gtfobins", "--update", "--version"]):
            with self.assertRaises(SystemExit):
                gtfo.parse_args()


# ---------------------------------------------------------------------------
# fetch_programs_from_file()
# ---------------------------------------------------------------------------
class TestFetchProgramsFromFile(unittest.TestCase):

    def test_reads_program_names(self):
        fake_file = "/bin/vim\n/usr/bin/python3\n/bin/bash\n"
        with patch("builtins.open", mock_open(read_data=fake_file)):
            result = gtfo.fetch_programs_from_file("fakepath.txt")
        self.assertEqual(sorted(result), ["bash", "python3", "vim"])

    def test_file_not_found_exits(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            with self.assertRaises(SystemExit):
                gtfo.fetch_programs_from_file("nonexistent.txt")

    def test_ignores_blank_lines(self):
        fake_file = "/bin/vim\n\n/usr/bin/python3\n\n"
        with patch("builtins.open", mock_open(read_data=fake_file)):
            result = gtfo.fetch_programs_from_file("fakepath.txt")
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# fetch_programs_from_stdin()
# ---------------------------------------------------------------------------
class TestFetchProgramsFromStdin(unittest.TestCase):

    def test_filters_by_keyword(self):
        fake_stdin = (
            "some line without keyword\n"
            "1234 SUID /usr/bin/vim\n"
            "another line\n"
            "NOPASSWD /usr/bin/python3\n"
        )
        with patch("sys.stdin", StringIO(fake_stdin)):
            result = gtfo.fetch_programs_from_stdin()
        self.assertIn("vim", result)
        self.assertIn("python3", result)
        self.assertEqual(len(result), 2)

    def test_no_matches_returns_empty(self):
        fake_stdin = "nothing interesting here\njust normal lines\n"
        with patch("sys.stdin", StringIO(fake_stdin)):
            result = gtfo.fetch_programs_from_stdin()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# download_api()
# ---------------------------------------------------------------------------
class TestDownloadApi(unittest.TestCase):

    def test_successful_download(self):
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"executables": {}}).encode("utf-8")
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_response):
            data = gtfo.download_api()
        self.assertIn("executables", data)

    def test_network_error_raises_connection_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            with self.assertRaises(ConnectionError):
                gtfo.download_api()

    def test_invalid_json_raises_value_error(self):
        fake_response = MagicMock()
        fake_response.read.return_value = b"not valid json {{{"
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_response):
            with self.assertRaises(ValueError):
                gtfo.download_api()

    def test_missing_executables_key_raises_value_error(self):
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"something": "else"}).encode("utf-8")
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_response):
            with self.assertRaises(ValueError):
                gtfo.download_api()


if __name__ == "__main__":
    unittest.main(verbosity=2)