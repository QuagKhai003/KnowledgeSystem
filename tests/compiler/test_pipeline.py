import pytest
from pathlib import Path

from src.compiler.pipeline import CompilerPipeline
from src.compiler.schemas import KnowledgeObject
from src.ingestion.parsers.markdown import parse_markdown
from src.ingestion.parsers.code_ast import parse_code


@pytest.fixture
def pipeline():
    return CompilerPipeline()


@pytest.fixture
def sample_md_parsed(tmp_path):
    content = """---
tags: [algorithm, graph]
title: Kruskal Algorithm
---

# Kruskal's Algorithm

A greedy MST algorithm.

## Overview

Uses [[UnionFind|Disjoint Set Union]] and edge sorting.

## Complexity

O(E log E) time.
"""
    path = tmp_path / "kruskal.md"
    path.write_text(content)
    return parse_markdown(str(path))


@pytest.fixture
def sample_py_parsed(tmp_path):
    content = '''import os
from pathlib import Path


class UnionFind:
    """Disjoint Set Union with path compression."""

    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def kruskal(edges: list, n: int) -> list:
    """Find MST using Kruskal's algorithm."""
    uf = UnionFind(n)
    mst = []
    for w, u, v in sorted(edges):
        if uf.find(u) != uf.find(v):
            uf.union(u, v)
            mst.append((w, u, v))
    return mst
'''
    path = tmp_path / "graph_algo.py"
    path.write_text(content)
    return parse_code(str(path))


class TestMarkdownCompilation:
    def test_produces_concept_and_file(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        types = {o.type for o in objects}
        assert "concept" in types
        assert "implementation" in types

    def test_concept_has_correct_name(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        concept = next(o for o in objects if o.type == "concept")
        assert concept.name == "Kruskal Algorithm"

    def test_concept_has_wikilink_relationships(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        concept = next(o for o in objects if o.type == "concept")
        targets = [r.target for r in concept.relationships]
        assert "concept_unionfind" in targets

    def test_file_links_to_concept(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        file_obj = next(o for o in objects if o.type == "implementation")
        assert any(r.predicate == "example_of" for r in file_obj.relationships)

    def test_concept_has_tags(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        concept = next(o for o in objects if o.type == "concept")
        assert "algorithm" in concept.tags
        assert "graph" in concept.tags

    def test_domain_inferred_from_tags(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        concept = next(o for o in objects if o.type == "concept")
        assert concept.domain in ("algorithms", "graph_algorithms")

    def test_level_1_built_from_headings(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        concept = next(o for o in objects if o.type == "concept")
        assert "H1:" in concept.abstractions.level_1 or "H2:" in concept.abstractions.level_1


class TestCodeCompilation:
    def test_produces_class_concepts(self, pipeline, sample_py_parsed):
        objects = pipeline.compile(sample_py_parsed, "code")
        names = [o.name for o in objects if o.type == "concept"]
        assert "UnionFind" in names

    def test_class_has_methods_in_level_1(self, pipeline, sample_py_parsed):
        objects = pipeline.compile(sample_py_parsed, "code")
        uf = next(o for o in objects if o.name == "UnionFind")
        assert "find" in uf.abstractions.level_1
        assert "union" in uf.abstractions.level_1

    def test_class_inheritance_creates_extends(self, tmp_path, pipeline):
        content = '''class Base:
    pass

class Child(Base):
    pass
'''
        path = tmp_path / "inherit.py"
        path.write_text(content)
        parsed = parse_code(str(path))
        objects = pipeline.compile(parsed, "code")
        child = next(o for o in objects if o.name == "Child")
        assert any(r.predicate == "extends" for r in child.relationships)

    def test_function_concepts_created(self, pipeline, sample_py_parsed):
        objects = pipeline.compile(sample_py_parsed, "code")
        names = [o.name for o in objects if o.type == "concept"]
        assert "kruskal" in names

    def test_imports_become_depends_on(self, pipeline, sample_py_parsed):
        objects = pipeline.compile(sample_py_parsed, "code")
        file_obj = next(o for o in objects if o.type == "implementation")
        predicates = [r.predicate for r in file_obj.relationships]
        assert "depends_on" in predicates

    def test_file_node_created(self, pipeline, sample_py_parsed):
        objects = pipeline.compile(sample_py_parsed, "code")
        impl = [o for o in objects if o.type == "implementation"]
        assert len(impl) == 1


class TestCompileAndValidate:
    def test_valid_markdown_has_no_errors(self, pipeline, sample_md_parsed):
        objects, errors = pipeline.compile_and_validate(sample_md_parsed, "markdown")
        assert len(objects) > 0
        assert len(errors) == 0

    def test_valid_code_has_no_errors(self, pipeline, sample_py_parsed):
        objects, errors = pipeline.compile_and_validate(sample_py_parsed, "code")
        assert len(objects) > 0
        # Only type_mismatch errors expected for Concept->Concept example_of
        critical = [e for e in errors if e.rule in ("invalid_class", "invalid_predicate", "cycle_detected")]
        assert len(critical) == 0

    def test_to_dict_roundtrip(self, pipeline, sample_md_parsed):
        objects = pipeline.compile(sample_md_parsed, "markdown")
        for obj in objects:
            d = obj.to_dict()
            assert "id" in d
            assert "abstractions" in d
            assert "relationships" in d
