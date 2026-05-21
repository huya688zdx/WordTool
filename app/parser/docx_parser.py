from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from docx import Document
from lxml import etree

from app.utils.xml_helpers import qn, find_child, find_children, get_text_content

logger = logging.getLogger(__name__)


@dataclass
class RunData:
    text: str
    is_bold: bool = False
    is_italic: bool = False
    is_highlighted: bool = False
    highlight_color: Optional[str] = None
    shading_color: Optional[str] = None
    is_inserted: bool = False
    is_deleted_text: bool = False
    revision_author: Optional[str] = None


@dataclass
class ParagraphData:
    para_index: int
    full_text: str
    style_name: Optional[str] = None
    heading_level: Optional[int] = None
    runs: List[RunData] = field(default_factory=list)
    has_highlights: bool = False
    has_revisions: bool = False
    is_deleted: bool = False
    is_image: bool = False
    image_count: int = 0
    xml_raw: Optional[str] = None


@dataclass
class DocumentStructure:
    paragraphs: List[ParagraphData] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _detect_heading_level(ppr) -> int | None:
    """Detect heading level from paragraph properties.

    Checks outlineLvl first (most reliable), then pStyle name patterns
    including English 'HeadingN', Chinese '标题 N', and numbered variants.
    """
    if ppr is None:
        return None
    # 1. outlineLvl — the most reliable indicator (0 = Heading 1)
    outline = find_child(ppr, "w:outlineLvl")
    if outline is not None:
        try:
            return int(outline.get(qn("w:val"))) + 1
        except (ValueError, TypeError):
            pass
    # 2. pStyle name patterns
    pstyle = find_child(ppr, "w:pStyle")
    if pstyle is not None:
        name = pstyle.get(qn("w:val"), "")
        if not name:
            return None
        for prefix in ("Heading", "标题", "heading"):
            if name.startswith(prefix):
                suffix = name[len(prefix):].strip()
                try:
                    return int(suffix)
                except ValueError:
                    pass
    return None


class DocxParser:
    """Parse DOCX file into structured paragraph data using python-docx + lxml."""

    def parse(self, file_path: Path) -> DocumentStructure:
        """Parse a DOCX file and extract all paragraphs with their structure."""
        doc = Document(str(file_path))
        paragraphs = self._extract_paragraphs(doc)

        metadata = {
            "core_properties": {
                "author": doc.core_properties.author,
                "title": doc.core_properties.title,
                "created": str(doc.core_properties.created) if doc.core_properties.created else None,
                "modified": str(doc.core_properties.modified) if doc.core_properties.modified else None,
            }
        }

        return DocumentStructure(paragraphs=paragraphs, metadata=metadata)

    def _extract_paragraphs(self, doc: Document) -> List[ParagraphData]:
        """Walk the document body and extract only the final version paragraphs.

        Tracked changes (w:ins and w:del at body level) are handled:
        - w:ins: inserted paragraphs included as normal content
        - w:del: deleted paragraphs skipped entirely
        This ensures paragraph count matches the PDF (rendered in Final mode).
        """
        paragraphs = []
        para_index = 0

        body = doc.element.body
        for element in body:
            if element.tag == qn("w:p"):
                para_data = self._parse_paragraph(element, para_index)
                if para_data:
                    paragraphs.append(para_data)
                    para_index += 1
            elif element.tag == qn("w:tbl"):
                for cell_para in self._extract_table_paragraphs(element, para_index):
                    paragraphs.append(cell_para)
                    para_index += 1
            elif element.tag in (qn("w:drawing"), qn("w:pict")):
                para_data = self._parse_image_element(element, para_index)
                if para_data:
                    paragraphs.append(para_data)
                    para_index += 1
            elif element.tag == qn("w:ins"):
                # Inserted paragraphs (tracked changes) — include as normal
                for p in element.findall(qn("w:p")):
                    para_data = self._parse_paragraph(p, para_index)
                    if para_data:
                        paragraphs.append(para_data)
                        para_index += 1
            elif element.tag == qn("w:del"):
                # Deleted paragraphs (tracked changes) — skip entirely
                pass

        return paragraphs

    def _extract_table_paragraphs(self, table_element, start_index: int) -> List[ParagraphData]:
        """Extract paragraphs from table cells."""
        paragraphs = []
        index = start_index

        for tc in table_element.iter(qn("w:tc")):
            for p in tc.findall(qn("w:p")):
                para_data = self._parse_paragraph(p, index)
                if para_data:
                    paragraphs.append(para_data)
                    index += 1

        return paragraphs

    def _parse_paragraph(self, para_element: etree._Element, para_index: int) -> Optional[ParagraphData]:
        """Parse a single w:p element into ParagraphData."""
        runs = []
        full_text_parts = []
        has_highlights = False
        has_revisions = False
        is_deleted = False

        # Check if entire paragraph is deleted — skip it
        ppr = find_child(para_element, "w:pPr")
        if ppr is not None:
            rpr = find_child(ppr, "w:rPr")
            if rpr is not None and find_child(rpr, "w:del") is not None:
                # Entire paragraph deleted by tracked changes — exclude from output
                return None

        # Get style info
        style_name = None
        heading_level = None
        if ppr is not None:
            pstyle = find_child(ppr, "w:pStyle")
            if pstyle is not None:
                style_name = pstyle.get(qn("w:val"))
            heading_level = _detect_heading_level(ppr)

        # Parse child elements
        run_index = 0
        for child in para_element:
            if child.tag == qn("w:r"):
                run_data = self._parse_run(child)
                if run_data:
                    runs.append(run_data)
                    full_text_parts.append(run_data.text)
                    if run_data.is_highlighted:
                        has_highlights = True
                    run_index += 1

            elif child.tag == qn("w:ins"):
                # Inserted content (revision)
                has_revisions = True
                author = child.get(qn("w:author"), "")
                for r in child.findall(qn("w:r")):
                    run_data = self._parse_run(r, is_inserted=True, revision_author=author)
                    if run_data:
                        runs.append(run_data)
                        full_text_parts.append(run_data.text)
                        run_index += 1

            elif child.tag == qn("w:del"):
                # Deleted content (revision) — skip from full_text to show only latest version
                has_revisions = True
                is_deleted = True
                author = child.get(qn("w:author"), "")
                for r in child.findall(qn("w:r")):
                    run_data = self._parse_run(r, is_deleted=True, revision_author=author)
                    if run_data:
                        runs.append(run_data)
                        # Do NOT add deleted text to full_text_parts
                        if run_data.is_highlighted:
                            has_highlights = True
                        run_index += 1

            elif child.tag == qn("w:hyperlink"):
                for r in child.findall(qn("w:r")):
                    run_data = self._parse_run(r)
                    if run_data:
                        runs.append(run_data)
                        full_text_parts.append(run_data.text)
                        if run_data.is_highlighted:
                            has_highlights = True
                        run_index += 1

            elif child.tag in (qn("w:drawing"), qn("w:pict")):
                # Inline image within a paragraph
                inline_count = len(child.findall(".//" + qn("wp:inline")))
                if inline_count == 0:
                    inline_count = 1
                full_text_parts.append(f"[图片 x{inline_count}]")

        full_text = "".join(full_text_parts)

        # Don't skip paragraphs that contain images
        if not full_text.strip() and not runs:
            return None

        return ParagraphData(
            para_index=para_index,
            full_text=full_text,
            style_name=style_name,
            heading_level=heading_level,
            runs=runs,
            has_highlights=has_highlights,
            has_revisions=has_revisions,
            is_deleted=is_deleted,
            xml_raw=etree.tostring(para_element, encoding="unicode"),
        )

    def _parse_image_element(
        self, element: etree._Element, para_index: int
    ) -> Optional[ParagraphData]:
        """Parse a standalone image element (w:drawing or w:pict)."""
        image_count = len(element.findall(".//" + qn("wp:inline"))) + \
                      len(element.findall(".//" + qn("wp:anchor")))
        if image_count == 0:
            image_count = len(element.findall(".//" + qn("w:drawing")))
        if image_count == 0:
            image_count = 1  # Assume at least one image

        return ParagraphData(
            para_index=para_index,
            full_text=f"[图片 x{image_count}]",
            is_image=True,
            image_count=image_count,
            xml_raw=etree.tostring(element, encoding="unicode"),
        )

    def _parse_run(
        self,
        run_element: etree._Element,
        is_inserted: bool = False,
        is_deleted: bool = False,
        revision_author: Optional[str] = None,
    ) -> Optional[RunData]:
        """Parse a single w:r element into RunData."""
        # Get text content
        text = ""
        t_elem = find_child(run_element, "w:t")
        if t_elem is not None and t_elem.text:
            text = t_elem.text

        # Check for deleted text
        del_text_elem = find_child(run_element, "w:delText")
        if del_text_elem is not None and del_text_elem.text:
            text = del_text_elem.text
            is_deleted = True

        if not text:
            return None

        # Get formatting
        rpr = find_child(run_element, "w:rPr")
        is_bold = False
        is_italic = False
        is_highlighted = False
        highlight_color = None
        shading_color = None

        if rpr is not None:
            is_bold = find_child(rpr, "w:b") is not None
            is_italic = find_child(rpr, "w:i") is not None

            # Highlight detection (w:highlight)
            highlight_elem = find_child(rpr, "w:highlight")
            if highlight_elem is not None:
                val = highlight_elem.get(qn("w:val"))
                if val and val != "none":
                    is_highlighted = True
                    highlight_color = val

            # Shading detection (w:shd)
            shd_elem = find_child(rpr, "w:shd")
            if shd_elem is not None:
                fill = shd_elem.get(qn("w:fill"))
                if fill and fill != "auto" and fill != "000000":
                    is_highlighted = True
                    shading_color = fill

        return RunData(
            text=text,
            is_bold=is_bold,
            is_italic=is_italic,
            is_highlighted=is_highlighted,
            highlight_color=highlight_color,
            shading_color=shading_color,
            is_inserted=is_inserted,
            is_deleted_text=is_deleted,
            revision_author=revision_author,
        )
