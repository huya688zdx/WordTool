import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget,
    QFileDialog, QLabel, QListWidgetItem, QGroupBox,
    QPlainTextEdit, QSplitter, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont


CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp", ".c", ".h"}


class CodebasePanel(QGroupBox):
    def __init__(self):
        super().__init__("代码仓库")
        self._current_dir = None
        self._selected_code = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Select directory button
        top_row = QHBoxLayout()
        self.select_btn = QPushButton("选择代码目录")
        self.select_btn.clicked.connect(self._on_select_dir)
        top_row.addWidget(self.select_btn)

        self.dir_label = QLabel("(未选择)")
        self.dir_label.setWordWrap(True)
        top_row.addWidget(self.dir_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        # File tree + preview
        splitter = QSplitter(Qt.Vertical)

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._on_file_clicked)
        splitter.addWidget(self.file_list)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setPlaceholderText("点击文件预览代码...")
        splitter.addWidget(self.preview)
        splitter.setSizes([200, 150])

        layout.addWidget(splitter)

    def _on_select_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择代码仓库目录")
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
            # Skip hidden dirs and common ignores
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
            self.preview.setPlainText(content[:5000])  # limit preview
        except Exception as e:
            self.preview.setPlainText(f"读取失败: {e}")

    def get_selected_code(self) -> str:
        """Return the code content of the currently selected file."""
        return self._selected_code

    def get_codebase_path(self) -> str:
        """Return the root path of the selected codebase."""
        return str(self._current_dir) if self._current_dir else ""
