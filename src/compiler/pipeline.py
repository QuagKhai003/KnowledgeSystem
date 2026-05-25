"""Compiler pipeline: transforms Phase 1 parser output into Knowledge Objects."""

import re
from pathlib import Path

from .schemas import KnowledgeObject, Abstraction, Relationship
from .ontology import Ontology, ALLOWED_PREDICATES
from .ontology_val import OntologyValidator


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s-]+", "_", slug).strip("_")


class CompilerPipeline:
    """Compiles parser outputs into validated Knowledge Objects."""

    def __init__(self, ontology: Ontology | None = None):
        self.ontology = ontology or Ontology()
        self.validator = OntologyValidator(self.ontology)

    def compile_markdown(self, parsed: dict) -> list[KnowledgeObject]:
        file_path = parsed.get("file_path", "")
        metadata = parsed.get("metadata", {})
        name = metadata.get("title") or Path(file_path).stem
        tags = parsed.get("tags", [])

        concept_id = f"concept_{_slugify(name)}"
        file_id = file_path

        level_0_parts = [b["raw_text"] for b in parsed.get("content_blocks", [])]
        level_0 = "\n\n".join(level_0_parts)

        if not level_0.strip():
            raw_text = parsed.get("raw_text", "")
            if not raw_text and file_path:
                try:
                    raw_text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    raw_text = ""
            level_0 = raw_text

        level_1 = self._build_level_1_from_hierarchy(parsed.get("hierarchy", []))
        if not level_1 and level_0:
            level_1 = self._build_level_1_from_text(level_0)

        level_2 = self._build_level_2_summary(name, level_0, tags)

        domain = self._infer_domain(tags) or self._infer_domain_from_name(name)

        concept = KnowledgeObject(
            id=concept_id,
            type="concept",
            name=name,
            domain=domain,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1, level_2=level_2),
            ontology_class="Concept",
            ontology_depth=3,
            tags=tags,
            metadata=metadata,
        )

        # Build relationships from wikilinks
        for link in parsed.get("links", []):
            target_id = f"concept_{_slugify(link['target'])}"
            concept.relationships.append(
                Relationship(target=target_id, predicate="uses")
            )

        # File node
        file_obj = KnowledgeObject(
            id=file_id,
            type="implementation",
            name=Path(file_path).name,
            source_file=file_path,
            ontology_class="Implementation",
            ontology_depth=4,
            relationships=[Relationship(target=concept_id, predicate="example_of")],
        )

        return [concept, file_obj]

    def compile_code(self, parsed: dict) -> list[KnowledgeObject]:
        file_path = parsed.get("file_path", "")
        file_name = Path(file_path).stem
        objects = []

        # File-level implementation node
        file_id = file_path
        file_obj = KnowledgeObject(
            id=file_id,
            type="implementation",
            name=Path(file_path).name,
            source_file=file_path,
            ontology_class="Implementation",
            ontology_depth=4,
        )

        # Import relationships
        for imp in parsed.get("imports", []):
            module = imp["module"].split(".")[-1]
            target_id = f"concept_{_slugify(module)}"
            file_obj.relationships.append(
                Relationship(target=target_id, predicate="depends_on")
            )

        # Class-level concept nodes
        for cls in parsed.get("classes", []):
            cls_id = f"concept_{_slugify(cls['name'])}"
            methods_desc = ", ".join(m["name"] for m in cls.get("methods", []))
            level_1 = f"Class {cls['name']}"
            if cls.get("bases"):
                level_1 += f" extends {', '.join(cls['bases'])}"
            if methods_desc:
                level_1 += f" with methods: {methods_desc}"

            cls_obj = KnowledgeObject(
                id=cls_id,
                type="concept",
                name=cls["name"],
                source_file=file_path,
                abstractions=Abstraction(level_1=level_1),
                ontology_class="DataStructure",
                ontology_depth=3,
            )

            # Inheritance
            for base in cls.get("bases", []):
                base_id = f"concept_{_slugify(base)}"
                cls_obj.relationships.append(
                    Relationship(target=base_id, predicate="extends")
                )

            file_obj.relationships.append(
                Relationship(target=cls_id, predicate="example_of")
            )
            objects.append(cls_obj)

        # Top-level function concept nodes
        for func in parsed.get("functions", []):
            func_id = f"concept_{_slugify(file_name)}_{_slugify(func['name'])}"
            args_str = ", ".join(func.get("args", []))
            ret = func.get("returns", "")
            level_1 = f"Function {func['name']}({args_str})"
            if ret:
                level_1 += f" -> {ret}"

            func_obj = KnowledgeObject(
                id=func_id,
                type="concept",
                name=func["name"],
                source_file=file_path,
                abstractions=Abstraction(level_1=level_1),
                ontology_class="Algorithm",
                ontology_depth=4,
            )
            objects.append(func_obj)

        objects.append(file_obj)
        return objects

    def compile_pdf(self, parsed: dict) -> list[KnowledgeObject]:
        file_path = parsed.get("file_path", "")
        file_name = Path(file_path).stem

        concept_id = f"concept_{_slugify(file_name)}"
        pages = parsed.get("pages", [])
        level_0 = "\n\n".join(p.get("text", "") for p in pages)

        headings = parsed.get("headings", [])
        level_1 = "; ".join(h["text"] for h in headings) if headings else ""

        outline = parsed.get("outline", [])
        if not level_1 and outline:
            level_1 = "; ".join(o["title"] for o in outline)

        concept = KnowledgeObject(
            id=concept_id,
            type="reference",
            name=file_name,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1),
            ontology_class="Reference",
            ontology_depth=3,
        )

        file_obj = KnowledgeObject(
            id=file_path,
            type="implementation",
            name=Path(file_path).name,
            source_file=file_path,
            ontology_class="Implementation",
            relationships=[Relationship(target=concept_id, predicate="example_of")],
        )

        return [concept, file_obj]

    def compile(self, parsed: dict, file_type: str) -> list[KnowledgeObject]:
        dispatch = {
            "markdown": self.compile_markdown,
            "code": self.compile_code,
            "pdf": self.compile_pdf,
        }
        compiler = dispatch.get(file_type)
        if compiler is None:
            return []
        return compiler(parsed)

    def compile_and_validate(self, parsed: dict, file_type: str) -> tuple[list[KnowledgeObject], list]:
        objects = self.compile(parsed, file_type)
        errors = self.validator.validate(objects)
        return objects, errors

    def _build_level_1_from_hierarchy(self, hierarchy: list[dict]) -> str:
        parts = []
        self._flatten_headings(hierarchy, parts)
        return "; ".join(parts)

    def _flatten_headings(self, nodes: list[dict], parts: list[str]):
        for node in nodes:
            parts.append(node["node"])
            if node.get("children"):
                self._flatten_headings(node["children"], parts)

    def _build_level_1_from_text(self, text: str) -> str:
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
        outline_parts = []
        for p in paragraphs[:20]:
            first_sentence = re.split(r'[.!?]\s', p)[0].strip()
            if len(first_sentence) > 20 and not first_sentence.isdigit():
                cleaned = re.sub(r'\s+', ' ', first_sentence)[:150]
                outline_parts.append(cleaned)
        seen = set()
        unique = []
        for part in outline_parts:
            key = part[:50].lower()
            if key not in seen:
                seen.add(key)
                unique.append(part)
        return "; ".join(unique[:10])

    def _build_level_2_summary(self, name: str, text: str, tags: list[str]) -> str:
        if not text or len(text) < 50:
            return ""
        keywords = set()
        for pattern in [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
            r'▪\s*(.+?)(?:\n|$)',
            r'(?:is|are|means?|refers?\s+to|defined?\s+as)\s+(.{20,120}?)[.\n]',
        ]:
            matches = re.findall(pattern, text[:5000])
            for m in matches[:10]:
                cleaned = m.strip() if isinstance(m, str) else m
                if len(cleaned) > 5:
                    keywords.add(cleaned)

        bullet_points = re.findall(r'▪\s*(.+?)(?:\n|$)', text[:5000])
        key_points = [bp.strip() for bp in bullet_points if len(bp.strip()) > 10][:8]

        parts = [f"{name}."]
        if key_points:
            parts.append("Key topics: " + "; ".join(key_points))
        elif keywords:
            top_kw = sorted(keywords, key=len, reverse=True)[:8]
            parts.append("Covers: " + ", ".join(top_kw))

        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        if paragraphs:
            first_meaningful = paragraphs[0]
            first_sentence = re.split(r'[.!?]\s', first_meaningful)[0].strip()
            if len(first_sentence) > 30:
                parts.append(first_sentence[:200])

        return " ".join(parts)[:500]

    def _infer_domain_from_name(self, name: str) -> str:
        name_lower = name.lower()
        domain_map = {
            "security": "cybersecurity", "cyber": "cybersecurity",
            "crypto": "cryptography", "encrypt": "cryptography",
            "network": "networking", "wireless": "networking", "mobile": "networking",
            "cloud": "cloud_computing", "access": "identity_management",
            "auth": "identity_management", "vulnerab": "vulnerability_management",
            "ethic": "ethics", "privacy": "ethics", "crime": "ethics",
            "algorithm": "algorithms", "data_structure": "data_structures",
            "math": "mathematics", "web": "web_development",
        }
        for keyword, domain in domain_map.items():
            if keyword in name_lower:
                return domain
        return "general"

    def _infer_domain(self, tags: list[str]) -> str:
        if not tags:
            return ""
        domain_keywords = {
            "algorithm": "algorithms",
            "graph": "graph_algorithms",
            "data_structure": "data_structures",
            "architecture": "architecture",
            "math": "mathematics",
            "web": "web_development",
            "system": "systems",
            "security": "cybersecurity",
        }
        for tag in tags:
            for keyword, domain in domain_keywords.items():
                if keyword in tag.lower():
                    return domain
        return tags[0] if tags else ""
