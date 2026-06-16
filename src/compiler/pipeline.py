"""Compiler pipeline: transforms Phase 1 parser output into Knowledge Objects."""

import math
import re
from collections import Counter
from pathlib import Path

from .schemas import KnowledgeObject, Abstraction, Relationship
from .ontology import Ontology, ALLOWED_PREDICATES
from .ontology_val import OntologyValidator


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s-]+", "_", slug).strip("_")[:200]


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
        level_3 = self._build_level_3_keywords(level_0)

        domain = self._infer_domain(tags) or self._infer_domain_from_name(name)

        concept = KnowledgeObject(
            id=concept_id,
            type="concept",
            name=name,
            domain=domain,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1, level_2=level_2, level_3=level_3),
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
        raw_text = parsed.get("raw_text", "")

        level_0 = raw_text
        level_1_parts = []
        for cls in parsed.get("classes", []):
            desc = f"Class {cls['name']}"
            if cls.get("bases"):
                desc += f" extends {', '.join(cls['bases'])}"
            methods = ", ".join(m["name"] for m in cls.get("methods", []))
            if methods:
                desc += f" with methods: {methods}"
            level_1_parts.append(desc)
        for func in parsed.get("functions", []):
            args_str = ", ".join(func.get("args", []))
            desc = f"Function {func['name']}({args_str})"
            ret = func.get("returns", "")
            if ret:
                desc += f" -> {ret}"
            level_1_parts.append(desc)
        level_1 = "; ".join(level_1_parts)

        prose_parts = parsed.get("docstrings", []) + parsed.get("comments", [])
        if prose_parts:
            level_2 = " ".join(prose_parts)[:800]
        else:
            level_2 = self._identifiers_to_prose(parsed)

        level_3 = self._code_keywords(parsed, raw_text)

        concept_id = f"concept_{_slugify(Path(file_path).stem)}"
        concept = KnowledgeObject(
            id=concept_id,
            type="implementation",
            name=Path(file_path).name,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1, level_2=level_2, level_3=level_3),
            ontology_class="Implementation",
            ontology_depth=4,
            domain=self._infer_domain_from_name(Path(file_path).stem),
        )

        for imp in parsed.get("imports", []):
            module = imp["module"].split(".")[-1]
            concept.relationships.append(
                Relationship(target=f"concept_{_slugify(module)}", predicate="depends_on")
            )

        return [concept]

    def _identifiers_to_prose(self, parsed: dict) -> str:
        """Convert identifier names to natural language when no comments exist."""
        names = []
        for cls in parsed.get("classes", []):
            names.append(self._split_identifier(cls["name"]))
            for m in cls.get("methods", []):
                if not m["name"].startswith("_"):
                    names.append(self._split_identifier(m["name"]))
        for func in parsed.get("functions", []):
            if not func["name"].startswith("_"):
                names.append(self._split_identifier(func["name"]))
        for imp in parsed.get("imports", []):
            parts = imp["module"].split(".")
            names.append(" ".join(parts[-2:]) if len(parts) > 1 else parts[0])
        return " ".join(names)[:800] if names else ""

    def _split_identifier(self, name: str) -> str:
        """Split camelCase and snake_case into words."""
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        words = words.replace("_", " ")
        return words.lower().strip()

    def _code_keywords(self, parsed: dict, raw_text: str) -> str:
        """Extract searchable keywords from code: identifiers + imports + comments."""
        terms = set()
        for cls in parsed.get("classes", []):
            terms.add(cls["name"].lower())
            terms.add(self._split_identifier(cls["name"]))
            for m in cls.get("methods", []):
                terms.add(self._split_identifier(m["name"]))
        for func in parsed.get("functions", []):
            terms.add(self._split_identifier(func["name"]))
        for imp in parsed.get("imports", []):
            parts = imp["module"].split(".")
            for p in parts:
                if len(p) > 2:
                    terms.add(p.lower())
        for doc in parsed.get("docstrings", []):
            words = re.findall(r'\b[a-z]{3,}\b', doc.lower())
            terms.update(words[:20])
        for comment in parsed.get("comments", []):
            words = re.findall(r'\b[a-z]{3,}\b', comment.lower())
            terms.update(words[:10])
        terms.discard("")
        return "; ".join(sorted(terms)[:100])

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

        level_3 = self._build_level_3_keywords(level_0)

        concept = KnowledgeObject(
            id=concept_id,
            type="reference",
            name=file_name,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1, level_3=level_3),
            ontology_class="Concept",
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

    def compile_text(self, parsed: dict) -> list[KnowledgeObject]:
        """Universal text compiler — works for any readable text file."""
        file_path = parsed.get("file_path", "")
        raw_text = parsed.get("raw_text", "")
        name = Path(file_path).name

        level_0 = raw_text
        level_1 = self._build_level_1_from_text(raw_text)
        level_2 = self._build_level_2_summary(name, raw_text, [])
        level_3 = self._build_level_3_keywords(raw_text)

        concept_id = f"concept_{_slugify(Path(file_path).stem)}"
        concept = KnowledgeObject(
            id=concept_id,
            type="concept",
            name=name,
            source_file=file_path,
            abstractions=Abstraction(level_0=level_0, level_1=level_1, level_2=level_2, level_3=level_3),
            ontology_class="Concept",
            ontology_depth=3,
            domain=self._infer_domain_from_name(Path(file_path).stem),
        )
        return [concept]

    def compile(self, parsed: dict, file_type: str) -> list[KnowledgeObject]:
        dispatch = {
            "markdown": self.compile_markdown,
            "code": self.compile_code,
            "pdf": self.compile_pdf,
            "text": self.compile_text,
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
            matches = re.findall(pattern, text)
            for m in matches[:15]:
                cleaned = m.strip() if isinstance(m, str) else m
                if len(cleaned) > 5:
                    keywords.add(cleaned)

        bullet_points = re.findall(r'▪\s*(.+?)(?:\n|$)', text)
        key_points = [bp.strip() for bp in bullet_points if len(bp.strip()) > 10][:8]

        parts = [f"{name}."]
        if key_points:
            parts.append("Key topics: " + "; ".join(key_points))
        elif keywords:
            top_kw = sorted(keywords, key=len, reverse=True)[:8]
            parts.append("Covers: " + ", ".join(top_kw))

        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        sampled = self._sample_passages(paragraphs)
        for p in sampled:
            first_sentence = re.split(r'[.!?]\s', p)[0].strip()
            if len(first_sentence) > 30:
                parts.append(first_sentence[:200])

        return " ".join(parts)[:800]

    def _sample_passages(self, paragraphs: list[str], n: int = 3) -> list[str]:
        """Sample passages from beginning, middle, and end of document."""
        if not paragraphs:
            return []
        if len(paragraphs) <= n:
            return paragraphs
        indices = [0, len(paragraphs) // 2, len(paragraphs) - 1]
        return [paragraphs[i] for i in indices]

    def _build_level_3_keywords(self, text: str) -> str:
        """TF-IDF keyword extraction across the entire document. No AI needed."""
        if not text or len(text) < 50:
            return ""

        STOP_WORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "must", "ought",
            "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
            "us", "them", "my", "your", "his", "its", "our", "their", "mine",
            "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
            "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more", "most",
            "other", "some", "such", "no", "only", "same", "than", "too", "very",
            "just", "because", "as", "until", "while", "of", "at", "by", "for",
            "with", "about", "against", "between", "through", "during", "before",
            "after", "above", "below", "to", "from", "up", "down", "in", "out",
            "on", "off", "over", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "what", "which",
            "who", "whom", "if", "also", "like", "going", "know", "think",
            "really", "right", "get", "got", "go", "one", "two", "even",
            "well", "back", "much", "many", "still", "now", "way", "look",
            "make", "come", "see", "take", "want", "give", "use", "say", "said",
            "thing", "things", "people", "something", "lot", "actually", "kind",
        }

        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOP_WORDS]

        tf = Counter(words)
        total = len(words) if words else 1

        bigrams = []
        raw_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        for i in range(len(raw_words) - 1):
            w1, w2 = raw_words[i].lower(), raw_words[i + 1].lower()
            if w1 not in STOP_WORDS and w2 not in STOP_WORDS:
                bigrams.append(f"{w1} {w2}")
        bigram_counts = Counter(bigrams)

        scored = {}
        for word, count in tf.items():
            freq = count / total
            boost = 1 + math.log(count) if count > 1 else 1
            scored[word] = freq * boost

        for bigram, count in bigram_counts.items():
            if count >= 2:
                scored[bigram] = (count / total) * (1 + math.log(count)) * 2

        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        proper_counts = Counter(proper_nouns)
        for noun, count in proper_counts.items():
            if count >= 2 and len(noun) > 3:
                key = noun.lower()
                scored[key] = scored.get(key, 0) + (count / total) * 3

        doc_type_patterns = re.findall(
            r'\b(guest lecture|keynote|seminar|workshop|tutorial|transcript|presentation|interview)\b',
            text.lower(),
        )
        for phrase in doc_type_patterns:
            scored[phrase] = scored.get(phrase, 0) + 0.05

        top = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:100]
        return "; ".join(term for term, _ in top)

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
