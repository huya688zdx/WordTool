from dataclasses import dataclass
from typing import List, Optional

from lxml import etree

from app.utils.xml_helpers import qn, find_child, find_children, get_text_content


@dataclass
class RevisionInfo:
    revision_type: str  # 'insert', 'delete', 'format_change'
    author: str
    date: Optional[str]
    text: str
    element_id: Optional[str] = None


class RevisionParser:
    """Parse track changes (revisions) in DOCX XML."""

    def parse_paragraph_revisions(self, para_element: etree._Element) -> List[RevisionInfo]:
        """Extract all revision marks from a paragraph."""
        revisions = []

        # Check for paragraph property changes
        ppr = find_child(para_element, "w:pPr")
        if ppr is not None:
            ppr_change = find_child(ppr, "w:pPrChange")
            if ppr_change is not None:
                revisions.append(RevisionInfo(
                    revision_type="format_change",
                    author=ppr_change.get(qn("w:author"), ""),
                    date=ppr_change.get(qn("w:date")),
                    text="[paragraph format changed]",
                    element_id=ppr_change.get(qn("w:id")),
                ))

        # Process child elements
        for child in para_element:
            if child.tag == qn("w:ins"):
                author = child.get(qn("w:author"), "")
                date = child.get(qn("w:date"))
                elem_id = child.get(qn("w:id"))
                text = get_text_content(child)
                if text:
                    revisions.append(RevisionInfo(
                        revision_type="insert",
                        author=author,
                        date=date,
                        text=text,
                        element_id=elem_id,
                    ))

            elif child.tag == qn("w:del"):
                author = child.get(qn("w:author"), "")
                date = child.get(qn("w:date"))
                elem_id = child.get(qn("w:id"))
                text = get_text_content(child)
                if text:
                    revisions.append(RevisionInfo(
                        revision_type="delete",
                        author=author,
                        date=date,
                        text=text,
                        element_id=elem_id,
                    ))

            elif child.tag == qn("w:r"):
                rpr = find_child(child, "w:rPr")
                if rpr is not None:
                    rpr_change = find_child(rpr, "w:rPrChange")
                    if rpr_change is not None:
                        revisions.append(RevisionInfo(
                            revision_type="format_change",
                            author=rpr_change.get(qn("w:author"), ""),
                            date=rpr_change.get(qn("w:date")),
                            text="[run format changed]",
                            element_id=rpr_change.get(qn("w:id")),
                        ))

        return revisions

    def get_inserted_text(self, para_element: etree._Element) -> str:
        """Get only the text that was inserted."""
        parts = []
        for ins in para_element.findall(qn("w:ins")):
            parts.append(get_text_content(ins))
        return "".join(parts)

    def get_deleted_text(self, para_element: etree._Element) -> str:
        """Get only the text that was deleted."""
        parts = []
        for del_elem in para_element.findall(qn("w:del")):
            parts.append(get_text_content(del_elem))
        return "".join(parts)
