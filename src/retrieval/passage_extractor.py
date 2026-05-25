"""Phase 2 passage extractor: uses L1 to locate sections, extracts relevant passages from L0."""

import re
from dataclasses import dataclass


@dataclass
class Passage:
    text: str
    section: str
    relevance_score: float


def extract_passages(
    query: str,
    level_0: str,
    level_1: str,
    max_passages: int = 3,
    passage_window: int = 600,
) -> list[Passage]:
    """Extract relevant passages from L0 using L1 sections as a guide.

    1. Parse L1 into section headings
    2. Score each section against the query
    3. Extract text windows around the best-matching sections from L0
    """
    if not level_0:
        return []

    query_terms = _extract_query_terms(query)

    sections = _parse_sections(level_0, level_1)

    if not sections:
        return _fallback_extract(query_terms, level_0, max_passages, passage_window)

    scored = []
    for section in sections:
        score = _score_section(query_terms, section["heading"], section["text"])
        scored.append((score, section))

    scored.sort(key=lambda x: x[0], reverse=True)

    passages = []
    seen_ranges = []
    for score, section in scored[:max_passages * 2]:
        if score <= 0:
            break
        text = section["text"].strip()
        if not text:
            continue

        start = section.get("start_pos", 0)
        if _overlaps(start, start + len(text), seen_ranges):
            continue

        trimmed = _trim_passage(text, query_terms, passage_window)
        if len(trimmed.strip()) < 30:
            continue

        passages.append(Passage(
            text=trimmed,
            section=section["heading"],
            relevance_score=score,
        ))
        seen_ranges.append((start, start + len(text)))

        if len(passages) >= max_passages:
            break

    if not passages:
        return _fallback_extract(query_terms, level_0, max_passages, passage_window)

    return passages


def _extract_query_terms(query: str) -> list[str]:
    """Extract meaningful terms from the query."""
    stop = {
        "what", "are", "the", "is", "how", "does", "do", "can", "which",
        "where", "when", "why", "who", "in", "of", "a", "an", "and", "or",
        "to", "for", "on", "at", "by", "from", "with", "about", "between",
    }
    words = re.findall(r'\b\w+\b', query.lower())
    terms = [w for w in words if w not in stop and len(w) > 2]

    bigrams = []
    for i in range(len(words) - 1):
        if words[i] not in stop and words[i + 1] not in stop:
            bigrams.append(f"{words[i]} {words[i+1]}")

    return bigrams + terms


def _parse_sections(level_0: str, level_1: str) -> list[dict]:
    """Parse L0 into sections using heading patterns or L1 outline."""
    heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
    headings = list(heading_pattern.finditer(level_0))

    if headings:
        sections = []
        for i, match in enumerate(headings):
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(level_0)
            sections.append({
                "heading": match.group(2).strip(),
                "text": level_0[start:end],
                "start_pos": start,
            })
        return sections

    timestamp_pattern = re.compile(r'\*\*\[[\d:]+\]\*\*\s*(.*?)(?=\*\*\[|\Z)', re.DOTALL)
    timestamps = list(timestamp_pattern.finditer(level_0))
    if timestamps:
        sections = []
        for match in timestamps:
            text = match.group(1).strip()
            if len(text) > 50:
                first_line = text.split('\n')[0][:80]
                sections.append({
                    "heading": first_line,
                    "text": text,
                    "start_pos": match.start(),
                })
        return sections

    paragraphs = re.split(r'\n{2,}', level_0)
    if len(paragraphs) > 3:
        sections = []
        pos = 0
        for para in paragraphs:
            if len(para.strip()) > 50:
                first_sentence = re.split(r'[.!?]\s', para)[0][:80]
                sections.append({
                    "heading": first_sentence,
                    "text": para,
                    "start_pos": pos,
                })
            pos += len(para) + 2
        return sections

    return []


def _score_section(query_terms: list[str], heading: str, text: str) -> float:
    """Score a section's relevance to query terms."""
    score = 0.0
    heading_lower = heading.lower()
    text_lower = text.lower()

    for term in query_terms:
        if term in heading_lower:
            score += 3.0
        term_count = text_lower.count(term)
        if term_count > 0:
            score += min(term_count * 0.5, 5.0)

    if len(text) > 100:
        density = sum(text_lower.count(t) for t in query_terms) / (len(text) / 100)
        score += density * 0.5

    return score


def _trim_passage(text: str, query_terms: list[str], max_chars: int) -> str:
    """Trim a passage to max_chars, centered around the most relevant part."""
    if len(text) <= max_chars:
        return text

    text_lower = text.lower()
    best_pos = 0
    best_density = 0

    window = max_chars // 2
    for i in range(0, len(text) - window, window // 4):
        chunk = text_lower[i:i + window]
        density = sum(chunk.count(t) for t in query_terms)
        if density > best_density:
            best_density = density
            best_pos = i

    start = max(0, best_pos - max_chars // 4)
    end = min(len(text), start + max_chars)

    passage = text[start:end]

    if start > 0:
        first_break = passage.find('\n')
        if first_break > 0 and first_break < 100:
            passage = passage[first_break + 1:]
        else:
            passage = "..." + passage

    if end < len(text):
        last_break = passage.rfind('\n')
        if last_break > len(passage) - 100:
            passage = passage[:last_break]
        else:
            passage = passage + "..."

    return passage


def _fallback_extract(
    query_terms: list[str],
    text: str,
    max_passages: int,
    window: int,
) -> list[Passage]:
    """Fallback: scan L0 for paragraphs with highest query term density."""
    paragraphs = re.split(r'\n{2,}', text)
    scored = []

    for para in paragraphs:
        if len(para.strip()) < 40:
            continue
        para_lower = para.lower()
        density = sum(para_lower.count(t) for t in query_terms)
        if density > 0:
            scored.append((density, para))

    scored.sort(key=lambda x: x[0], reverse=True)

    passages = []
    for density, para in scored[:max_passages]:
        trimmed = para[:window] if len(para) > window else para
        passages.append(Passage(
            text=trimmed,
            section="(matched paragraph)",
            relevance_score=density,
        ))

    return passages


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for s, e in ranges:
        if start < e and end > s:
            return True
    return False
