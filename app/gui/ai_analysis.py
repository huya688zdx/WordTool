from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QTextEdit, QLabel, QGroupBox,
)
from PySide6.QtCore import Signal

from app.ai.requirement_analyzer import analyze_requirement
from app.gui.i18n import I18n


class AIAnalysisWidget(QGroupBox):
    analysis_requested = Signal(str)

    def __init__(self):
        super().__init__("")
        self._use_code_context = False
        self._paragraph_text = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        control_row = QHBoxLayout()
        self.analyze_btn = QPushButton(I18n.tr("ai.analyze"))
        self.analyze_btn.clicked.connect(self._on_analyze)
        control_row.addWidget(self.analyze_btn)

        self.code_ctx_check = QCheckBox(I18n.tr("ai.use_code"))
        self.code_ctx_check.toggled.connect(self._on_ctx_toggled)
        control_row.addWidget(self.code_ctx_check)
        control_row.addStretch()
        layout.addLayout(control_row)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText(I18n.tr("ai.hint"))
        layout.addWidget(self.result_text)

    def refresh_text(self):
        self.setTitle(I18n.tr("ai.title"))
        self.analyze_btn.setText(I18n.tr("ai.analyze"))
        self.code_ctx_check.setText(I18n.tr("ai.use_code"))
        self.result_text.setPlaceholderText(I18n.tr("ai.hint"))

    def _on_analyze(self):
        if not self._paragraph_text:
            self.result_text.setPlainText(I18n.tr("ai.no_para"))
            return
        self.analysis_requested.emit(self._paragraph_text)

    def _on_ctx_toggled(self, checked: bool):
        self._use_code_context = checked

    def set_paragraph_text(self, text: str):
        self._paragraph_text = text

    def use_code_context(self) -> bool:
        return self._use_code_context

    def run_analysis(self, api_key: str, base_url: str, model: str,
                     paragraph_text: str, code_context: str = ""):
        self.result_text.setPlainText(I18n.tr("ai.analyzing"))
        try:
            result = analyze_requirement(
                api_key=api_key, base_url=base_url, model=model,
                paragraph_text=paragraph_text, code_context=code_context,
            )
            self.result_text.setMarkdown(result)
        except Exception as e:
            self.result_text.setPlainText(I18n.tr("ai.error", error=str(e)))

    def clear(self):
        self.result_text.clear()
