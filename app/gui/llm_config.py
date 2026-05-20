from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton,
    QLabel, QGroupBox,
)
from PySide6.QtCore import Qt

from app.ai.client import LLMClient


class LLMConfigWidget(QGroupBox):
    def __init__(self):
        super().__init__("大模型配置")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # Provider selector
        layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list(LLMClient.PROVIDER_CONFIGS.keys()) + ["自定义"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        # Base URL
        layout.addWidget(QLabel("Base URL:"))
        self.base_url_input = QLineEdit("https://api.openai.com/v1")
        self.base_url_input.setMinimumWidth(250)
        layout.addWidget(self.base_url_input)

        # Model
        layout.addWidget(QLabel("Model:"))
        self.model_input = QLineEdit("gpt-4o")
        self.model_input.setMinimumWidth(120)
        layout.addWidget(self.model_input)

        # API Key
        layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setMinimumWidth(150)
        layout.addWidget(self.api_key_input)

        # Test connection
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)

        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _on_provider_changed(self, name: str):
        config = LLMClient.PROVIDER_CONFIGS.get(name)
        if config:
            self.base_url_input.setText(config["base_url"])
            self.model_input.setText(config["model"])

    def _test_connection(self):
        api_key = self.get_api_key()
        if not api_key:
            self.status_label.setText("请填写 API Key")
            return

        self.status_label.setText("测试中...")
        try:
            client = LLMClient(
                api_key=api_key,
                base_url=self.get_base_url(),
                model=self.get_model(),
            )
            if client.test_connection():
                self.status_label.setText("已连接")
            else:
                self.status_label.setText("连接失败")
        except Exception as e:
            self.status_label.setText(f"错误: {e}")

    def get_api_key(self) -> str:
        return self.api_key_input.text().strip()

    def get_base_url(self) -> str:
        return self.base_url_input.text().strip()

    def get_model(self) -> str:
        return self.model_input.text().strip()
