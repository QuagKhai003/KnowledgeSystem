import tempfile
from pathlib import Path

import pytest

from src.ingestion.parsers.markdown import parse_markdown


@pytest.fixture
def sample_md(tmp_path):
    content = """---
tags: [algorithm, graph]
aliases: [MST, Minimum Spanning Tree]
---

# Kruskal's Algorithm

A greedy algorithm for finding minimum spanning trees.

## Overview

Uses [[UnionFind|Disjoint Set Union]] to track connected components.

## Complexity Analysis

Kruskal's algorithm runs in O(E log E) time complexity.
Uses sorting and union-find operations.

### Space Complexity

O(V) for the disjoint set structure.

## Implementation

```python
def kruskal(graph):
    pass
```

See also [[Prim Algorithm]] and [[Graph Theory]].
"""
    path = tmp_path / "kruskal.md"
    path.write_text(content)
    return str(path)


class TestMarkdownParser:
    def test_extracts_frontmatter(self, sample_md):
        result = parse_markdown(sample_md)
        assert "algorithm" in result["metadata"]["tags"]
        assert "MST" in result["metadata"]["aliases"]

    def test_extracts_wikilinks(self, sample_md):
        result = parse_markdown(sample_md)
        targets = [l["target"] for l in result["links"]]
        assert "UnionFind" in targets
        assert "Prim Algorithm" in targets
        assert "Graph Theory" in targets

    def test_extracts_aliases(self, sample_md):
        result = parse_markdown(sample_md)
        link = next(l for l in result["links"] if l["target"] == "UnionFind")
        assert link["alias"] == "Disjoint Set Union"

    def test_extracts_heading_hierarchy(self, sample_md):
        result = parse_markdown(sample_md)
        assert len(result["hierarchy"]) == 1
        root = result["hierarchy"][0]
        assert root["node"] == "H1: Kruskal's Algorithm"
        assert root["level"] == 1
        assert len(root["children"]) >= 2

    def test_nested_headings(self, sample_md):
        result = parse_markdown(sample_md)
        root = result["hierarchy"][0]
        complexity = next(c for c in root["children"] if "Complexity" in c["node"])
        assert len(complexity["children"]) == 1
        assert "Space" in complexity["children"][0]["node"]

    def test_extracts_tags(self, sample_md):
        result = parse_markdown(sample_md)
        assert "algorithm" in result["tags"]
        assert "graph" in result["tags"]

    def test_content_blocks_have_text(self, sample_md):
        result = parse_markdown(sample_md)
        assert len(result["content_blocks"]) > 0
        texts = [b["raw_text"] for b in result["content_blocks"]]
        assert any("O(V)" in t for t in texts)

    def test_handles_empty_file(self, tmp_path):
        path = tmp_path / "empty.md"
        path.write_text("")
        result = parse_markdown(str(path))
        assert result["hierarchy"] == []
        assert result["links"] == []
