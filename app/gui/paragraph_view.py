from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush

from app.models.base import get_session_factory
from app.models.paragraph import Paragraph
from app.gui.i18n import I18n


class ParagraphView(QGroupBox):
    paragraph_selected = Signal(str, str)

    def __init__(self):
        super().__init__("")
        self._document_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def refresh_text(self):
        self.setTitle(I18n.tr("para.title"))
        self.table.setHorizontalHeaderLabels([
            I18n.tr("para.col_index"),
            I18n.tr("para.col_content"),
            I18n.tr("para.col_style"),
            I18n.tr("para.col_highlight"),
            I18n.tr("para.col_revision"),
        ])

    def load_paragraphs(self, document_id: str):
        self._document_id = document_id
        self.table.setRowCount(0)
        db = get_session_factory()()
        try:
            paragraphs = db.query(Paragraph).filter(
                Paragraph.document_id == document_id
            ).order_by(Paragraph.para_index).all()

            self.table.setRowCount(len(paragraphs))
            for row, para in enumerate(paragraphs):
                self.table.setItem(row, 0, QTableWidgetItem(str(para.para_index)))

                text_item = QTableWidgetItem(para.full_text[:100])
                text_item.setData(Qt.UserRole, para.id)
                self.table.setItem(row, 1, text_item)

                self.table.setItem(row, 2, QTableWidgetItem(para.style_name or "-"))

                if para.is_image:
                    hl_item = QTableWidgetItem(I18n.tr("para.image_marker"))
                else:
                    hl_item = QTableWidgetItem("⚡" if para.has_highlights else "-")
                self.table.setItem(row, 3, hl_item)

                rev_item = QTableWidgetItem("✏" if para.has_revisions else "-")
                self.table.setItem(row, 4, rev_item)

                if para.has_highlights:
                    yellow = QColor(255, 255, 200)
                    for col in range(5):
                        self.table.item(row, col).setBackground(QBrush(yellow))
                elif para.is_image:
                    blue = QColor(200, 220, 255)
                    for col in range(5):
                        self.table.item(row, col).setBackground(QBrush(blue))
        finally:
            db.close()

    def _on_cell_clicked(self, row: int, col: int):
        text_item = self.table.item(row, 1)
        if text_item and self._document_id:
            para_id = text_item.data(Qt.UserRole)
            self.paragraph_selected.emit(para_id, self._document_id)
