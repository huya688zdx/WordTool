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
import logging
_log = logging.getLogger(__name__)


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
        doc = None
        storage_key = None
        try:
            db = get_session_factory()()
            try:
                doc = self._create_document(db)
                storage_key = doc.storage_key

                if doc.original_format == "doc":
                    self.progress.emit("解析 .doc 结构（通过 Word COM）...")
                    self._parse_doc_via_com(doc, db)
                elif self.password:
                    # Encrypted .docx — python-docx can't open it, use Word COM
                    self.progress.emit("解析加密 DOCX 结构（通过 Word COM）...")
                    self._parse_doc_via_com(doc, db)
                else:
                    self.progress.emit("解析 DOCX 结构...")
                    self._parse_docx(doc, db)

                self.progress.emit("渲染 PDF（调用 Word）...")
                self._render(doc, db)

                self._ai_heading_check(doc, db)

                self.progress.emit("对齐段落坐标...")
                self._align(doc, db)

                doc.status = "aligned"
                db.commit()

                self.progress.emit("完成！")
                self.finished.emit(doc.id, {
                    "status": "aligned",
                    "document_id": doc.id,
                })
            except Exception:
                # Rollback any partial DB changes and clean up storage
                db.rollback()
                if doc is not None:
                    try:
                        if doc.pdf_storage_key:
                            storage.delete_file(doc.pdf_storage_key)
                    except Exception:
                        pass
                if storage_key:
                    try:
                        storage.delete_file(storage_key)
                    except Exception:
                        pass
                raise
            finally:
                db.close()
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "protected" in msg or "encrypted" in msg or "cannot open" in msg:
                self.password_needed.emit()
            else:
                self.error.emit(str(e))

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
        db.flush()  # flush to get ID, but don't commit yet
        return doc

    def _parse_docx(self, doc, db):
        doc.status = "parsing"
        db.flush()

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
        db.flush()

    def _parse_doc_via_com(self, doc, db):
        """Parse .doc file by extracting text via Word COM (no python-docx support)."""
        doc.status = "parsing"
        db.flush()

        from app.parser.doc_parser import parse_doc_via_com
        docx_path = storage.get_path(doc.storage_key)
        paragraphs_data = parse_doc_via_com(docx_path, password=self.password)

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
        db.flush()

    def _ai_heading_check(self, doc, db):
        """Run AI heading detection — text-only or visual depending on settings."""
        llm_cfg = {}
        try:
            from app.gui.llm_config import _load_config
            llm_cfg = _load_config()
        except Exception as e:
            print(f"[AI标题] 读取配置失败: {e}")
            return

        if not llm_cfg:
            print("[AI标题] 未找到 LLM 配置（请先在 Settings 中保存 API Key）")
            return
        if not llm_cfg.get("ai_heading_enabled", False):
            print("[AI标题] 未启用（Settings → 勾选 'AI标题层级检测'）")
            return
        if not llm_cfg.get("api_key"):
            print("[AI标题] 未配置 API Key")
            return
        if not llm_cfg.get("base_url"):
            print("[AI标题] 未配置 Base URL")
            return

        paragraphs = db.query(Paragraph).filter(
            Paragraph.document_id == doc.id
        ).order_by(Paragraph.para_index).all()

        para_list = [
            {"index": p.para_index, "heading_level": p.heading_level, "text": p.full_text}
            for p in paragraphs
        ]

        word_positions = getattr(self, "_word_positions", None)

        # Check if visual heading verification is enabled
        use_visual = llm_cfg.get("ai_visual_enabled", False)

        self.progress.emit("AI 检查标题层级...")

        if use_visual:
            self._ai_heading_check_visual(doc, paragraphs, para_list, word_positions, llm_cfg, db)
        else:
            self._ai_heading_check_text(para_list, word_positions, llm_cfg, paragraphs, db)

    def _ai_heading_check_text(self, para_list, word_positions, llm_cfg, paragraphs, db):
        """Text-only heading detection (no page images)."""
        if word_positions:
            print(f"[AI标题] 发送 {len(para_list)} 个段落 + {len(word_positions)} 个坐标分析层级结构...")
        else:
            print(f"[AI标题] 发送 {len(para_list)} 个段落分析层级结构...")
        try:
            from app.ai.heading_detector import detect_headings
            corrections = detect_headings(
                llm_cfg["api_key"], llm_cfg["base_url"], llm_cfg["model"],
                para_list,
                positions=word_positions,
            )
            self._apply_heading_corrections(corrections, paragraphs, db)
        except Exception as e:
            print(f"[AI标题] 检测失败: {e}")

    def _ai_heading_check_visual(self, doc, paragraphs, para_list, word_positions, llm_cfg, db):
        """Visual heading verification — send page screenshots + text to AI."""
        from app.ai.visual_detector import VisualPageDetector
        from app.render.page_cropper import PageCropper
        import fitz

        detector = VisualPageDetector(
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg["base_url"],
            model=llm_cfg["model"],
        )

        # Build page→paragraphs mapping from Word COM positions
        page_paras = {}  # page_num → [(para_index, text, heading_level)]
        if word_positions:
            wp_map = {wp["para_index"]: wp["page"] for wp in word_positions}
            for p in paragraphs:
                page = wp_map.get(p.para_index, 1)
                page_paras.setdefault(page, []).append({
                    "index": p.para_index,
                    "text": p.full_text,
                    "heading_level": p.heading_level or 0,
                })
        else:
            # No Word COM positions — put all paragraphs on page 1
            page_paras[1] = [
                {"index": p.para_index, "text": p.full_text, "heading_level": p.heading_level or 0}
                for p in paragraphs
            ]

        pdf_path = storage.get_path(doc.pdf_storage_key)
        cropper = PageCropper()
        pdf_doc = fitz.open(str(pdf_path))
        total_pages = len(pdf_doc)

        all_corrections = []
        for page_num in sorted(page_paras.keys()):
            try:
                image_bytes = cropper.get_page_thumbnail(
                    Path(pdf_path), page_num, max_width=1200,
                )
                print(f"[AI标题-视觉] 发送第 {page_num}/{total_pages} 页，{len(page_paras[page_num])} 个段落")
                self.progress.emit(f"AI 视觉验证标题层级 (第 {page_num}/{total_pages} 页)...")

                corrections = detector.verify_headings(
                    image_bytes,
                    page_number=page_num,
                    total_pages=total_pages,
                    paragraphs=page_paras[page_num],
                )
                all_corrections.extend(corrections)
            except Exception as e:
                print(f"[AI标题-视觉] 第 {page_num} 页失败: {e}")
                continue

        pdf_doc.close()

        if all_corrections:
            print(f"[AI标题-视觉] 共 {len(all_corrections)} 个层级修正")
            self._apply_heading_corrections(all_corrections, paragraphs, db)
        else:
            print("[AI标题-视觉] AI 认为层级无需修正")

    def _apply_heading_corrections(self, corrections, paragraphs, db):
        """Apply heading level corrections from AI to DB session."""
        if not corrections:
            print("[AI标题] AI 认为层级无需修正")
            return
        print(f"[AI标题] 发现 {len(corrections)} 个层级修正:")
        for c in corrections:
            idx = c.get("index", 0)
            level = c.get("heading_level", 1)
            reason = c.get("reason", "")
            print(f"  段落[{idx}] → Heading {level}: {reason}")
            p = next((x for x in paragraphs if x.para_index == idx), None)
            if p:
                p.heading_level = level
        db.flush()

    def _render(self, doc, db):
        doc.status = "rendering"
        db.flush()

        from app.config.settings import settings
        from uuid import uuid4

        docx_path = storage.get_path(doc.storage_key)
        pdf_filename = f"{uuid4().hex}.pdf"
        pdf_path = settings.TEMP_DIR / pdf_filename
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            _, positions = render_docx_to_pdf(
                docx_path, pdf_path,
                password=self.password,
                extract_positions=True,
            )
            pdf_storage_key = storage.save_file(pdf_path, subdir="pdfs")
        finally:
            if pdf_path.exists():
                pdf_path.unlink(missing_ok=True)

        doc.pdf_storage_key = pdf_storage_key
        # Store Word COM positions for use in alignment
        self._word_positions = positions
        doc.status = "rendered"
        db.flush()

    def _align(self, doc, db):
        doc.status = "aligning"
        db.flush()

        paragraphs = db.query(Paragraph).filter(
            Paragraph.document_id == doc.id
        ).order_by(Paragraph.para_index).all()

        word_positions = getattr(self, "_word_positions", None)
        para_by_index = {p.para_index: p for p in paragraphs}

        # Prefer bboxes extracted from the rendered PDF itself. Word COM is
        # still useful for rendering and page hints, but Range.Information()
        # does not expose a real paragraph rectangle, so its y1 is only an
        # estimate and tends to over/under-crop screenshots.
        from app.parser.docx_parser import ParagraphData
        para_data_list = [
            ParagraphData(
                para_index=p.para_index,
                full_text=p.full_text,
                style_name=p.style_name,
                heading_level=p.heading_level,
                has_highlights=p.has_highlights,
                has_revisions=p.has_revisions,
                is_deleted=p.is_deleted,
                is_image=p.is_image,
            )
            for p in paragraphs
        ]

        pdf_path = storage.get_path(doc.pdf_storage_key)
        mappings = map_paragraphs_to_pdf(para_data_list, str(pdf_path))
        mapped_indices = set()
        if mappings:
            print(f"[对齐] 使用 PDF 文本坐标映射 {len(mappings)} 个段落")
            self.progress.emit(f"对齐: 使用 PDF 文本坐标 ({len(mappings)} 段落)")

        for mapping in mappings:
            para = para_by_index.get(mapping.paragraph_id)
            if not para:
                continue
            mapped_indices.add(mapping.paragraph_id)
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

        if word_positions:
            fallback_count = 0
            for wp in word_positions:
                pi = wp.get("para_index", 0)
                if pi in mapped_indices:
                    continue
                para = para_by_index.get(pi)
                if not para:
                    continue
                fallback_count += 1
                coord = PDFCoordinate(
                    document_id=doc.id,
                    paragraph_id=para.id,
                    page_number=wp["page"],
                    bbox_x0=wp["x0"],
                    bbox_y0=wp["y0"],
                    bbox_x1=wp["x1"],
                    bbox_y1=wp["y1"],
                    match_confidence=0.35,
                    match_strategy="word_com_fallback",
                )
                db.add(coord)
            if fallback_count:
                print(f"[对齐] PDF 未匹配段落使用 Word COM 兜底 {fallback_count} 个")

        doc.status = "aligned"
        db.flush()
