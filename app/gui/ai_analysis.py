from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QTextEdit, QLabel, QGroupBox,
)
from PySide6.QtCore import Signal

from app.ai.requirement_analyzer import analyze_requirement


class AIAnalysisWidget(QGroupBox):
    analysis_requested = Signal(str)  # emits paragraph_text

    def __init__(self):
        super().__init__("AI 需求分析")
        self._use_code_context = False
        self._paragraph_text = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Control row
        control_row = QHBoxLayout()

        self.analyze_btn = QPushButton("分析选中段落")
        self.analyze_btn.clicked.connect(self._on_analyze)
        control_row.addWidget(self.analyze_btn)

        self.code_ctx_check = QCheckBox("包含代码上下文")
        self.code_ctx_check.toggled.connect(self._on_ctx_toggled)
        control_row.addWidget(self.code_ctx_check)

        control_row.addStretch()
        layout.addLayout(control_row)

        # Result area
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText(
            '点击段落列表中的任意行，然后点击「分析选中段落」按钮'
        )
        layout.addWidget(self.result_text)

    def _on_analyze(self):
        if not self._paragraph_text:
            self.result_text.setPlainText("请先在左侧段落列表中点击一个段落")
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
        """Execute AI analysis in-place (called from main window)."""
        self.result_text.setPlainText("分析中，请稍候...")
        try:
            result = analyze_requirement(
                api_key=api_key,
                base_url=base_url,
                model=model,
                paragraph_text=paragraph_text,
                code_context=code_context,
            )
            self.result_text.setMarkdown(result)
        except Exception as e:
            self.result_text.setPlainText(f"分析失败: {e}")

    def clear(self):
        self.result_text.clear()
