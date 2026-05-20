import logging
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF

from app.layout.page_model import (
    PageData, TextBlock, TextLine, TextSpan, WordInfo
)

logger = logging.getLogger(__name__)


class PDFParser:
    """Extract text and coordinates from PDF using PyMuPDF."""

    def parse_document(self, pdf_path: Path) -> List[PageData]:
        """Parse entire PDF, return per-page structured data."""
        pages = []
        doc = fitz.open(str(pdf_path))

        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                page_data = self._parse_page(page, page_index + 1)
                pages.append(page_data)
        finally:
            doc.close()

        return pages

    def _parse_page(self, page: fitz.Page, page_number: int) -> PageData:
        """Parse a single page into PageData."""
        rect = page.rect
        page_data = PageData(
            page_number=page_number,
            width=rect.width,
            height=rect.height,
        )

        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip image blocks
                continue

            block_bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
            text_block = TextBlock(bbox=block_bbox)

            for line in block.get("lines", []):
                line_bbox = tuple(line.get("bbox", (0, 0, 0, 0)))
                text_line = TextLine(bbox=line_bbox)

                for span in line.get("spans", []):
                    span_bbox = tuple(span.get("bbox", (0, 0, 0, 0)))
                    text_span = TextSpan(
                        text=span.get("text", ""),
                        bbox=span_bbox,
                        font=span.get("font", ""),
                        size=span.get("size", 0.0),
                        color=span.get("color", 0),
                    )
                    text_line.spans.append(text_span)

                text_block.lines.append(text_line)

            page_data.blocks.append(text_block)

        return page_data

    def get_page_words(self, page: fitz.Page) -> List[WordInfo]:
        """Extract individual words with coordinates.

        Uses page.get_text('words') which returns tuples:
        (x0, y0, x1, y1, text, block_no, line_no, word_no)
        """
        words = []
        raw_words = page.get_text("words")

        for w in raw_words:
            if len(w) >= 8:
                words.append(WordInfo(
                    bbox=(w[0], w[1], w[2], w[3]),
                    text=w[4],
                    block_no=w[5],
                    line_no=w[6],
                    word_no=w[7],
                ))

        return words

    def search_text(self, page: fitz.Page, text: str) -> List[fitz.Rect]:
        """Search for exact text on page using page.search_for()."""
        return page.search_for(text)

    def get_full_page_text(self, page: fitz.Page) -> str:
        """Get plain text for entire page."""
        return page.get_text("text")


def parse_pdf(pdf_path: Path) -> List[PageData]:
    """Convenience function to parse a PDF file."""
    parser = PDFParser()
    return parser.parse_document(pdf_path)
