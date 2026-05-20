from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QStatusBar, QMessageBox, QMenuBar,
    QGroupBox, QScrollArea, QDockWidget,
)
from PySide6.QtCore import Qt

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
        self.setWindowTitle("WordAgent - AI 需求变更追踪系统")
        self.resize(1400, 900)

        self._setup_menu()
        self._setup_ui()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction("退出(&Q)", self.close)

        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.addAction("关于(&A)", self._show_about)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_splitter = QSplitter(Qt.Horizontal)

        # === Left panel ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # Document panel
        self.document_panel = DocumentPanel()
        left_layout.addWidget(self.document_panel)

        # Codebase panel
        self.codebase_panel = CodebasePanel()
        left_layout.addWidget(self.codebase_panel)

        # Pipeline panel
        self.pipeline_panel = PipelinePanel()
        left_layout.addWidget(self.pipeline_panel)

        left_layout.addStretch()

        # === Right panel ===
        right_splitter = QSplitter(Qt.Vertical)

        # Paragraph view (top)
        self.paragraph_view = ParagraphView()
        right_splitter.addWidget(self.paragraph_view)

        # Coordinate view (bottom)
        self.coordinate_view = CoordinateView()
        right_splitter.addWidget(self.coordinate_view)

        right_splitter.setSizes([400, 400])

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([350, 1000])

        # Main layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)

        # === Bottom dock: LLM + AI ===
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(4, 4, 4, 4)

        self.llm_config = LLMConfigWidget()
        bottom_layout.addWidget(self.llm_config)

        self.ai_analysis = AIAnalysisWidget()
        bottom_layout.addWidget(self.ai_analysis)

        bottom_dock = QDockWidget("AI 分析")
        bottom_dock.setWidget(bottom_widget)
        bottom_dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom_dock)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

    def _connect_signals(self):
        # Document selected → load paragraphs
        self.document_panel.document_selected.connect(
            self._on_document_selected
        )
        # Pipeline progress
        self.pipeline_panel.status_changed.connect(
            self.statusbar.showMessage
        )
        # Paragraph selected → show coordinates + screenshot
        self.paragraph_view.paragraph_selected.connect(
            self._on_paragraph_selected
        )
        # AI analysis needs document context
        self.ai_analysis.analysis_requested.connect(
            self._on_analysis_requested
        )

    def _on_document_selected(self, document_id: str):
        """Load paragraphs and coordinates for selected document."""
        self.statusbar.showMessage(f"加载文档 {document_id}...")
        self.paragraph_view.load_paragraphs(document_id)

    def _on_paragraph_selected(self, paragraph_id: str, document_id: str):
        """Show coordinates and screenshot for selected paragraph."""
        self.coordinate_view.load_coordinates(paragraph_id, document_id)

    def _on_analysis_requested(self, paragraph_text: str):
        """Run AI analysis on selected paragraph."""
        api_key = self.llm_config.get_api_key()
        base_url = self.llm_config.get_base_url()
        model = self.llm_config.get_model()

        if not api_key:
            QMessageBox.warning(self, "配置缺失", "请先配置大模型 API Key")
            return

        code_context = ""
        if self.ai_analysis.use_code_context():
            code_context = self.codebase_panel.get_selected_code()

        self.ai_analysis.run_analysis(
            api_key=api_key,
            base_url=base_url,
            model=model,
            paragraph_text=paragraph_text,
            code_context=code_context,
        )

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于 WordAgent",
            "WordAgent - AI 需求变更追踪系统\n\n"
            "自动解析 Word 设计书 → 识别修改点 → 定位影响代码\n\n"
            "Version 0.1.0"
        )
