from dataclasses import dataclass, field
from typing import List, Tuple


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
