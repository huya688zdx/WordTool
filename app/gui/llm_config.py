from pathlib import Path
import json

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton,
    QLabel, QGroupBox, QCheckBox, QVBoxLayout,
)

from app.ai.client import LLMClient
from app.gui.i18n import I18n

_config_path = Path("./data/llm_config.json")


def _load_config() -> dict:
    if _config_path.exists():
        try:
            return json.loads(_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(data: dict) -> None:
    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class LLMConfigWidget(QGroupBox):
    def __init__(self):
        super().__init__("")
        self._setup_ui()
        self.load()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        top_row = QHBoxLayout()

        self.provider_label = QLabel(I18n.tr("llm.provider"))
        top_row.addWidget(self.provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list(LLMClient.PROVIDER_CONFIGS.keys()) + ["Custom"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        top_row.addWidget(self.provider_combo)

        self.url_label = QLabel(I18n.tr("llm.base_url"))
        top_row.addWidget(self.url_label)

        self.base_url_input = QLineEdit("https://api.openai.com/v1")
        self.base_url_input.setMinimumWidth(250)
        top_row.addWidget(self.base_url_input)

        self.model_label = QLabel(I18n.tr("llm.model"))
        top_row.addWidget(self.model_label)

        self.model_input = QLineEdit("gpt-4o")
        self.model_input.setMinimumWidth(120)
        top_row.addWidget(self.model_input)

        self.key_label = QLabel(I18n.tr("llm.api_key"))
        top_row.addWidget(self.key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setMinimumWidth(150)
        top_row.addWidget(self.api_key_input)

        self.test_btn = QPushButton(I18n.tr("llm.test"))
        self.test_btn.clicked.connect(self._test_connection)
        top_row.addWidget(self.test_btn)

        self.status_label = QLabel("")
        top_row.addWidget(self.status_label)
        top_row.addStretch()
        main_layout.addLayout(top_row)

        # AI visual detection toggle row
        ai_row = QHBoxLayout()
        self.ai_visual_check = QCheckBox(I18n.tr("llm.ai_visual"))
        ai_row.addWidget(self.ai_visual_check)
        ai_row.addStretch()
        main_layout.addLayout(ai_row)

    def refresh_text(self):
        self.setTitle(I18n.tr("llm.title"))
        self.provider_label.setText(I18n.tr("llm.provider"))
        self.url_label.setText(I18n.tr("llm.base_url"))
        self.model_label.setText(I18n.tr("llm.model"))
        self.key_label.setText(I18n.tr("llm.api_key"))
        self.api_key_input.setPlaceholderText(I18n.tr("llm.api_key_placeholder"))
        self.test_btn.setText(I18n.tr("llm.test"))
        self.ai_visual_check.setText(I18n.tr("llm.ai_visual"))

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

    def load(self):
        """Load saved config from disk."""
        data = _load_config()
        if data.get("api_key"):
            self.api_key_input.setText(data["api_key"])
        if data.get("base_url"):
            self.base_url_input.setText(data["base_url"])
        if data.get("model"):
            self.model_input.setText(data["model"])
        self.ai_visual_check.setChecked(data.get("ai_visual_enabled", False))

    def save(self):
        """Persist current config to disk."""
        _save_config({
            "api_key": self.get_api_key(),
            "base_url": self.get_base_url(),
            "model": self.get_model(),
            "ai_visual_enabled": self.is_ai_visual_enabled(),
        })

    def is_ai_visual_enabled(self) -> bool:
        return self.ai_visual_check.isChecked()

    def get_api_key(self) -> str:
        return self.api_key_input.text().strip()

    def get_base_url(self) -> str:
        return self.base_url_input.text().strip()

    def get_model(self) -> str:
        return self.model_input.text().strip()
