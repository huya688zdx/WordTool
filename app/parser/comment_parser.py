from dataclasses import dataclass
from typing import List, Optional

from lxml import etree

from app.utils.xml_helpers import qn, get_text_content


@dataclass
class CommentInfo:
    comment_id: str
    author: str
    date: Optional[str]
    text: str
    paragraph_index: Optional[int] = None


class CommentParser:
    """Extract comments from DOCX XML."""

    def extract_comments(self, doc_element: etree._Element) -> List[CommentInfo]:
        """Extract all comments from the document."""
        comments = []

        # Comments are stored in word/comments.xml
        # We need to find comment references in the document body
        for comment_ref in doc_element.iter(qn("w:commentReference")):
            comment_id = comment_ref.get(qn("w:id"))
            if comment_id:
                comments.append(CommentInfo(
                    comment_id=comment_id,
                    author="",
                    date=None,
                    text="",
                ))

        return comments

    def get_comment_text(self, comments_element: etree._Element, comment_id: str) -> str:
        """Get the text content of a specific comment."""
        for comment in comments_element.findall(qn("w:comment")):
            if comment.get(qn("w:id")) == comment_id:
                return get_text_content(comment)
        return ""
