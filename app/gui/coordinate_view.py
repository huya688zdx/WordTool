from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QScrollArea, QSlider, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from app.models.base import get_session_factory
from app.models.coordinate import PDFCoordinate
from app.models.document import Document
from app.render.page_cropper import PageCropper
from app.storage.local_fs import storage


class CoordinateView(QGroupBox):
    def __init__(self):
        super().__init__("PDF 坐标 & 截图")
        self._cropper = PageCropper()
        self._zoom = 2.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Coordinate info
        self.coord_label = QLabel("点击左侧段落查看坐标和截图")
        self.coord_label.setWordWrap(True)
        layout.addWidget(self.coord_label)

        # Zoom controls
        zoom_row = QHBoxLayout()
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_row.addWidget(self.zoom_out_btn)

        self.zoom_label = QLabel(f"缩放: {self._zoom:.1f}x")
        zoom_row.addWidget(self.zoom_label)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_row.addWidget(self.zoom_in_btn)
        zoom_row.addStretch()
        layout.addLayout(zoom_row)

        # Screenshot display
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("(截图将显示在此处)")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(200)
        self.scroll.setWidget(self.image_label)

        layout.addWidget(self.scroll)

    def load_coordinates(self, paragraph_id: str, document_id: str):
        db = get_session_factory()()
        try:
            coords = db.query(PDFCoordinate).filter(
                PDFCoordinate.document_id == document_id,
                PDFCoordinate.paragraph_id == paragraph_id,
            ).all()

            if not coords:
                self.coord_label.setText("(未找到坐标映射)")
                self.image_label.setText("(无截图)")
                return

            c = coords[0]
            info = (
                f"Page: {c.page_number}\n"
                f"BBox: ({c.bbox_x0:.1f}, {c.bbox_y0:.1f}, "
                f"{c.bbox_x1:.1f}, {c.bbox_y1:.1f})\n"
                f"Confidence: {c.match_confidence:.2f}\n"
                f"Strategy: {c.match_strategy}"
            )
            self.coord_label.setText(info)

            # Get PDF and crop
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.pdf_storage_key:
                pdf_path = storage.get_path(doc.pdf_storage_key)
                if pdf_path.exists():
                    try:
                        image_bytes = self._cropper.crop_paragraph(
                            pdf_path, c.page_number,
                            (c.bbox_x0, c.bbox_y0, c.bbox_x1, c.bbox_y1),
                            padding=5, zoom=self._zoom,
                        )
                        pixmap = QPixmap()
                        pixmap.loadFromData(image_bytes)
                        self.image_label.setPixmap(pixmap)
                        self.image_label.setFixedSize(pixmap.size())
                    except Exception as e:
                        self.image_label.setText(f"截图失败: {e}")

        finally:
            db.close()

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.5, 6.0)
        self.zoom_label.setText(f"缩放: {self._zoom:.1f}x")

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.5, 0.5)
        self.zoom_label.setText(f"缩放: {self._zoom:.1f}x")
