from dataclasses import dataclass
from typing import Optional

from lxml import etree

from app.utils.xml_helpers import qn, find_child


@dataclass
class StyleInfo:
    style_id: str
    name: str
    style_type: str  # 'paragraph', 'character', 'table'
    heading_level: Optional[int] = None
    is_list: bool = False


class StyleAnalyzer:
    """Analyze document styles and heading levels."""

    def get_heading_level(self, para_element: etree._Element) -> Optional[int]:
        """Get the heading level for a paragraph."""
        ppr = find_child(para_element, "w:pPr")
        if ppr is None:
            return None

        pstyle = find_child(ppr, "w:pStyle")
        if pstyle is None:
            return None

        style_name = pstyle.get(qn("w:val"), "")
        if style_name.startswith("Heading"):
            try:
                return int(style_name.replace("Heading", ""))
            except ValueError:
                pass

        return None

    def get_style_name(self, para_element: etree._Element) -> Optional[str]:
        """Get the style name for a paragraph."""
        ppr = find_child(para_element, "w:pPr")
        if ppr is None:
            return None

        pstyle = find_child(ppr, "w:pStyle")
        if pstyle is None:
            return None

        return pstyle.get(qn("w:val"))

    def is_list_paragraph(self, para_element: etree._Element) -> bool:
        """Check if paragraph is a list item."""
        ppr = find_child(para_element, "w:pPr")
        if ppr is None:
            return False

        num_pr = find_child(ppr, "w:numPr")
        return num_pr is not None
