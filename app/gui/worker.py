from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.models.base import get_session_factory
from app.models.document import Document
from app.models.paragraph import Paragraph, Run
from app.models.coordinate import PDFCoordinate
from app.parser.docx_parser import DocxParser
from app.render.word_renderer import render_docx_to_pdf
from app.render.text_anchor import map_paragraphs_to_pdf
from app.storage.local_fs import storage


class PipelineWorker(QThread):
    """Run parse → render → align in background thread."""
    finished = Signal(str, object)  # document_id, result dict
    progress = Signal(str)          # status message
    error = Signal(str)             # error message
    password_needed = Signal()      # emitted when document needs a password

    def __init__(self, file_path: str, password: str | None = None):
        super().__init__()
        self.file_path = Path(file_path)
        self.password = password

    def run(self):
        try:
            db = get_session_factory()()
            try:
                doc = self._create_document(db)

                if doc.original_format == "doc":
                    self.progress.emit("解析 .doc 结构（通过 Word COM）...")
                    self._parse_doc_via_com(doc, db)
                else:
                    self.progress.emit("解析 DOCX 结构...")
                    self._parse_docx(doc, db)

                self.progress.emit("渲染 PDF（调用 Word）...")
                self._render(doc, db)

                self.progress.emit("对齐段落坐标...")
                self._align(doc, db)

                self.progress.emit("完成！")
                self.finished.emit(doc.id, {
                    "status": "aligned",
                    "document_id": doc.id,
                })
            finally:
                db.close()
        except Exception as e:
            msg = str(e)
            if "password" in msg.lower() or "protected" in msg.lower():
                self.password_needed.emit()
            self.error.emit(msg)

    def _create_document(self, db):
        suffix = self.file_path.suffix.lower()
        fmt = "doc" if suffix == ".doc" else "docx"
        storage_key = storage.save_file(self.file_path, subdir="documents")
        doc = Document(
            filename=self.file_path.name,
            original_format=fmt,
            storage_key=storage_key,
            status="uploaded",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def _parse_docx(self, doc, db):
        doc.status = "parsing"
        db.commit()

        parser = DocxParser()
        structure = parser.parse(storage.get_path(doc.storage_key))

        for para_data in structure.paragraphs:
            paragraph = Paragraph(
                document_id=doc.id,
                para_index=para_data.para_index,
                style_name=para_data.style_name,
                heading_level=para_data.heading_level,
                full_text=para_data.full_text,
                xml_raw=para_data.xml_raw,
                has_highlights=para_data.has_highlights,
                has_revisions=para_data.has_revisions,
                is_deleted=para_data.is_deleted,
                is_image=para_data.is_image,
            )
            db.add(paragraph)
            db.flush()

            for i, run_data in enumerate(para_data.runs):
                run = Run(
                    paragraph_id=paragraph.id,
                    run_index=i,
                    text=run_data.text,
                    is_bold=run_data.is_bold,
                    is_italic=run_data.is_italic,
                    is_highlighted=run_data.is_highlighted,
                    highlight_color=run_data.highlight_color,
                    shading_color=run_data.shading_color,
                    is_inserted=run_data.is_inserted,
                    is_deleted_text=run_data.is_deleted_text,
                    revision_author=run_data.revision_author,
                )
                db.add(run)

        doc.status = "parsed"
        db.commit()

    def _parse_doc_via_com(self, doc, db):
        """Parse .doc file by extracting text via Word COM (no python-docx support)."""
        doc.status = "parsing"
        db.commit()

        from app.parser.doc_parser import parse_doc_via_com
        docx_path = storage.get_path(doc.storage_key)
        paragraphs_data = parse_doc_via_com(docx_path)

        for para_data in paragraphs_data:
            paragraph = Paragraph(
                document_id=doc.id,
                para_index=para_data.para_index,
                style_name=para_data.style_name,
                heading_level=para_data.heading_level,
                full_text=para_data.full_text,
                has_highlights=para_data.has_highlights,
                has_revisions=para_data.has_revisions,
                is_deleted=para_data.is_deleted,
                is_image=para_data.is_image,
            )
            db.add(paragraph)
            db.flush()

            for i, run_data in enumerate(para_data.runs):
                run = Run(
                    paragraph_id=paragraph.id,
                    run_index=i,
                    text=run_data.text,
                    is_bold=run_data.is_bold,
                    is_italic=run_data.is_italic,
                    is_highlighted=run_data.is_highlighted,
                    highlight_color=run_data.highlight_color,
                    shading_color=run_data.shading_color,
                    is_inserted=run_data.is_inserted,
                    is_deleted_text=run_data.is_deleted_text,
                    revision_author=run_data.revision_author,
                )
                db.add(run)

        doc.status = "parsed"
        db.commit()

    def _render(self, doc, db):
        doc.status = "rendering"
        db.commit()

        from app.config.settings import settings

        docx_path = storage.get_path(doc.storage_key)
        pdf_filename = self.file_path.stem + ".pdf"
        pdf_path = settings.TEMP_DIR / pdf_filename
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        render_docx_to_pdf(docx_path, pdf_path, password=self.password)
        pdf_storage_key = storage.save_file(pdf_path, subdir="pdfs")

        doc.pdf_storage_key = pdf_storage_key
        doc.status = "rendered"
        db.commit()

    def _align(self, doc, db):
        doc.status = "aligning"
        db.commit()

        paragraphs = db.query(Paragraph).filter(
            Paragraph.document_id == doc.id
        ).order_by(Paragraph.para_index).all()

        from app.parser.docx_parser import ParagraphData
        para_data_list = []
        for p in paragraphs:
            pd = ParagraphData(
                para_index=p.para_index,
                full_text=p.full_text,
                style_name=p.style_name,
                heading_level=p.heading_level,
                has_highlights=p.has_highlights,
                has_revisions=p.has_revisions,
                is_deleted=p.is_deleted,
                is_image=p.is_image,
            )
            para_data_list.append(pd)

        pdf_path = storage.get_path(doc.pdf_storage_key)
        mappings = map_paragraphs_to_pdf(para_data_list, str(pdf_path))

        for mapping in mappings:
            para = next(
                (p for p in paragraphs if p.para_index == mapping.paragraph_id),
                None
            )
            if para:
                coord = PDFCoordinate(
                    document_id=doc.id,
                    paragraph_id=para.id,
                    page_number=mapping.page_number,
                    bbox_x0=mapping.bbox[0],
                    bbox_y0=mapping.bbox[1],
                    bbox_x1=mapping.bbox[2],
                    bbox_y1=mapping.bbox[3],
                    match_confidence=mapping.confidence,
                    match_strategy=mapping.strategy,
                )
                db.add(coord)

        doc.status = "aligned"
        db.commit()
