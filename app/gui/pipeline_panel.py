from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QProgressBar,
    QLabel, QGroupBox,
)
from PySide6.QtCore import Signal


class PipelinePanel(QGroupBox):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__("流程控制")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.parse_btn = QPushButton("1. 解析 DOCX")
        self.parse_btn.clicked.connect(lambda: self.status_changed.emit("请先上传文档（双击文档列表加载）"))
        layout.addWidget(self.parse_btn)

        self.render_btn = QPushButton("2. 渲染 PDF")
        self.render_btn.clicked.connect(lambda: self.status_changed.emit("渲染需通过上传文档触发"))
        layout.addWidget(self.render_btn)

        self.align_btn = QPushButton("3. 文本锚点对齐")
        self.align_btn.clicked.connect(lambda: self.status_changed.emit("对齐需通过上传文档触发"))
        layout.addWidget(self.align_btn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("就绪 - 请上传文档开始")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_progress(self, value: int, message: str):
        self.progress.setVisible(True)
        self.progress.setValue(value)
        self.status_label.setText(message)
        self.status_changed.emit(message)

    def set_done(self):
        self.progress.setValue(100)
        self.status_label.setText("完成")
        self.status_changed.emit("完成")
