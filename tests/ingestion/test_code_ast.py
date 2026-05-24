from pathlib import Path

import pytest

from src.ingestion.parsers.code_ast import parse_code


@pytest.fixture
def sample_py(tmp_path):
    content = '''"""Sample module for testing."""

import os
from pathlib import Path
from typing import Optional, List

CONSTANT = 42


class BaseProcessor:
    """Base class for processors."""

    def __init__(self, name: str):
        self.name = name

    def process(self, data: List[str]) -> Optional[dict]:
        raise NotImplementedError


class FileProcessor(BaseProcessor):
    """Processes files from disk."""

    @staticmethod
    def validate(path: str) -> bool:
        return os.path.exists(path)

    def process(self, data: List[str]) -> Optional[dict]:
        return {"files": data}


def standalone_function(x: int, y: int = 0) -> int:
    """Add two numbers."""
    return x + y
'''
    path = tmp_path / "sample.py"
    path.write_text(content)
    return str(path)


class TestCodeAstParser:
    def test_extracts_imports(self, sample_py):
        result = parse_code(sample_py)
        modules = [i["module"] for i in result["imports"]]
        assert "os" in modules
        assert "pathlib.Path" in modules

    def test_extracts_classes(self, sample_py):
        result = parse_code(sample_py)
        names = [c["name"] for c in result["classes"]]
        assert "BaseProcessor" in names
        assert "FileProcessor" in names

    def test_class_inheritance(self, sample_py):
        result = parse_code(sample_py)
        fp = next(c for c in result["classes"] if c["name"] == "FileProcessor")
        assert "BaseProcessor" in fp["bases"]

    def test_class_methods(self, sample_py):
        result = parse_code(sample_py)
        bp = next(c for c in result["classes"] if c["name"] == "BaseProcessor")
        method_names = [m["name"] for m in bp["methods"]]
        assert "__init__" in method_names
        assert "process" in method_names

    def test_extracts_functions(self, sample_py):
        result = parse_code(sample_py)
        assert len(result["functions"]) == 1
        func = result["functions"][0]
        assert func["name"] == "standalone_function"
        assert "x" in func["args"]
        assert func["returns"] == "int"

    def test_line_bounds(self, sample_py):
        result = parse_code(sample_py)
        for cls in result["classes"]:
            assert cls["line_bounds"][0] < cls["line_bounds"][1]

    def test_handles_syntax_error(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(\n")
        result = parse_code(str(bad))
        assert result["error"] == "SyntaxError"

    def test_method_decorators(self, sample_py):
        result = parse_code(sample_py)
        fp = next(c for c in result["classes"] if c["name"] == "FileProcessor")
        validate = next(m for m in fp["methods"] if m["name"] == "validate")
        assert "staticmethod" in validate["decorators"]
