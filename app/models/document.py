import enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    RENDERING = "rendering"
    RENDERED = "rendered"
    ALIGNING = "aligning"
    ALIGNED = "aligned"
    ERROR = "error"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    filename: Mapped[str] = mapped_column(String(512))
    original_format: Mapped[str] = mapped_column(String(10))
    storage_key: Mapped[str] = mapped_column(String(1024))
    pdf_storage_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    paragraphs = relationship("Paragraph", back_populates="document", order_by="Paragraph.para_index")
    coordinates = relationship("PDFCoordinate", back_populates="document")
