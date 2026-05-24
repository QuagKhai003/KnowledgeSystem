import tempfile
from pathlib import Path

import pytest

from src.ingestion.scanner import Scanner
from src.ingestion.state_db import StateDB


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "note.md").write_text("# Hello\nSome content")
    (tmp_path / "script.py").write_text("def hello():\n    pass")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.md").write_text("# Deep note\n[[note]]")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored")
    return tmp_path


@pytest.fixture
def state_db(tmp_path):
    db = StateDB(tmp_path / "test_state.db")
    yield db
    db.close()


class TestScanner:
    def test_discovers_supported_files(self, workspace, state_db):
        scanner = Scanner(workspace, state_db)
        results = list(scanner.walk())
        paths = {r["path"] for r in results}

        assert str(workspace / "note.md") in paths
        assert str(workspace / "script.py") in paths
        assert str(workspace / "sub" / "deep.md") in paths

    def test_ignores_git_directory(self, workspace, state_db):
        scanner = Scanner(workspace, state_db)
        results = list(scanner.walk())
        paths = {r["path"] for r in results}

        assert not any(".git" in p for p in paths)

    def test_incremental_scan_skips_unchanged(self, workspace, state_db):
        scanner = Scanner(workspace, state_db)
        first_run = list(scanner.walk())
        second_run = list(scanner.walk())

        assert len(first_run) == 3
        assert len(second_run) == 0

    def test_detects_changed_files(self, workspace, state_db):
        scanner = Scanner(workspace, state_db)
        list(scanner.walk())

        (workspace / "note.md").write_text("# Updated content")
        results = list(scanner.walk())

        assert len(results) == 1
        assert results[0]["status"] == "CHANGED"

    def test_marks_deleted_files(self, workspace, state_db):
        scanner = Scanner(workspace, state_db)
        list(scanner.walk())

        (workspace / "script.py").unlink()
        list(scanner.walk())

        active = state_db.get_all_active_paths()
        assert str(workspace / "script.py") not in active
