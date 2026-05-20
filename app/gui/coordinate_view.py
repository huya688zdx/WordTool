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

    def refresh_text(self):
        self.setTitle(I18n.tr("coord.title"))
        self.coord_label.setText(I18n.tr("coord.hint"))
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()

    def _update_screenshot(self):
        if self._last_pdf_path and self._last_coord:
            try:
                image_bytes = self._cropper.crop_paragraph(
                    self._last_pdf_path, self._last_coord.page_number,
                    (self._last_coord.bbox_x0, self._last_coord.bbox_y0,
                     self._last_coord.bbox_x1, self._last_coord.bbox_y1),
                    padding=5, zoom=self._zoom,
                )
                pixmap = QPixmap()
                pixmap.loadFromData(image_bytes)
                self.image_label.setPixmap(pixmap)
                self.image_label.setFixedSize(pixmap.size())
            except Exception as e:
                self.image_label.setText(I18n.tr("coord.crop_error", error=str(e)))
        else:
            self.image_label.setText(I18n.tr("coord.no_image"))

    def load_coordinates(self, paragraph_id: str, document_id: str):
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

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.5, 6.0)
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.5, 0.5)
        self.zoom_label.setText(I18n.tr("coord.zoom", zoom=self._zoom))
        self._update_screenshot()
