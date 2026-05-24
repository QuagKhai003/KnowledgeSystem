from pathlib import Path

from .markdown import parse_markdown
from .code_ast import parse_code
from .pdf_layout import parse_pdf

PARSER_MAP = {
    "markdown": parse_markdown,
    "code": parse_code,
    "pdf": parse_pdf,
}


def parse_file(file_path: str | Path, file_type: str) -> dict | None:
    """Route a file to the appropriate parser based on its type."""
    parser = PARSER_MAP.get(file_type)
    if parser is None:
        return None
    return parser(str(file_path))
