from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QListWidget,
    QFileDialog, QLabel, QListWidgetItem, QGroupBox,
)
from PySide6.QtCore import Signal, Qt

from app.models.base import get_session_factory
from app.models.document import Document


class DocumentPanel(QGroupBox):
    document_selected = Signal(str)  # document_id

    def __init__(self):
        super().__init__("文档管理")
        self._setup_ui()
        self._load_documents()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.upload_btn = QPushButton("上传文档")
        self.upload_btn.clicked.connect(self._on_upload)
        layout.addWidget(self.upload_btn)

        self.doc_list = QListWidget()
        self.doc_list.itemDoubleClicked.connect(self._on_document_double_clicked)
        layout.addWidget(self.doc_list)

    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文档", "",
            "Word/PDF (*.docx *.pdf);;All Files (*)"
        )
        if not path:
            return

        from app.gui.worker import PipelineWorker

        self.worker = PipelineWorker(path)
        self.worker.progress.connect(lambda msg: None)
        self.worker.finished.connect(self._on_pipeline_done)
        self.worker.error.connect(lambda e: None)
        self.worker.start()

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText("处理中...")

    def _on_pipeline_done(self, document_id, result):
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText("上传文档")
        self._load_documents()

    def _on_document_double_clicked(self, item: QListWidgetItem):
        doc_id = item.data(Qt.UserRole)
        self.document_selected.emit(doc_id)

    def _load_documents(self):
        self.doc_list.clear()
        db = get_session_factory()()
        try:
            docs = db.query(Document).order_by(Document.created_at.desc()).all()
            for doc in docs:
                item = QListWidgetItem(f"{doc.filename}  [{doc.status}]")
                item.setData(Qt.UserRole, doc.id)
                self.doc_list.addItem(item)
        finally:
            db.close()
