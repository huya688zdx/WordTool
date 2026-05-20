import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget,
    QFileDialog, QLabel, QListWidgetItem, QGroupBox,
    QPlainTextEdit, QSplitter, QHBoxLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.gui.i18n import I18n

CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"}


class CodebasePanel(QGroupBox):
    def __init__(self):
        super().__init__("")
        self._current_dir = None
        self._selected_code = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.select_btn = QPushButton("")
        self.select_btn.clicked.connect(self._on_select_dir)
        top_row.addWidget(self.select_btn)

        self.dir_label = QLabel("")
        self.dir_label.setWordWrap(True)
        top_row.addWidget(self.dir_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        splitter = QSplitter(Qt.Vertical)
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_file_clicked)
        splitter.addWidget(self.file_list)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        splitter.addWidget(self.preview)
        splitter.setSizes([200, 150])
        layout.addWidget(splitter)

    def refresh_text(self):
        self.setTitle(I18n.tr("codebase.title"))
        self.select_btn.setText(I18n.tr("codebase.select"))
        if not self._current_dir:
            self.dir_label.setText(I18n.tr("codebase.none"))
        self.preview.setPlaceholderText(I18n.tr("codebase.preview_hint"))

    def _on_select_dir(self):
        path = QFileDialog.getExistingDirectory(self, I18n.tr("codebase.select"))
        if not path:
            return
        self._current_dir = Path(path)
        self.dir_label.setText(path)
        self._scan_files()

    def _scan_files(self):
        self.file_list.clear()
        if not self._current_dir:
            return
        for root, dirs, files in os.walk(self._current_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       ("node_modules", "__pycache__", "venv", ".venv", ".git",
                        "build", "dist", ".idea", ".vscode")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in CODE_EXTENSIONS:
                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(self._current_dir)
                    item = QListWidgetItem(str(rel_path))
                    item.setData(Qt.UserRole, str(full_path))
                    self.file_list.addItem(item)

    def _on_file_clicked(self, item: QListWidgetItem):
        file_path = item.data(Qt.UserRole)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self._selected_code = content
            self.preview.setPlainText(content[:5000])
        except Exception as e:
            self.preview.setPlainText(I18n.tr("codebase.read_error", error=str(e)))

    def get_selected_code(self) -> str:
        return self._selected_code

    def get_codebase_path(self) -> str:
        return str(self._current_dir) if self._current_dir else ""
