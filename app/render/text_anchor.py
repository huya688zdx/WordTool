import logging
from typing import List, Tuple, Optional

import fitz  # PyMuPDF

from app.layout.page_model import (
    PageData, WordInfo, CoordinateMapping
)
from app.parser.docx_parser import ParagraphData
from app.render.pdf_parser import PDFParser
from app.utils.text_normalize import normalize_for_matching, extract_search_tokens
from app.config.settings import settings

logger = logging.getLogger(__name__)


class TextAnchorMapper:
    """Map paragraph text from DOCX XML to PDF page coordinates.

    Uses a 3-strategy cascade:
    1. Full text search (fast, high confidence)
    2. Chunked sequential search (medium, handles long text)
    3. Word sequence fuzzy match (slow, fallback)
    """

    def __init__(
        self,
        min_confidence: Optional[float] = None,
        chunk_size: Optional[int] = None,
    ):
        self._min_confidence = min_confidence or settings.TEXT_ANCHOR_MIN_CONFIDENCE
        self._chunk_size = chunk_size or settings.TEXT_ANCHOR_CHUNK_SIZE
        self._pdf_parser = PDFParser()
        self._cursor_page = 0  # For disambiguation
        self._cursor_y = 0.0

    def map_paragraphs(
        self,
        paragraphs: List[ParagraphData],
        pdf_path: str,
    ) -> List[CoordinateMapping]:
        """Map all paragraphs to PDF coordinates.

        Args:
            paragraphs: List of parsed paragraph data from DOCX
            pdf_path: Path to the rendered PDF file

        Returns:
            List of coordinate mappings
        """
        mappings = []
        doc = fitz.open(pdf_path)

        try:
            # Pre-load all page words for Strategy 3
            page_words = {}
            for page_index in range(len(doc)):
                page = doc[page_index]
                page_words[page_index + 1] = self._pdf_parser.get_page_words(page)

            # Reset cursor
            self._cursor_page = 1
            self._cursor_y = 0.0

            for para in paragraphs:
                if not para.full_text.strip():
                    continue

                mapping = self._map_single_paragraph(para, doc, page_words)
                if mapping:
                    mappings.append(mapping)
                    # Update cursor for disambiguation
                    self._cursor_page = mapping.page_number
                    self._cursor_y = mapping.bbox[3]  # bottom y

        finally:
            doc.close()

        return mappings

    def _map_single_paragraph(
        self,
        para: ParagraphData,
        doc: fitz.Document,
        page_words: dict,
    ) -> Optional[CoordinateMapping]:
        """Map a single paragraph using the 3-strategy cascade."""
        normalized_text = normalize_for_matching(para.full_text)

        if not normalized_text:
            return None

        # Strategy 1: Full text search
        mapping = self._strategy_full_text(para, normalized_text, doc)
        if mapping:
            logger.debug(f"Para {para.para_index}: matched via full_text")
            return mapping

        # Strategy 2: Chunked sequential search
        mapping = self._strategy_chunked(para, normalized_text, doc)
        if mapping:
            logger.debug(f"Para {para.para_index}: matched via chunked")
            return mapping

        # Strategy 3: Word sequence fuzzy match
        mapping = self._strategy_word_sequence(para, normalized_text, doc, page_words)
        if mapping:
            logger.debug(f"Para {para.para_index}: matched via word_sequence")
            return mapping

        logger.warning(f"Para {para.para_index}: no match found for '{para.full_text[:50]}...'")
        return None

    def _strategy_full_text(
        self,
        para: ParagraphData,
        normalized_text: str,
        doc: fitz.Document,
    ) -> Optional[CoordinateMapping]:
        """Strategy 1: Search for full paragraph text on each page."""
        # Only try for shorter paragraphs
        if len(normalized_text) > 200:
            return None

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_num = page_index + 1

            # Skip pages before cursor (disambiguation)
            if page_num < self._cursor_page:
                continue

            rects = page.search_for(normalized_text)
            if rects:
                # Filter by cursor position on same page
                valid_rects = []
                for rect in rects:
                    if page_num == self._cursor_page and rect.y0 < self._cursor_y:
                        continue
                    valid_rects.append(rect)

                if valid_rects:
                    bbox = self._merge_rects(valid_rects)
                    return CoordinateMapping(
                        paragraph_id=para.para_index,
                        page_number=page_num,
                        bbox=(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                        confidence=1.0,
                        strategy="full_text",
                    )

        return None

    def _strategy_chunked(
        self,
        para: ParagraphData,
        normalized_text: str,
        doc: fitz.Document,
    ) -> Optional[CoordinateMapping]:
        """Strategy 2: Split text into chunks and search sequentially."""
        from app.utils.text_normalize import chunk_text

        chunks = chunk_text(normalized_text, self._chunk_size)
        if not chunks:
            return None

        best_page = None
        best_rects = []
        matched_chunks = 0
        total_chunks = len(chunks)

        # Start searching from cursor page
        for page_index in range(self._cursor_page - 1, len(doc)):
            page = doc[page_index]
            page_num = page_index + 1

            page_rects = []
            page_matched = 0

            for chunk in chunks:
                if not chunk.strip():
                    continue

                rects = page.search_for(chunk)
                if rects:
                    page_rects.extend(rects)
                    page_matched += 1

            if page_matched > matched_chunks:
                matched_chunks = page_matched
                best_page = page_num
                best_rects = page_rects

            # If we found all chunks on this page, stop
            if page_matched == total_chunks:
                break

        if best_page and matched_chunks > 0:
            confidence = matched_chunks / total_chunks
            if confidence >= self._min_confidence:
                bbox = self._merge_rects(best_rects)
                return CoordinateMapping(
                    paragraph_id=para.para_index,
                    page_number=best_page,
                    bbox=(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                    confidence=confidence,
                    strategy="chunked",
                )

        return None

    def _strategy_word_sequence(
        self,
        para: ParagraphData,
        normalized_text: str,
        doc: fitz.Document,
        page_words: dict,
    ) -> Optional[CoordinateMapping]:
        """Strategy 3: Fuzzy match using word sequence."""
        import difflib

        para_tokens = extract_search_tokens(normalized_text, min_length=2)
        if len(para_tokens) < 3:
            return None

        # Use first N tokens as anchor
        anchor_size = min(10, len(para_tokens))
        anchor_tokens = para_tokens[:anchor_size]

        best_ratio = 0.0
        best_page = None
        best_rect = None

        for page_index in range(self._cursor_page - 1, len(doc)):
            page_num = page_index + 1
            words = page_words.get(page_num, [])

            if len(words) < anchor_size:
                continue

            # Sliding window match
            page_tokens = [w.text.lower() for w in words]

            for i in range(len(page_tokens) - anchor_size + 1):
                window = page_tokens[i:i + anchor_size]
                ratio = difflib.SequenceMatcher(
                    None, [t.lower() for t in anchor_tokens], window
                ).ratio()

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_page = page_num
                    # Compute bbox from matching words
                    matched_words = words[i:i + anchor_size]
                    best_rect = self._words_to_rect(matched_words)

        if best_page and best_ratio >= 0.7:
            # Apply cursor filtering
            if best_page == self._cursor_page and best_rect:
                if best_rect.y0 < self._cursor_y:
                    return None

            return CoordinateMapping(
                paragraph_id=para.para_index,
                page_number=best_page,
                bbox=(best_rect.x0, best_rect.y0, best_rect.x1, best_rect.y1),
                confidence=best_ratio,
                strategy="word_sequence",
            )

        return None

    def _merge_rects(self, rects: List[fitz.Rect]) -> fitz.Rect:
        """Merge multiple Rect objects into their union bounding box."""
        if not rects:
            return fitz.Rect(0, 0, 0, 0)

        result = rects[0]
        for rect in rects[1:]:
            result = result | rect  # Union operator
        return result

    def _words_to_rect(self, words: List[WordInfo]) -> fitz.Rect:
        """Convert a list of WordInfo to a bounding rect."""
        if not words:
            return fitz.Rect(0, 0, 0, 0)

        x0 = min(w.bbox[0] for w in words)
        y0 = min(w.bbox[1] for w in words)
        x1 = max(w.bbox[2] for w in words)
        y1 = max(w.bbox[3] for w in words)

        return fitz.Rect(x0, y0, x1, y1)


def map_paragraphs_to_pdf(
    paragraphs: List[ParagraphData],
    pdf_path: str,
) -> List[CoordinateMapping]:
    """Convenience function to map paragraphs to PDF coordinates."""
    mapper = TextAnchorMapper()
    return mapper.map_paragraphs(paragraphs, pdf_path)
