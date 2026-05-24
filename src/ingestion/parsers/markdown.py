import re
from pathlib import Path

import yaml
import mistune

WIKILINK_PATTERN = re.compile(r"\[\[([^\]|\\]+)(?:[\\|]+([^\]]+))?\]\]")
TAG_PATTERN = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]*)")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_markdown(file_path: str) -> dict:
    """Parse a markdown file into a structured representation."""
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    metadata = _extract_frontmatter(text)
    links = _extract_wikilinks(lines)
    tags = _extract_tags(text, metadata)
    hierarchy = _extract_heading_hierarchy(lines)
    content_blocks = _extract_content_blocks(lines, hierarchy)

    return {
        "parser_source": "markdown_mistune",
        "file_path": file_path,
        "metadata": metadata,
        "hierarchy": hierarchy,
        "links": links,
        "tags": tags,
        "content_blocks": content_blocks,
    }


def _extract_frontmatter(text: str) -> dict:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}
    try:
        fm = yaml.safe_load(match.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def _extract_wikilinks(lines: list[str]) -> list[dict]:
    links = []
    for i, line in enumerate(lines):
        for match in WIKILINK_PATTERN.finditer(line):
            links.append({
                "target": match.group(1).strip(),
                "alias": match.group(2).strip() if match.group(2) else None,
                "line_offset": i + 1,
            })
    return links


def _extract_tags(text: str, metadata: dict) -> list[str]:
    inline_tags = set(TAG_PATTERN.findall(text))
    fm_tags = metadata.get("tags", [])
    if isinstance(fm_tags, list):
        inline_tags.update(str(t) for t in fm_tags)
    return sorted(inline_tags)


def _extract_heading_hierarchy(lines: list[str]) -> list[dict]:
    headings = []
    for i, line in enumerate(lines):
        if line.startswith("#"):
            stripped = line.lstrip("#")
            level = len(line) - len(stripped)
            title = stripped.strip()
            if title:
                headings.append({
                    "node": f"H{level}: {title}",
                    "level": level,
                    "line": i + 1,
                })

    return _nest_headings(headings, lines)


def _nest_headings(flat_headings: list[dict], lines: list[str]) -> list[dict]:
    """Convert flat heading list into nested hierarchy with line bounds."""
    if not flat_headings:
        return []

    total_lines = len(lines)

    for i, h in enumerate(flat_headings):
        start = h["line"]
        end = flat_headings[i + 1]["line"] - 1 if i + 1 < len(flat_headings) else total_lines
        h["line_bounds"] = [start, end]
        h["children"] = []

    root_nodes = []
    stack = []

    for h in flat_headings:
        node = {
            "node": h["node"],
            "level": h["level"],
            "line_bounds": h["line_bounds"],
            "children": [],
        }
        while stack and stack[-1]["level"] >= h["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            root_nodes.append(node)
        stack.append(node)

    return root_nodes


def _extract_content_blocks(lines: list[str], hierarchy: list[dict]) -> list[dict]:
    """Extract text blocks under each leaf heading."""
    blocks = []
    _collect_blocks(hierarchy, lines, blocks)
    return blocks


def _collect_blocks(nodes: list[dict], lines: list[str], blocks: list[dict]):
    for node in nodes:
        if node["children"]:
            _collect_blocks(node["children"], lines, blocks)
        else:
            start, end = node["line_bounds"]
            raw = "\n".join(lines[start:end])  # skip heading line itself
            if raw.strip():
                blocks.append({
                    "heading_context": node["node"],
                    "start_line": start,
                    "end_line": end,
                    "raw_text": raw,
                })
