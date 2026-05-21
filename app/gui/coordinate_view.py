from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QScrollArea, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from app.models.base import get_session_factory
from app.models.coordinate import PDFCoordinate
from app.models.document import Document
from app.render.page_cropper import PageCropper
from app.storage.local_fs import storage
from app.gui.i18n import I18n


class CoordinateView(QGroupBox):
    def __init__(self):
        super().__init__("")
        self._cropper = PageCropper()
        self._zoom = 2.0
        self._last_pdf_path = None
        self._last_coord = None
        self._last_mode = "paragraph"  # "paragraph" or "section"
        self._last_section_bboxes = {}  # {page_number: [bbox, ...]}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.coord_label = QLabel("")
        self.coord_label.setWordWrap(True)
        layout.addWidget(self.coord_label)

        zoom_row = QHBoxLayout()
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_row.addWidget(self.zoom_out_btn)

        self.zoom_label = QLabel("")
        zoom_row.addWidget(self.zoom_label)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_row.addWidget(self.zoom_in_btn)
        zoom_row.addStretch()
        layout.addLayout(zoom_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(200)
        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)

    def clear(self):
        """Clear screenshot and reset internal state."""
        self._last_pdf_path = None
        self._last_coord = None
        self._last_section_bboxes = {}
        self.coord_label.setText(I18n.tr("coord.hint"))
        self.image_label.setText(I18n.tr("coord.no_image"))

    def refresh_text(self):
        self.setTitle(I18n.tr("coord.title"))
        self.coord_label.setText(I18n.tr("coord.hint"))
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()

    def _update_screenshot(self):
        if self._last_mode == "paragraph":
            self._update_paragraph_screenshot()
        elif self._last_mode == "section":
            self._update_section_screenshot()

    def _update_paragraph_screenshot(self):
        if self._last_pdf_path and self._last_coord:
            try:
                image_bytes = self._cropper.crop_paragraph(
                    self._last_pdf_path, self._last_coord.page_number,
                    (self._last_coord.bbox_x0, self._last_coord.bbox_y0,
                     self._last_coord.bbox_x1, self._last_coord.bbox_y1),
                    padding=15, zoom=self._zoom,
                )
                pixmap = QPixmap()
                pixmap.loadFromData(image_bytes)
                self.image_label.setPixmap(pixmap)
                self.image_label.setFixedSize(pixmap.size())
            except Exception as e:
                self.image_label.setText(I18n.tr("coord.crop_error", error=str(e)))
        else:
            self.image_label.setText(I18n.tr("coord.no_image"))

    def _update_section_screenshot(self):
        if not self._last_pdf_path or not self._last_section_bboxes:
            self.image_label.setText(I18n.tr("coord.no_image"))
            return
        try:
            page = min(self._last_section_bboxes.keys())
            bboxes = self._last_section_bboxes[page]
            if not bboxes:
                self.image_label.setText(I18n.tr("coord.no_image"))
                return
            image_bytes = self._cropper.crop_union(
                self._last_pdf_path, page, bboxes,
                padding=10, zoom=self._zoom,
            )
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            self.image_label.setPixmap(pixmap)
            self.image_label.setFixedSize(pixmap.size())
        except Exception as e:
            self.image_label.setText(I18n.tr("coord.crop_error", error=str(e)))

    def load_coordinates(self, paragraph_id: str, document_id: str):
        self._last_mode = "paragraph"
        self._last_section_bboxes = {}
        db = get_session_factory()()
        try:
            coords = db.query(PDFCoordinate).filter(
                PDFCoordinate.document_id == document_id,
                PDFCoordinate.paragraph_id == paragraph_id,
            ).all()

            if not coords:
                self.coord_label.setText(I18n.tr("coord.not_found"))
                self.image_label.setText(I18n.tr("coord.no_image"))
                self._last_coord = None
                return

            c = coords[0]
            self._last_coord = c
            info = (
                f"{I18n.tr('coord.page')}: {c.page_number}\n"
                f"{I18n.tr('coord.bbox')}: ({c.bbox_x0:.1f}, {c.bbox_y0:.1f}, "
                f"{c.bbox_x1:.1f}, {c.bbox_y1:.1f})\n"
                f"{I18n.tr('coord.confidence')}: {c.match_confidence:.2f}\n"
                f"{I18n.tr('coord.strategy')}: {c.match_strategy}"
            )
            self.coord_label.setText(info)

            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.pdf_storage_key:
                pdf_path = storage.get_path(doc.pdf_storage_key)
                if pdf_path.exists():
                    self._last_pdf_path = pdf_path
                    self._update_screenshot()
                else:
                    self.image_label.setText(I18n.tr("coord.no_image"))
        finally:
            db.close()

    def load_section_coordinates(self, section_node, document_id: str):
        """Load combined coordinates for all paragraphs in a section.

        Computes the union bbox per page and shows the first page's screenshot.
        """
        from app.layout.page_model import SectionNode
        self._last_mode = "section"
        self._last_coord = None

        para_ids = section_node.all_paragraph_ids()
        if not para_ids:
            self.coord_label.setText(I18n.tr("coord.not_found"))
            self.image_label.setText(I18n.tr("coord.no_image"))
            return

        db = get_session_factory()()
        try:
            coords = db.query(PDFCoordinate).filter(
                PDFCoordinate.document_id == document_id,
                PDFCoordinate.paragraph_id.in_(para_ids),
            ).all()

            if not coords:
                self.coord_label.setText(I18n.tr("coord.not_found"))
                self.image_label.setText(I18n.tr("coord.no_image"))
                return

            # Group bboxes by page
            pages = {}
            for c in coords:
                bbox = (c.bbox_x0, c.bbox_y0, c.bbox_x1, c.bbox_y1)
                pages.setdefault(c.page_number, []).append(bbox)

            self._last_section_bboxes = pages
            page_nums = sorted(pages.keys())
            page_str = str(page_nums[0]) if len(page_nums) == 1 else f"{page_nums[0]}-{page_nums[-1]}"
            title = section_node.title[:60] if section_node.title else ""
            info = I18n.tr("coord.section_info",
                          title=title, count=len(para_ids), page=page_str)
            self.coord_label.setText(info)

            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.pdf_storage_key:
                pdf_path = storage.get_path(doc.pdf_storage_key)
                if pdf_path.exists():
                    self._last_pdf_path = pdf_path
                    self._update_screenshot()
                else:
                    self.image_label.setText(I18n.tr("coord.no_image"))
        finally:
            db.close()

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.5, 6.0)
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.5, 0.5)
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()
