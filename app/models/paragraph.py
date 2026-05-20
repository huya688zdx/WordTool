from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Paragraph(Base, TimestampMixin):
    __tablename__ = "paragraphs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"))
    para_index: Mapped[int] = mapped_column(Integer)
    style_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    heading_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str] = mapped_column(Text, default="")
    xml_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_highlights: Mapped[bool] = mapped_column(Boolean, default=False)
    has_revisions: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_image: Mapped[bool] = mapped_column(Boolean, default=False)

    document = relationship("Document", back_populates="paragraphs")
    runs = relationship("Run", back_populates="paragraph", order_by="Run.run_index")
    coordinates = relationship("PDFCoordinate", back_populates="paragraph")

    @property
    def highlighted_text(self) -> str:
        return "".join(r.text for r in self.runs if r.is_highlighted)

    @property
    def changed_text(self) -> str:
        return "".join(r.text for r in self.runs if r.is_inserted)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    paragraph_id: Mapped[str] = mapped_column(String(36), ForeignKey("paragraphs.id", ondelete="CASCADE"))
    run_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    is_bold: Mapped[bool] = mapped_column(Boolean, default=False)
    is_italic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    highlight_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    shading_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_inserted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted_text: Mapped[bool] = mapped_column(Boolean, default=False)
    revision_author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    paragraph = relationship("Paragraph", back_populates="runs")
