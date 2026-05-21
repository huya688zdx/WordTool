from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class TextSpan:
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font: str = ""
    size: float = 0.0
    color: int = 0


@dataclass
class TextLine:
    bbox: Tuple[float, float, float, float]
    spans: List[TextSpan] = field(default_factory=list)


@dataclass
class TextBlock:
    bbox: Tuple[float, float, float, float]
    lines: List[TextLine] = field(default_factory=list)


@dataclass
class PageData:
    page_number: int  # 1-based
    width: float
    height: float
    blocks: List[TextBlock] = field(default_factory=list)


@dataclass
class WordInfo:
    """Individual word with coordinates from page.get_text('words')."""
    bbox: Tuple[float, float, float, float]
    text: str
    block_no: int
    line_no: int
    word_no: int


@dataclass
class CoordinateMapping:
    """Maps a paragraph to PDF coordinates."""
    paragraph_id: str
    page_number: int
    bbox: Tuple[float, float, float, float]
    confidence: float
    strategy: str  # 'full_text', 'chunked', 'word_sequence'


@dataclass
class SectionNode:
    """A node in the section hierarchy built from heading levels."""
    heading_paragraph_id: str | None  # None for orphan paragraphs before any heading
    heading_level: int  # 0 = no heading (orphan), 1-9 = heading level
    title: str
    para_index: int  # index of heading paragraph, or first child's index for root
    children: list = None  # list of child SectionNode
    paragraph_ids: list = None  # IDs of direct non-heading child paragraphs
    style_name: str | None = None
    has_highlights: bool = False
    has_revisions: bool = False
    is_image: bool = False

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.paragraph_ids is None:
            self.paragraph_ids = []

    def all_paragraph_ids(self) -> list[str]:
        """Recursively collect all paragraph IDs in this section."""
        ids = list(self.paragraph_ids)
        if self.heading_paragraph_id:
            ids.append(self.heading_paragraph_id)
        for child in self.children:
            ids.extend(child.all_paragraph_ids())
        return ids
