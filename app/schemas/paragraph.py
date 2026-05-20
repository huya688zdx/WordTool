from typing import Optional, List

from pydantic import BaseModel


class RunResponse(BaseModel):
    id: str
    run_index: int
    text: str
    is_bold: bool
    is_italic: bool
    is_highlighted: bool
    highlight_color: Optional[str] = None
    is_inserted: bool
    is_deleted_text: bool

    class Config:
        from_attributes = True


class ParagraphResponse(BaseModel):
    id: str
    para_index: int
    style_name: Optional[str] = None
    heading_level: Optional[int] = None
    full_text: str
    has_highlights: bool
    has_revisions: bool
    runs: List[RunResponse] = []

    class Config:
        from_attributes = True
