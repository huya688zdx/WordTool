from dataclasses import dataclass
from typing import Optional

from lxml import etree

from app.utils.xml_helpers import qn, find_child


# DOCX highlight color values (w:highlight w:val)
HIGHLIGHT_COLORS = {
    "yellow", "green", "cyan", "magenta", "blue", "red",
    "darkBlue", "darkCyan", "darkGreen", "darkMagenta",
    "darkRed", "darkYellow", "darkGray", "lightGray",
    "black", "white",
}


@dataclass
class HighlightInfo:
    color: str
    color_type: str  # 'highlight' or 'shading'
    hex_color: Optional[str] = None  # For shading


class HighlightParser:
    """Detect highlighted and shaded text in DOCX XML."""

    def detect_run_highlights(self, run_element: etree._Element) -> Optional[HighlightInfo]:
        """Check a run element for highlight or shading."""
        rpr = find_child(run_element, "w:rPr")
        if rpr is None:
            return None

        # Check w:highlight (16 preset colors)
        highlight = find_child(rpr, "w:highlight")
        if highlight is not None:
            val = highlight.get(qn("w:val"))
            if val and val != "none":
                return HighlightInfo(color=val, color_type="highlight")

        # Check w:shd (arbitrary hex colors)
        shd = find_child(rpr, "w:shd")
        if shd is not None:
            fill = shd.get(qn("w:fill"))
            if fill and fill != "auto" and fill != "000000":
                return HighlightInfo(
                    color=self._hex_to_name(fill),
                    color_type="shading",
                    hex_color=fill,
                )

        return None

    def is_paragraph_highlighted(self, para_element: etree._Element) -> bool:
        """Check if any run in the paragraph has highlighting."""
        # Check paragraph-level shading
        ppr = find_child(para_element, "w:pPr")
        if ppr is not None:
            pshd = find_child(ppr, "w:shd")
            if pshd is not None:
                fill = pshd.get(qn("w:fill"))
                if fill and fill != "auto" and fill != "000000":
                    return True

        # Check run-level highlights
        for run in para_element.iter(qn("w:r")):
            if self.detect_run_highlights(run) is not None:
                return True

        return False

    def _hex_to_name(self, hex_color: str) -> str:
        """Convert hex color to a readable name."""
        color_map = {
            "FFFF00": "yellow",
            "00FF00": "green",
            "00FFFF": "cyan",
            "FF00FF": "magenta",
            "0000FF": "blue",
            "FF0000": "red",
            "000080": "darkBlue",
            "008080": "darkCyan",
            "008000": "darkGreen",
            "800080": "darkMagenta",
            "800000": "darkRed",
            "808000": "darkYellow",
            "808080": "darkGray",
            "C0C0C0": "lightGray",
            "000000": "black",
            "FFFFFF": "white",
        }
        return color_map.get(hex_color.upper(), f"#{hex_color}")
