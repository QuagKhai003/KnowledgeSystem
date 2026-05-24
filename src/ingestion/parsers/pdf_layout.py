from pathlib import Path

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def parse_pdf(file_path: str) -> dict:
    """Extract structural layout from a PDF file."""
    if not HAS_PYMUPDF:
        return {
            "parser_source": "pdf_pymupdf",
            "file_path": file_path,
            "error": "PyMuPDF not installed",
            "pages": [],
            "headings": [],
            "outline": [],
        }

    doc = fitz.open(file_path)

    outline = _extract_outline(doc)
    pages = _extract_pages(doc)
    headings = _detect_headings(pages)

    doc.close()

    return {
        "parser_source": "pdf_pymupdf",
        "file_path": file_path,
        "page_count": len(pages),
        "outline": outline,
        "headings": headings,
        "pages": pages,
    }


def _extract_outline(doc) -> list[dict]:
    """Extract the PDF table of contents / bookmarks."""
    toc = doc.get_toc()
    return [
        {"level": level, "title": title, "page": page}
        for level, title, page in toc
    ]


def _extract_pages(doc) -> list[dict]:
    """Extract text blocks per page with bounding box metadata."""
    pages = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        text_blocks = []

        for block in blocks:
            if block.get("type") != 0:  # text blocks only
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if not text.strip():
                    continue
                text_blocks.append({
                    "text": text,
                    "bbox": block["bbox"],
                    "font_size": spans[0]["size"],
                    "font_name": spans[0]["font"],
                })

        page_text = "\n".join(b["text"] for b in text_blocks)
        pages.append({
            "page": page_num + 1,
            "text": page_text,
            "blocks": text_blocks,
        })

    return pages


def _detect_headings(pages: list[dict]) -> list[dict]:
    """Identify headings by font size relative to body text."""
    all_sizes = []
    for page in pages:
        for block in page["blocks"]:
            all_sizes.append(block["font_size"])

    if not all_sizes:
        return []

    # Body text is the most common font size
    size_counts: dict[float, int] = {}
    for s in all_sizes:
        size_counts[s] = size_counts.get(s, 0) + 1
    body_size = max(size_counts, key=size_counts.get)

    headings = []
    for page in pages:
        for block in page["blocks"]:
            if block["font_size"] > body_size * 1.15:
                headings.append({
                    "text": block["text"].strip(),
                    "page": page["page"],
                    "font_size": block["font_size"],
                })

    return headings
