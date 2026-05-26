"""Universal text parser — fallback for any readable text file."""

from pathlib import Path


def parse_text(file_path: str) -> dict:
    """Parse any text file into a basic structure for compilation."""
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    return {
        "parser_source": "universal_text",
        "file_path": file_path,
        "raw_text": text,
        "line_count": len(lines),
        "extension": path.suffix.lower(),
    }
