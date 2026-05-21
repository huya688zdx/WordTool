import logging
import re
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

    Uses a 4-strategy cascade:
    0. BBox sequential mapping (for garbled/non-searchable text like CJK)
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
        self._cursor_page = 0
        self._cursor_y = 0.0

    def map_paragraphs(
        self,
        paragraphs: List[ParagraphData],
        pdf_path: str,
    ) -> List[CoordinateMapping]:
        mappings = []
        doc = fitz.open(pdf_path)

        try:
            # Check if PDF text is searchable/garbled
            is_garbled = self._detect_garbled_text(doc)

            page_words = {}
            for page_index in range(len(doc)):
                page = doc[page_index]
                page_words[page_index + 1] = self._pdf_parser.get_page_words(page)

            self._cursor_page = 1
            self._cursor_y = 0.0

            # Step 1: Try text search first (skip if PDF text is garbled)
            text_mappings = {}
            if not is_garbled:
                for para in paragraphs:
                    if not para.full_text.strip():
                        continue
                    mapping = self._map_single_paragraph(para, doc, page_words)
                    if mapping:
                        text_mappings[para.para_index] = mapping
                        self._cursor_page = mapping.page_number
                        self._cursor_y = mapping.bbox[3]

            # Step 2: Fill unmapped paragraphs with position-based estimation
            position_mappings = self._strategy_position_based(paragraphs, doc)
            for pm in position_mappings:
                if pm.paragraph_id not in text_mappings:
                    text_mappings[pm.paragraph_id] = pm

            mappings = list(text_mappings.values())

        finally:
            doc.close()

        return mappings

    def _detect_garbled_text(self, doc: fitz.Document) -> bool:
        """Check if PDF text extraction produces garbled characters."""
        if len(doc) == 0:
            return False
        page = doc[0]
        text = page.get_text("text")
        # Count replacement characters vs total chars
        if not text.strip():
            return False
        garbled_count = text.count("�")
        total_chars = len(text.strip())
        ratio = garbled_count / max(total_chars, 1)
        return ratio > 0.1  # More than 10% garbled

    def _strategy_position_based(
        self,
        paragraphs: List[ParagraphData],
        doc: fitz.Document,
    ) -> List[CoordinateMapping]:
        """Strategy 0: Map paragraphs to PDF blocks by sequential position.

        Uses adaptive gap clustering per page: computes the median vertical gap
        between consecutive blocks, then merges blocks whose gap is less than
        2× the median. This correctly groups lines belonging to the same paragraph
        while treating large gaps as paragraph boundaries.

        The algorithm:
          1. Collect text blocks, filter out header/footer zones
          2. Per page: compute gaps → median → merge threshold = max(2×median, 12pt)
          3. Merge blocks with gap < threshold (same paragraph)
          4. Flatten clusters across pages, map 1:1 to paragraphs
        """
        valid_paras = [p for p in paragraphs if p.full_text.strip() or p.is_image]
        if not valid_paras:
            return []

        # 1. Collect blocks per page, filter headers/footers
        first_page = doc[0]
        page_h = first_page.rect.height
        header_margin = page_h * 0.08
        footer_margin = page_h * 0.92

        pages_blocks = {}  # page_num -> [(x0, y0, x1, y1, type)]
        for page_index in range(len(doc)):
            page = doc[page_index]
            text_dict = page.get_text("dict")
            page_list = []
            for block in text_dict.get("blocks", []):
                bbox = block.get("bbox", (0, 0, 0, 0))
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w < 20 or h < 6:
                    continue
                if bbox[3] < header_margin:   # header
                    continue
                if bbox[1] > footer_margin:   # footer
                    continue
                page_list.append((
                    bbox[0], bbox[1], bbox[2], bbox[3],
                    "image" if block.get("type") == 1 else "text"
                ))
            page_list.sort(key=lambda b: (b[1], b[0]))
            pages_blocks[page_index + 1] = page_list

        # 2. Per-page adaptive gap clustering
        for page_num in pages_blocks:
            blocks = pages_blocks[page_num]
            if len(blocks) < 2:
                continue

            # Compute gaps between consecutive blocks (by their top edges)
            gaps = []
            for i in range(len(blocks) - 1):
                g = blocks[i + 1][1] - blocks[i][3]  # next.y0 - current.y1
                if g > 0:
                    gaps.append(g)

            if not gaps:
                continue

            # Median gap as baseline line spacing
            gaps_sorted = sorted(gaps)
            median_gap = gaps_sorted[len(gaps_sorted) // 2]
            # Merge threshold: 2× median, but at least 12pt (covers dense CJK)
            merge_threshold = max(median_gap * 2.0, 12.0)

            # Merge blocks within same paragraph
            i = 0
            while i < len(blocks):
                j = i + 1
                while j < len(blocks):
                    gap = blocks[j][1] - blocks[i][3]
                    if gap < merge_threshold:
                        # Merge blocks[j] into blocks[i]
                        blocks[i] = (
                            min(blocks[i][0], blocks[j][0]),
                            blocks[i][1],
                            max(blocks[i][2], blocks[j][2]),
                            blocks[j][3],
                            blocks[i][4],
                        )
                        blocks.pop(j)
                    else:
                        break
                i += 1

        # 3. Build ordered per-page cluster lists
        page_clusters = {}  # page_num -> [(x0, y0, x1, y1, type)]
        for page_num in sorted(pages_blocks.keys()):
            page_clusters[page_num] = list(pages_blocks[page_num])

        total_clusters = sum(len(v) for v in page_clusters.values())
        if total_clusters == 0:
            return []

        total_paras = len(valid_paras)

        # 4. Distribute paragraphs across pages proportionally
        # Each page gets paragraphs in proportion to its share of text clusters.
        # This prevents cross-page drift: errors on one page don't affect others.
        page_para_counts = {}
        assigned = 0
        page_nums = sorted(page_clusters.keys())
        for idx, pn in enumerate(page_nums):
            if idx == len(page_nums) - 1:
                # Last page gets all remaining paragraphs
                page_para_counts[pn] = total_paras - assigned
            else:
                ratio = len(page_clusters[pn]) / total_clusters
                count = max(1, round(total_paras * ratio))
                page_para_counts[pn] = min(count, total_paras - assigned)
            assigned += page_para_counts[pn]
            if assigned >= total_paras:
                # Assign zero to remaining pages
                for later_pn in page_nums[idx + 1:]:
                    page_para_counts[later_pn] = 0
                break

        # 5. Map paragraphs to clusters per page
        mappings = []
        para_idx = 0
        for page_num in page_nums:
            clusters = page_clusters[page_num]
            n_paras = page_para_counts.get(page_num, 0)
            for c_idx in range(min(n_paras, len(clusters))):
                if para_idx >= total_paras:
                    break
                para = valid_paras[para_idx]
                x0, y0, x1, y1, btype = clusters[c_idx]
                strategy = "image_block" if btype == "image" else "position_based"
                mappings.append(CoordinateMapping(
                    paragraph_id=para.para_index,
                    page_number=page_num,
                    bbox=(x0, y0, x1, y1),
                    confidence=0.5,
                    strategy=strategy,
                ))
                para_idx += 1

        return mappings

    def _map_single_paragraph(
        self,
        para: ParagraphData,
        doc: fitz.Document,
        page_words: dict,
    ) -> Optional[CoordinateMapping]:
        normalized_text = normalize_for_matching(para.full_text)
        if not normalized_text:
            return None

        mapping = self._strategy_full_text(para, normalized_text, doc)
        if mapping:
            logger.debug(f"Para {para.para_index}: full_text")
            return mapping

        mapping = self._strategy_chunked(para, normalized_text, doc)
        if mapping:
            logger.debug(f"Para {para.para_index}: chunked")
            return mapping

        mapping = self._strategy_word_sequence(para, normalized_text, doc, page_words)
        if mapping:
            logger.debug(f"Para {para.para_index}: word_sequence")
            return mapping

        logger.warning(f"Para {para.para_index}: no match for '{para.full_text[:50]}...'")
        return None

    def _strategy_full_text(
        self,
        para: ParagraphData,
        normalized_text: str,
        doc: fitz.Document,
    ) -> Optional[CoordinateMapping]:
        if len(normalized_text) > 200:
            return None

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_num = page_index + 1

            if page_num < self._cursor_page:
                continue

            rects = page.search_for(normalized_text)
            if rects:
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
        from app.utils.text_normalize import chunk_text

        chunks = chunk_text(normalized_text, self._chunk_size)
        if not chunks:
            return None

        best_page = None
        best_rects = []
        matched_chunks = 0
        total_chunks = len(chunks)

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
                    # Filter rects below cursor on the current page
                    valid = []
                    for r in rects:
                        if page_num == self._cursor_page and r.y0 < self._cursor_y:
                            continue
                        valid.append(r)
                    if valid:
                        page_rects.extend(valid)
                        page_matched += 1

            if page_matched > matched_chunks:
                matched_chunks = page_matched
                best_page = page_num
                best_rects = page_rects

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
        import difflib

        para_tokens = extract_search_tokens(normalized_text, min_length=2)
        if len(para_tokens) < 3:
            return None

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

            page_tokens = [w.text.lower() for w in words]
            for i in range(len(page_tokens) - anchor_size + 1):
                window = page_tokens[i:i + anchor_size]
                ratio = difflib.SequenceMatcher(
                    None, [t.lower() for t in anchor_tokens], window
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_page = page_num
                    matched_words = words[i:i + anchor_size]
                    best_rect = self._words_to_rect(matched_words)

        if best_page and best_ratio >= 0.7:
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
        if not rects:
            return fitz.Rect(0, 0, 0, 0)
        result = rects[0]
        for rect in rects[1:]:
            result = result | rect
        return result

    def _words_to_rect(self, words: List[WordInfo]) -> fitz.Rect:
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
    mapper = TextAnchorMapper()
    return mapper.map_paragraphs(paragraphs, pdf_path)
