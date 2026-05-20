from typing import Tuple
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PDFCoordinate(Base, TimestampMixin):
    __tablename__ = "pdf_coordinates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"))
    paragraph_id: Mapped[str] = mapped_column(String(36), ForeignKey("paragraphs.id", ondelete="CASCADE"))
    page_number: Mapped[int] = mapped_column(Integer)  # 1-based
    bbox_x0: Mapped[float] = mapped_column(Float)
    bbox_y0: Mapped[float] = mapped_column(Float)
    bbox_x1: Mapped[float] = mapped_column(Float)
    bbox_y1: Mapped[float] = mapped_column(Float)
    match_confidence: Mapped[float] = mapped_column(Float)
    match_strategy: Mapped[str] = mapped_column(String(32))  # full_text / chunked / word_sequence
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    document = relationship("Document", back_populates="coordinates")
    paragraph = relationship("Paragraph", back_populates="coordinates")

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.bbox_x0, self.bbox_y0, self.bbox_x1, self.bbox_y1)
