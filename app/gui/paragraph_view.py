from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush

from app.models.base import get_session_factory
from app.models.paragraph import Paragraph


class ParagraphView(QGroupBox):
    paragraph_selected = Signal(str, str)  # paragraph_id, document_id

    def __init__(self):
        super().__init__("段落列表")
        self._document_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "#", "内容", "样式", "高亮", "修订"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self.table)

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
                # Index
                self.table.setItem(row, 0, QTableWidgetItem(str(para.para_index)))

                # Text
                text_item = QTableWidgetItem(para.full_text[:100])
                text_item.setData(Qt.UserRole, para.id)
                self.table.setItem(row, 1, text_item)

                # Style
                self.table.setItem(row, 2, QTableWidgetItem(
                    para.style_name or "-"
                ))

                # Highlight marker
                hl_item = QTableWidgetItem("⚡" if para.has_highlights else "-")
                self.table.setItem(row, 3, hl_item)

                # Revision marker
                rev_item = QTableWidgetItem("✏" if para.has_revisions else "-")
                self.table.setItem(row, 4, rev_item)

                # Color rows with highlights
                if para.has_highlights:
                    yellow = QColor(255, 255, 200)
                    for col in range(5):
                        self.table.item(row, col).setBackground(QBrush(yellow))

        finally:
            db.close()

    def _on_cell_clicked(self, row: int, col: int):
        text_item = self.table.item(row, 1)
        if text_item and self._document_id:
            para_id = text_item.data(Qt.UserRole)
            self.paragraph_selected.emit(para_id, self._document_id)
