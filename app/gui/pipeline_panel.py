from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QProgressBar,
    QLabel, QGroupBox,
)
from PySide6.QtCore import Signal

from app.gui.i18n import I18n


class PipelinePanel(QGroupBox):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__("")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.parse_btn = QPushButton("")
        layout.addWidget(self.parse_btn)

        self.render_btn = QPushButton("")
        layout.addWidget(self.render_btn)

        self.align_btn = QPushButton("")
        layout.addWidget(self.align_btn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def refresh_text(self):
        self.setTitle(I18n.tr("pipeline.title"))
        self.parse_btn.setText(I18n.tr("pipeline.parse"))
        self.render_btn.setText(I18n.tr("pipeline.render"))
        self.align_btn.setText(I18n.tr("pipeline.align"))
        self.status_label.setText(I18n.tr("pipeline.ready"))

    def set_progress(self, value: int, message: str):
        self.progress.setVisible(True)
        self.progress.setValue(value)
        self.status_label.setText(message)
        self.status_changed.emit(message)

    def set_done(self):
        self.progress.setValue(100)
        self.status_label.setText(I18n.tr("pipeline.done"))
        self.status_changed.emit(I18n.tr("pipeline.done"))
