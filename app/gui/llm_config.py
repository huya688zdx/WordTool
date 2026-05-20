from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton,
    QLabel, QGroupBox,
)

from app.ai.client import LLMClient
from app.gui.i18n import I18n


class LLMConfigWidget(QGroupBox):
    def __init__(self):
        super().__init__("")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        self.provider_label = QLabel(I18n.tr("llm.provider"))
        layout.addWidget(self.provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list(LLMClient.PROVIDER_CONFIGS.keys()) + ["Custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        self.url_label = QLabel(I18n.tr("llm.base_url"))
        layout.addWidget(self.url_label)

        self.base_url_input = QLineEdit("https://api.openai.com/v1")
        self.base_url_input.setMinimumWidth(250)
        layout.addWidget(self.base_url_input)

        self.model_label = QLabel(I18n.tr("llm.model"))
        layout.addWidget(self.model_label)

        self.model_input = QLineEdit("gpt-4o")
        self.model_input.setMinimumWidth(120)
        layout.addWidget(self.model_input)

        self.key_label = QLabel(I18n.tr("llm.api_key"))
        layout.addWidget(self.key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setMinimumWidth(150)
        layout.addWidget(self.api_key_input)

        self.test_btn = QPushButton(I18n.tr("llm.test"))
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def refresh_text(self):
        self.setTitle(I18n.tr("llm.title"))
        self.provider_label.setText(I18n.tr("llm.provider"))
        self.url_label.setText(I18n.tr("llm.base_url"))
        self.model_label.setText(I18n.tr("llm.model"))
        self.key_label.setText(I18n.tr("llm.api_key"))
        self.api_key_input.setPlaceholderText(I18n.tr("llm.api_key_placeholder"))
        self.test_btn.setText(I18n.tr("llm.test"))

    def _on_provider_changed(self, name: str):
        config = LLMClient.PROVIDER_CONFIGS.get(name)
        if config:
            self.base_url_input.setText(config["base_url"])
            self.model_input.setText(config["model"])

    def _test_connection(self):
        api_key = self.get_api_key()
        if not api_key:
            self.status_label.setText(I18n.tr("llm.need_key"))
            return

        self.status_label.setText(I18n.tr("llm.testing"))
        try:
            client = LLMClient(api_key=api_key, base_url=self.get_base_url(), model=self.get_model())
            if client.test_connection():
                self.status_label.setText(I18n.tr("llm.connected"))
            else:
                self.status_label.setText(I18n.tr("llm.failed"))
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def get_api_key(self) -> str:
        return self.api_key_input.text().strip()

    def get_base_url(self) -> str:
        return self.base_url_input.text().strip()

    def get_model(self) -> str:
        return self.model_input.text().strip()
