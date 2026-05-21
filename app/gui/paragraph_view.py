from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QHeaderView, QMenu,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QAction

from app.models.base import get_session_factory
from app.models.paragraph import Paragraph
from app.layout.page_model import SectionNode
from app.gui.i18n import I18n


def build_section_tree(paragraphs: list[Paragraph]) -> SectionNode:
    """Build a section hierarchy from a flat list of paragraphs.

    Heading paragraphs become section parent nodes; non-heading paragraphs
    become leaf children of the nearest ancestor heading.
    """
    root = SectionNode(
        heading_paragraph_id=None,
        heading_level=0,
        title="",
        para_index=0,
    )
    stack: list[tuple[SectionNode, int]] = [(root, 0)]

    for para in paragraphs:
        if para.heading_level is not None and para.heading_level > 0:
            level = para.heading_level
            while stack and stack[-1][1] >= level:
                stack.pop()
            node = SectionNode(
                heading_paragraph_id=para.id,
                heading_level=level,
                title=para.full_text,
                para_index=para.para_index,
                style_name=para.style_name,
                has_highlights=para.has_highlights,
                has_revisions=para.has_revisions,
                is_image=para.is_image,
            )
            stack[-1][0].children.append(node)
            stack.append((node, level))
        else:
            stack[-1][0].paragraph_ids.append(para.id)

    return root


class ParagraphView(QGroupBox):
    paragraph_selected = Signal(str, str)        # (paragraph_id, document_id)
    section_selected = Signal(object, str)       # (SectionNode, document_id)

    def __init__(self):
        super().__init__("")
        self._document_id = None
        self._section_root: SectionNode | None = None
        self._para_map: dict[str, Paragraph] = {}
        self._setup_ui()
        self._setup_context_menu()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

    def _setup_context_menu(self):
        self.tree.setContextMenuPolicy(Qt.ActionsContextMenu)
        self._expand_all_action = QAction(self)
        self._expand_all_action.triggered.connect(self.tree.expandAll)
        self.tree.addAction(self._expand_all_action)
        self._collapse_all_action = QAction(self)
        self._collapse_all_action.triggered.connect(self.tree.collapseAll)
        self.tree.addAction(self._collapse_all_action)

    def refresh_text(self):
        self.setTitle(I18n.tr("para.title"))
        self.tree.setHeaderLabels([
            I18n.tr("para.col_index"),
            I18n.tr("para.col_content"),
            I18n.tr("para.col_style"),
            I18n.tr("para.col_highlight"),
            I18n.tr("para.col_revision"),
        ])
        self._expand_all_action.setText(I18n.tr("para.expand_all"))
        self._collapse_all_action.setText(I18n.tr("para.collapse_all"))

    def load_paragraphs(self, document_id: str):
        self._document_id = document_id
        self.tree.clear()
        self._para_map.clear()

        db = get_session_factory()()
        try:
            paragraphs = db.query(Paragraph).filter(
                Paragraph.document_id == document_id
            ).order_by(Paragraph.para_index).all()

            self._para_map = {p.id: p for p in paragraphs}
            self._section_root = build_section_tree(paragraphs)
            self._populate_tree(self._section_root)
        finally:
            db.close()

    def _populate_tree(self, root: SectionNode):
        """Recursively populate the QTreeWidget from a SectionNode tree."""
        for child in root.children:
            section_item = self._make_section_item(child)
            self.tree.addTopLevelItem(section_item)

        # Orphan paragraphs (before any heading)
        if root.paragraph_ids:
            orphan = SectionNode(
                heading_paragraph_id=None,
                heading_level=0,
                title=I18n.tr("para.orphan_section"),
                para_index=0,
                paragraph_ids=root.paragraph_ids,
            )
            orphan_item = self._make_section_item(orphan)
            self.tree.addTopLevelItem(orphan_item)

    def _make_section_item(self, node: SectionNode) -> QTreeWidgetItem:
        """Create a tree item for a section node and its children."""
        heading_para = None
        if node.heading_paragraph_id:
            heading_para = self._para_map.get(node.heading_paragraph_id)

        texts = [
            str(node.para_index) if node.para_index else "",
            node.title[:100],
            node.style_name or (heading_para.style_name if heading_para else "-"),
            "⚡" if node.has_highlights else "-",
            "✏" if node.has_revisions else "-",
        ]

        if node.heading_level == 0:
            # Orphan/root node — show special marker
            texts[0] = "-"
            texts[2] = "-"

        item = QTreeWidgetItem(texts)
        # Store section node in UserRole of column 1
        item.setData(1, Qt.UserRole + 1, node)
        # Store heading paragraph_id in UserRole of column 1
        item.setData(1, Qt.UserRole, node.heading_paragraph_id)

        # Style the section header row
        font = item.font(0)
        font.setBold(True)
        for col in range(5):
            item.setFont(col, font)

        if node.has_highlights:
            yellow = QColor(255, 255, 200)
            for col in range(5):
                item.setBackground(col, QBrush(yellow))
        elif node.is_image:
            blue = QColor(200, 220, 255)
            for col in range(5):
                item.setBackground(col, QBrush(blue))

        # Add child sections (recursive)
        for child_node in node.children:
            child_item = self._make_section_item(child_node)
            item.addChild(child_item)

        # Add leaf paragraphs
        for pid in node.paragraph_ids:
            para = self._para_map.get(pid)
            if para is None:
                continue
            leaf_texts = [
                str(para.para_index),
                para.full_text[:100],
                para.style_name or "-",
                I18n.tr("para.image_marker") if para.is_image else ("⚡" if para.has_highlights else "-"),
                "✏" if para.has_revisions else "-",
            ]
            leaf_item = QTreeWidgetItem(leaf_texts)
            leaf_item.setData(1, Qt.UserRole, para.id)

            if para.has_highlights:
                yellow = QColor(255, 255, 200)
                for col in range(5):
                    leaf_item.setBackground(col, QBrush(yellow))
            elif para.is_image:
                blue = QColor(200, 220, 255)
                for col in range(5):
                    leaf_item.setBackground(col, QBrush(blue))

            item.addChild(leaf_item)

        return item

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        if self._document_id is None:
            return
        section_node = item.data(1, Qt.UserRole + 1)
        if section_node is not None:
            # Clicked a section heading node
            self.section_selected.emit(section_node, self._document_id)
        else:
            # Clicked a leaf paragraph
            para_id = item.data(1, Qt.UserRole)
            if para_id:
                self.paragraph_selected.emit(para_id, self._document_id)
