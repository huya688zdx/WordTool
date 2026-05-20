from typing import List, Optional

from lxml import etree

# WordprocessingML namespaces
NSMAP = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
}

W_NS = NSMAP["w"]


def qn(tag: str) -> str:
    """Convert 'w:p' to '{http://...}p'."""
    prefix, local = tag.split(":")
    return f"{{{NSMAP[prefix]}}}{local}"


def find_child(element: etree._Element, tag: str) -> Optional[etree._Element]:
    """Find direct child by qualified tag name."""
    return element.find(qn(tag))


def find_children(element: etree._Element, tag: str) -> List[etree._Element]:
    """Find all direct children by qualified tag name."""
    return element.findall(qn(tag))


def get_text_content(element: etree._Element) -> str:
    """Extract all w:t and w:delText text from an element recursively."""
    parts = []
    for t_elem in element.iter(qn("w:t")):
        if t_elem.text:
            parts.append(t_elem.text)
    for dt_elem in element.iter(qn("w:delText")):
        if dt_elem.text:
            parts.append(dt_elem.text)
    return "".join(parts)
