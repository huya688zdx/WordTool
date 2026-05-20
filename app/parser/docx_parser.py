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
    xml_raw: Optional[str] = None


@dataclass
class DocumentStructure:
    paragraphs: List[ParagraphData] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


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
        """Walk the document body and extract all paragraphs."""
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
                # Extract paragraphs from table cells
                for cell_para in self._extract_table_paragraphs(element, para_index):
                    paragraphs.append(cell_para)
                    para_index += 1

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

        # Check if entire paragraph is deleted
        ppr = find_child(para_element, "w:pPr")
        if ppr is not None:
            rpr = find_child(ppr, "w:rPr")
            if rpr is not None and find_child(rpr, "w:del") is not None:
                is_deleted = True

        # Get style info
        style_name = None
        heading_level = None
        if ppr is not None:
            pstyle = find_child(ppr, "w:pStyle")
            if pstyle is not None:
                style_name = pstyle.get(qn("w:val"))
                if style_name and style_name.startswith("Heading"):
                    try:
                        heading_level = int(style_name.replace("Heading", ""))
                    except ValueError:
                        pass

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
                # Deleted content (revision)
                has_revisions = True
                is_deleted = True
                author = child.get(qn("w:author"), "")
                for r in child.findall(qn("w:r")):
                    run_data = self._parse_run(r, is_deleted=True, revision_author=author)
                    if run_data:
                        runs.append(run_data)
                        full_text_parts.append(run_data.text)
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

        full_text = "".join(full_text_parts)

        # Skip empty paragraphs
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
