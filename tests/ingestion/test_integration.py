"""Integration tests: run parsers against real workspace files."""

import json
import time
from pathlib import Path

import pytest

from src.ingestion.scanner import Scanner
from src.ingestion.state_db import StateDB
from src.ingestion.parsers.markdown import parse_markdown
from src.ingestion.parsers.code_ast import parse_code
from src.ingestion.parsers import parse_file

WORKSPACE = Path(__file__).parent.parent.parent


class TestObsidianWikilinks:
    """Verify wikilink parsing handles Obsidian's backslash-escaped pipe."""

    def test_escaped_pipe_alias(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text(r"See [[target\|Display Name]] for details")
        result = parse_markdown(str(md))
        assert len(result["links"]) == 1
        assert result["links"][0]["target"] == "target"
        assert result["links"][0]["alias"] == "Display Name"

    def test_standard_pipe_alias(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("See [[target|Display Name]] for details")
        result = parse_markdown(str(md))
        assert len(result["links"]) == 1
        assert result["links"][0]["target"] == "target"
        assert result["links"][0]["alias"] == "Display Name"

    def test_no_alias(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("See [[target]] for details")
        result = parse_markdown(str(md))
        assert len(result["links"]) == 1
        assert result["links"][0]["target"] == "target"
        assert result["links"][0]["alias"] is None


class TestRealWorkspace:
    """Run against actual project files to validate end-to-end."""

    def test_parse_project_md(self):
        path = WORKSPACE / "PROJECT.md"
        if not path.exists():
            pytest.skip("PROJECT.md not found")
        result = parse_markdown(str(path))
        assert result["parser_source"] == "markdown_mistune"
        assert len(result["hierarchy"]) > 0
        assert result["hierarchy"][0]["level"] == 1

    def test_parse_own_source(self):
        path = WORKSPACE / "src" / "ingestion" / "scanner.py"
        if not path.exists():
            pytest.skip("scanner.py not found")
        result = parse_code(str(path))
        assert result["parser_source"] == "python_ast"
        classes = [c["name"] for c in result["classes"]]
        assert "Scanner" in classes

    def test_parse_blueprint_with_wikilinks(self):
        path = WORKSPACE / "blueprint" / "01_Roadmap_and_Phases" / "phase_1_ingestion_and_extraction.md"
        if not path.exists():
            pytest.skip("phase_1 file not found")
        result = parse_markdown(str(path))
        targets = [l["target"] for l in result["links"]]
        assert "01_ingestion_layer" in targets
        assert "02_structural_extraction" in targets

    def test_router_dispatches_correctly(self):
        md_path = WORKSPACE / "PROJECT.md"
        py_path = WORKSPACE / "src" / "ingestion" / "scanner.py"
        if not md_path.exists() or not py_path.exists():
            pytest.skip("workspace files missing")

        md_result = parse_file(str(md_path), "markdown")
        py_result = parse_file(str(py_path), "code")
        assert md_result["parser_source"] == "markdown_mistune"
        assert py_result["parser_source"] == "python_ast"

    def test_scanner_performance(self, tmp_path):
        """Verify scanner meets <10ms per file target on small workspace."""
        state_db = StateDB(tmp_path / "perf.db")
        for i in range(100):
            (tmp_path / f"note_{i}.md").write_text(f"# Note {i}\nContent here")

        start = time.time()
        results = list(Scanner(tmp_path, state_db).walk())
        elapsed = time.time() - start
        state_db.close()

        assert len(results) == 100
        per_file_ms = (elapsed / 100) * 1000
        assert per_file_ms < 10, f"Per-file time {per_file_ms:.2f}ms exceeds 10ms target"
