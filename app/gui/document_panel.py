from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QFileDialog, QListWidgetItem, QGroupBox, QMessageBox, QMenu,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction

from app.models.base import get_session_factory
from app.models.document import Document
from app.models.paragraph import Paragraph
from app.models.coordinate import PDFCoordinate
from app.storage.local_fs import storage
from app.gui.i18n import I18n


def delete_document(document_id: str) -> None:
    """Delete a document: remove DB records (cascade) and storage files."""
    db = get_session_factory()()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        storage_key = doc.storage_key
        pdf_key = doc.pdf_storage_key

        # Delete child records explicitly (SQLAlchemy ORM doesn't always
        # delegate to DB-level CASCADE without passive_deletes=True)
        db.query(PDFCoordinate).filter(
            PDFCoordinate.document_id == document_id
        ).delete()
        db.query(Paragraph).filter(
            Paragraph.document_id == document_id
        ).delete()

        db.delete(doc)
        db.commit()

        # Delete storage files after successful DB commit
        if storage_key:
            storage.delete_file(storage_key)
        if pdf_key:
            storage.delete_file(pdf_key)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DocumentPanel(QGroupBox):
    document_selected = Signal(str)
    document_deleted = Signal(str)  # emitted when a document is deleted

    def __init__(self):
        super().__init__("")
        self._setup_ui()
        self._setup_context_menu()
        self._load_documents()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("")
        self.upload_btn.clicked.connect(self._on_upload)
        btn_row.addWidget(self.upload_btn)

        self.delete_btn = QPushButton("")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self.doc_list = QListWidget()
        self.doc_list.itemDoubleClicked.connect(self._on_document_double_clicked)
        layout.addWidget(self.doc_list)

    def _setup_context_menu(self):
        self.doc_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.doc_list.customContextMenuRequested.connect(self._on_context_menu)

    def _on_context_menu(self, pos):
        item = self.doc_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(I18n.tr("doc.delete"))
        action = menu.exec(self.doc_list.mapToGlobal(pos))
        if action == delete_action:
            self._delete_item(item)

    def refresh_text(self):
        self.setTitle(I18n.tr("doc.title"))
        self.upload_btn.setText(I18n.tr("doc.upload"))
        self.delete_btn.setText(I18n.tr("doc.delete"))
        if hasattr(self, "_uploading") and self._uploading:
            self.upload_btn.setText(I18n.tr("doc.uploading"))

    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, I18n.tr("doc.upload"), "",
            "Word/PDF (*.docx *.pdf);;All Files (*)"
        )
        if not path:
            return

        from app.gui.worker import PipelineWorker

        self._uploading = True
        self.worker = PipelineWorker(path)
        self.worker.finished.connect(self._on_pipeline_done)
        self.worker.error.connect(self._on_pipeline_error)
        self.worker.start()

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText(I18n.tr("doc.uploading"))

    def _on_pipeline_done(self, document_id, result):
        self._uploading = False
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText(I18n.tr("doc.upload"))
        self._load_documents()

    def _on_pipeline_error(self, error_msg):
        self._uploading = False
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText(I18n.tr("doc.upload"))

    def _on_document_double_clicked(self, item: QListWidgetItem):
        doc_id = item.data(Qt.UserRole)
        self.document_selected.emit(doc_id)

    def _on_delete(self):
        item = self.doc_list.currentItem()
        if not item:
            QMessageBox.information(self, "", I18n.tr("doc.delete"))
            return
        self._delete_item(item)

    def _delete_item(self, item: QListWidgetItem):
        doc_id = item.data(Qt.UserRole)
        filename = item.text()

        reply = QMessageBox.question(
            self,
            I18n.tr("doc.delete"),
            I18n.tr("doc.delete_confirm", filename=filename),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            delete_document(doc_id)
            self._load_documents()
            self.document_deleted.emit(doc_id)
            QMessageBox.information(self, "", I18n.tr("doc.deleted"))
        except Exception as e:
            QMessageBox.warning(
                self, "",
                I18n.tr("doc.delete_error", error=str(e))
            )

    def _load_documents(self):
        self.doc_list.clear()
        db = get_session_factory()()
        try:
            docs = db.query(Document).order_by(Document.created_at.desc()).all()
            for doc in docs:
                display = f"{doc.filename}  [{doc.status}]"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, doc.id)
                self.doc_list.addItem(item)
        finally:
            db.close()
