from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from app.gui.i18n import I18n


EMBEDDED_C_EXTENSIONS = {".c", ".h", ".s", ".S", ".asm", ".inc", ".ld"}
SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".vscode",
    ".idea",
    "build",
    "out",
    "dist",
    "debug",
    "release",
    "__pycache__",
}


@dataclass
class CodeCandidate:
    file_path: Path
    line_number: int
    symbol: str
    score: int
    snippet: str
    hits: list[str]


class CodeCandidatePanel(QGroupBox):
    """Embedded-C code candidate search workspace."""

    def __init__(self):
        super().__init__("")
        self._code_dir: Path | None = None
        self._change_text = ""
        self._selected_code = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.select_btn = QPushButton("")
        self.select_btn.clicked.connect(self._on_select_dir)
        top_row.addWidget(self.select_btn)

        self.dir_label = QLabel("")
        self.dir_label.setWordWrap(True)
        top_row.addWidget(self.dir_label, 1)
        layout.addLayout(top_row)

        self.change_label = QLabel("")
        self.change_label.setWordWrap(True)
        layout.addWidget(self.change_label)

        keyword_row = QHBoxLayout()
        self.keyword_label = QLabel("")
        keyword_row.addWidget(self.keyword_label)
        self.keyword_edit = QPlainTextEdit()
        self.keyword_edit.setMaximumHeight(62)
        self.keyword_edit.setPlaceholderText("")
        keyword_row.addWidget(self.keyword_edit, 1)

        self.search_btn = QPushButton("")
        self.search_btn.clicked.connect(self.search_candidates)
        keyword_row.addWidget(self.search_btn)
        layout.addLayout(keyword_row)

        manual_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.symbol_input = QLineEdit()
        self.line_input = QLineEdit()
        self.add_manual_btn = QPushButton("")
        self.add_manual_btn.clicked.connect(self._add_manual_candidate)
        manual_row.addWidget(self.path_input, 3)
        manual_row.addWidget(self.symbol_input, 2)
        manual_row.addWidget(self.line_input, 1)
        manual_row.addWidget(self.add_manual_btn)
        layout.addLayout(manual_row)

        self.manual_code = QPlainTextEdit()
        self.manual_code.setMaximumHeight(110)
        self.manual_code.setFont(QFont("Consolas", 10))
        layout.addWidget(self.manual_code)

        splitter = QSplitter(Qt.Horizontal)
        self.candidate_list = QListWidget()
        self.candidate_list.itemClicked.connect(self._on_candidate_clicked)
        splitter.addWidget(self.candidate_list)

        preview_wrap = QWidget()
        preview_layout = QVBoxLayout(preview_wrap)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        preview_layout.addWidget(self.meta_label)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self.preview)
        splitter.addWidget(preview_wrap)
        splitter.setSizes([360, 760])
        layout.addWidget(splitter, 1)

        self.refresh_text()

    def refresh_text(self):
        self.setTitle(I18n.tr("candidate.title"))
        self.select_btn.setText(I18n.tr("candidate.select_dir"))
        self.dir_label.setText(str(self._code_dir) if self._code_dir else I18n.tr("candidate.no_dir"))
        self.keyword_label.setText(I18n.tr("candidate.keywords"))
        self.keyword_edit.setPlaceholderText(I18n.tr("candidate.keyword_hint"))
        self.search_btn.setText(I18n.tr("candidate.search"))
        self.path_input.setPlaceholderText(I18n.tr("candidate.path_hint"))
        self.symbol_input.setPlaceholderText(I18n.tr("candidate.symbol_hint"))
        self.line_input.setPlaceholderText(I18n.tr("candidate.line_hint"))
        self.add_manual_btn.setText(I18n.tr("candidate.add_manual"))
        self.manual_code.setPlaceholderText(I18n.tr("candidate.manual_hint"))
        if not self._change_text:
            self.change_label.setText(I18n.tr("candidate.no_change"))
        self.meta_label.setText(I18n.tr("candidate.preview_hint"))

    def set_change_context(self, title: str, text: str):
        self._change_text = text or ""
        label = title or self._change_text[:80] or "未选择"
        self.change_label.setText(I18n.tr("candidate.current_change", label=label))
        suggested = self._suggest_keywords(self._change_text)
        if suggested and not self.keyword_edit.toPlainText().strip():
            self.keyword_edit.setPlainText(" ".join(suggested))

    def _on_select_dir(self):
        path = QFileDialog.getExistingDirectory(self, I18n.tr("candidate.select_dir"))
        if not path:
            return
        self._code_dir = Path(path)
        self.dir_label.setText(str(self._code_dir))
        self.search_candidates()

    def search_candidates(self):
        self.candidate_list.clear()
        self.preview.clear()
        self.meta_label.setText(I18n.tr("candidate.preview_hint"))

        if not self._code_dir:
            self.candidate_list.addItem(I18n.tr("candidate.select_dir_first"))
            return

        keywords = self._current_keywords()
        if not keywords:
            self.candidate_list.addItem(I18n.tr("candidate.need_keywords"))
            return

        candidates = self._scan_codebase(keywords)
        if not candidates:
            self.candidate_list.addItem(I18n.tr("candidate.no_results"))
            return

        for candidate in candidates[:200]:
            rel = candidate.file_path.relative_to(self._code_dir)
            hits = ", ".join(candidate.hits[:5])
            item = QListWidgetItem(
                f"[{candidate.score}] {rel}:{candidate.line_number}  {candidate.symbol}  ({hits})"
            )
            item.setData(Qt.UserRole, candidate)
            self.candidate_list.addItem(item)

    def _current_keywords(self) -> list[str]:
        raw = self.keyword_edit.toPlainText()
        tokens = re.split(r"[\s,;，；]+", raw)
        result = []
        seen = set()
        for token in tokens:
            token = token.strip()
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result

    def _add_manual_candidate(self):
        code = self.manual_code.toPlainText().strip()
        if not code:
            self.candidate_list.addItem(I18n.tr("candidate.manual_empty"))
            return
        file_text = self.path_input.text().strip() or "manual.c"
        line_text = self.line_input.text().strip()
        try:
            line_number = int(line_text) if line_text else 1
        except ValueError:
            line_number = 1
        candidate = CodeCandidate(
            file_path=Path(file_text),
            line_number=line_number,
            symbol=self.symbol_input.text().strip() or "-",
            score=999,
            snippet=code,
            hits=["manual"],
        )
        item = QListWidgetItem(f"[manual] {file_text}:{line_number}  {candidate.symbol}")
        item.setData(Qt.UserRole, candidate)
        self.candidate_list.insertItem(0, item)
        self.candidate_list.setCurrentItem(item)
        self._on_candidate_clicked(item)

    def _scan_codebase(self, keywords: list[str]) -> list[CodeCandidate]:
        candidates: list[CodeCandidate] = []
        lowered = [(kw, kw.lower()) for kw in keywords]

        for file_path in self._iter_code_files():
            text = self._read_text(file_path)
            if not text:
                continue
            lines = text.splitlines()
            lower_lines = [line.lower() for line in lines]
            for idx, lower_line in enumerate(lower_lines):
                hits = [kw for kw, low_kw in lowered if low_kw in lower_line]
                if not hits:
                    continue
                start = max(0, idx - 8)
                end = min(len(lines), idx + 18)
                snippet_lines = lines[start:end]
                snippet = "\n".join(
                    f"{line_no:5d}: {line}"
                    for line_no, line in enumerate(snippet_lines, start + 1)
                )
                symbol = self._find_symbol(lines, idx)
                score = len(hits) * 10 + len(set(hits))
                if re.search(r"\b(?:void|int|uint\d+_t|bool|static)\b", lines[idx]):
                    score += 4
                candidates.append(
                    CodeCandidate(
                        file_path=file_path,
                        line_number=idx + 1,
                        symbol=symbol,
                        score=score,
                        snippet=snippet,
                        hits=hits,
                    )
                )

        candidates.sort(key=lambda c: (-c.score, str(c.file_path), c.line_number))
        return candidates

    def _iter_code_files(self):
        if not self._code_dir:
            return
        for root, dirs, files in os.walk(self._code_dir):
            dirs[:] = [
                d for d in dirs
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            for filename in files:
                path = Path(root) / filename
                if path.suffix in EMBEDDED_C_EXTENSIONS:
                    yield path

    @staticmethod
    def _read_text(path: Path) -> str:
        for encoding in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                return path.read_text(encoding=encoding, errors="ignore")
            except OSError:
                return ""
            except UnicodeDecodeError:
                continue
        return ""

    @staticmethod
    def _find_symbol(lines: list[str], idx: int) -> str:
        func_pattern = re.compile(
            r"^\s*(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w\s\*]*\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?\s*$"
        )
        macro_pattern = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)")
        for pos in range(idx, max(-1, idx - 80), -1):
            line = lines[pos]
            macro = macro_pattern.match(line)
            if macro:
                return macro.group(1)
            func = func_pattern.match(line)
            if func:
                return func.group(1)
        return "-"

    @staticmethod
    def _suggest_keywords(text: str) -> list[str]:
        identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text or "")
        useful = []
        seen = set()
        for token in identifiers:
            if token.lower() in {"the", "and", "for", "with", "this", "that"}:
                continue
            if token not in seen:
                seen.add(token)
                useful.append(token)
        return useful[:20]

    def _on_candidate_clicked(self, item: QListWidgetItem):
        candidate = item.data(Qt.UserRole)
        if not isinstance(candidate, CodeCandidate):
            return
        self._selected_code = candidate.snippet
        rel = candidate.file_path.relative_to(self._code_dir) if self._code_dir else candidate.file_path
        self.meta_label.setText(
            f"文件: {rel} | 行: {candidate.line_number} | 符号: {candidate.symbol} | 命中: {', '.join(candidate.hits)}"
        )
        self.preview.setPlainText(candidate.snippet)

    def get_selected_code(self) -> str:
        return self._selected_code
