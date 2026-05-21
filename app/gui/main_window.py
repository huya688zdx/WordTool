from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QMessageBox, QMenuBar,
    QGroupBox, QDockWidget, QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup

from app.gui.i18n import I18n
from app.gui.document_panel import DocumentPanel
from app.gui.codebase_panel import CodebasePanel
from app.gui.pipeline_panel import PipelinePanel
from app.gui.paragraph_view import ParagraphView
from app.gui.coordinate_view import CoordinateView
from app.gui.llm_config import LLMConfigWidget
from app.gui.ai_analysis import AIAnalysisWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        I18n.instance()
        self.llm_config = LLMConfigWidget()  # hidden, used via Settings menu
        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()
        self._refresh_ui_text()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_splitter = QSplitter(Qt.Horizontal)

        # === Left panel (narrow) ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)

        self.document_panel = DocumentPanel()
        left_layout.addWidget(self.document_panel)

        self.codebase_panel = CodebasePanel()
        left_layout.addWidget(self.codebase_panel)

        self.pipeline_panel = PipelinePanel()
        left_layout.addWidget(self.pipeline_panel)
        left_layout.addStretch()

        # Min width for left panel
        left_widget.setMinimumWidth(240)

        # === Right panel (wide) ===
        right_splitter = QSplitter(Qt.Vertical)
        self.paragraph_view = ParagraphView()
        right_splitter.addWidget(self.paragraph_view)
        self.coordinate_view = CoordinateView()
        right_splitter.addWidget(self.coordinate_view)
        # Paragraph view gets more space
        right_splitter.setSizes([500, 350])

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        # Left panel ~250px, rest for right
        main_splitter.setSizes([260, 1100])
        main_splitter.setStretchFactor(0, 0)  # left: don't stretch
        main_splitter.setStretchFactor(1, 1)  # right: stretch

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)

        # === Bottom dock: AI Analysis ===
        self.ai_analysis = AIAnalysisWidget()
        bottom_dock = QDockWidget()
        bottom_dock.setWidget(self.ai_analysis)
        bottom_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom_dock)

    def _setup_menu(self):
        menubar = self.menuBar()

        self.file_menu = menubar.addMenu("")
        self.exit_action = self.file_menu.addAction("", self.close)

        self.lang_menu = menubar.addMenu("")
        self.lang_group = QActionGroup(self)
        self.lang_group.setExclusive(True)
        self.lang_group.triggered.connect(self._on_language_changed)

        for code, name in I18n.languages():
            action = QAction(name, self)
            action.setCheckable(True)
            action.setData(code)
            self.lang_menu.addAction(action)
            self.lang_group.addAction(action)
            if code == I18n.current_lang():
                action.setChecked(True)

        self.settings_menu = menubar.addMenu("")
        self.llm_settings_action = self.settings_menu.addAction("", self._show_llm_settings)

        self.help_menu = menubar.addMenu("")
        self.about_action = self.help_menu.addAction("", self._show_about)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

    def _connect_signals(self):
        self.document_panel.document_selected.connect(self._on_document_selected)
        self.document_panel.document_deleted.connect(self._on_document_deleted)
        self.pipeline_panel.status_changed.connect(self.statusbar.showMessage)
        self.paragraph_view.paragraph_selected.connect(self._on_paragraph_selected)
        self.paragraph_view.section_selected.connect(self._on_section_selected)
        self.ai_analysis.analysis_requested.connect(self._on_analysis_requested)
        I18n.instance().language_changed.connect(lambda _: self._refresh_ui_text())

    def _refresh_ui_text(self):
        self.setWindowTitle(I18n.tr("app.title"))
        self.file_menu.setTitle(I18n.tr("menu.file"))
        self.exit_action.setText(I18n.tr("menu.file.exit"))
        self.lang_menu.setTitle(I18n.tr("menu.language"))
        self.settings_menu.setTitle(I18n.tr("menu.settings"))
        self.llm_settings_action.setText(I18n.tr("menu.settings.llm"))
        self.help_menu.setTitle(I18n.tr("menu.help"))
        self.about_action.setText(I18n.tr("menu.help.about"))
        self.statusbar.showMessage(I18n.tr("statusbar.ready"))
        self.document_panel.refresh_text()
        self.codebase_panel.refresh_text()
        self.pipeline_panel.refresh_text()
        self.paragraph_view.refresh_text()
        self.coordinate_view.refresh_text()
        self.ai_analysis.refresh_text()
        bottom = self.findChild(QDockWidget)
        if bottom:
            bottom.setWindowTitle(I18n.tr("ai.title"))

    def _on_language_changed(self, action: QAction):
        lang = action.data()
        if lang:
            I18n.set_language(lang)

    def _show_llm_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(I18n.tr("settings.title"))
        dialog.resize(750, 120)
        layout = QVBoxLayout(dialog)

        llm_copy = LLMConfigWidget()
        llm_copy.api_key_input.setText(self.llm_config.get_api_key())
        llm_copy.base_url_input.setText(self.llm_config.get_base_url())
        llm_copy.model_input.setText(self.llm_config.get_model())
        layout.addWidget(llm_copy)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            self.llm_config.api_key_input.setText(llm_copy.get_api_key())
            self.llm_config.base_url_input.setText(llm_copy.get_base_url())
            self.llm_config.model_input.setText(llm_copy.get_model())

    def _on_document_selected(self, document_id: str):
        self.statusbar.showMessage(f"Loading document {document_id}...")
        self.paragraph_view.load_paragraphs(document_id)

    def _on_document_deleted(self, document_id: str):
        # Clear paragraph view and coordinate view when the displayed document is deleted
        self.paragraph_view.clear()
        self.coordinate_view.clear()

    def _on_paragraph_selected(self, paragraph_id: str, document_id: str):
        self.coordinate_view.load_coordinates(paragraph_id, document_id)

    def _on_section_selected(self, section_node, document_id: str):
        self.coordinate_view.load_section_coordinates(section_node, document_id)

    def _on_analysis_requested(self, paragraph_text: str):
        api_key = self.llm_config.get_api_key()
        base_url = self.llm_config.get_base_url()
        model = self.llm_config.get_model()

        if not api_key:
            QMessageBox.warning(self, "", I18n.tr("ai.need_config"))
            return

        code_context = ""
        if self.ai_analysis.use_code_context():
            code_context = self.codebase_panel.get_selected_code()

        self.ai_analysis.run_analysis(
            api_key=api_key, base_url=base_url, model=model,
            paragraph_text=paragraph_text, code_context=code_context,
        )

    def _show_about(self):
        QMessageBox.about(self, I18n.tr("about.title"), I18n.tr("about.text"))
