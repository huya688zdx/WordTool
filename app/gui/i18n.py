"""Internationalization (i18n) for WordAgent GUI.

Supports: English (en), Japanese (ja), Chinese (zh).
"""

from PySide6.QtCore import QObject, Signal


_translations = {
    "en": {
        "app.title": "WordAgent - AI Requirement Traceability System",
        "menu.file": "&File",
        "menu.file.exit": "E&xit",
        "menu.help": "&Help",
        "menu.help.about": "&About",
        "menu.language": "&Language",
        "menu.settings": "&Settings",
        "menu.settings.llm": "LLM &Config",
        "doc.title": "Documents",
        "doc.upload": "Upload Document",
        "doc.uploading": "Processing...",
        "doc.delete": "Delete",
        "doc.delete_confirm": "Delete '{filename}'?\n\nThis will remove all paragraphs, coordinates, and stored files.\nThis action cannot be undone.",
        "doc.deleted": "Document deleted.",
        "doc.delete_error": "Delete failed: {error}",
        "codebase.title": "Codebase",
        "codebase.select": "Select Code Directory",
        "codebase.none": "(not selected)",
        "codebase.preview_hint": "Click file to preview code...",
        "codebase.read_error": "Read error: {error}",
        "pipeline.title": "Pipeline",
        "pipeline.parse": "1. Parse DOCX",
        "pipeline.render": "2. Render PDF",
        "pipeline.align": "3. Align Text",
        "pipeline.ready": "Ready - upload a document to begin",
        "pipeline.done": "Done",
        "para.title": "Paragraphs",
        "para.col_index": "#",
        "para.col_content": "Content",
        "para.col_style": "Style",
        "para.col_highlight": "Highlight",
        "para.col_revision": "Revision",
        "para.image_marker": "[Image]",
        "coord.title": "PDF Coordinates & Screenshot",
        "coord.hint": "Click a paragraph on the left to view coordinates and screenshot",
        "coord.not_found": "(No coordinate mapping found)",
        "coord.no_image": "(No screenshot)",
        "coord.crop_error": "Crop failed: {error}",
        "coord.zoom": "Zoom: {zoom:.1f}x",
        "coord.page": "Page",
        "coord.bbox": "BBox",
        "coord.confidence": "Confidence",
        "coord.strategy": "Strategy",
        "llm.title": "LLM Config",
        "llm.provider": "Provider:",
        "llm.base_url": "Base URL:",
        "llm.model": "Model:",
        "llm.api_key": "API Key:",
        "llm.api_key_placeholder": "sk-...",
        "llm.test": "Test Connection",
        "llm.testing": "Testing...",
        "llm.connected": "Connected",
        "llm.failed": "Connection Failed",
        "llm.need_key": "Please enter API Key",
        "llm.custom": "Custom",
        "ai.title": "AI Analysis",
        "ai.analyze": "Analyze Selected Paragraph",
        "ai.use_code": "Include Code Context",
        "ai.hint": "Click a paragraph in the list, then click 'Analyze'...",
        "ai.analyzing": "Analyzing, please wait...",
        "ai.no_para": "Please click a paragraph in the list first",
        "ai.need_config": "Please configure LLM first",
        "ai.error": "Analysis failed: {error}",
        "statusbar.ready": "Ready",
        "about.title": "About WordAgent",
        "about.text": (
            "WordAgent - AI Requirement Traceability System\n\n"
            "Parse Word design documents -> Identify changes -> Locate affected code\n\n"
            "Version 0.1.0"
        ),
        "settings.title": "Settings",
        "settings.llm_title": "LLM Configuration",
        "settings.save": "Save",
        "settings.cancel": "Cancel",
        "para.expand_all": "Expand All",
        "para.collapse_all": "Collapse All",
        "para.section_children": "{count} paragraphs",
        "para.orphan_section": "(No Heading)",
        "coord.section_page": "Pages {start}-{end}",
        "coord.section_info": "Section: {title} | {count} paragraphs | Page {page}",
    },
    "ja": {
        "app.title": "WordAgent - AI要件追跡システム",
        "menu.file": "ファイル(&F)",
        "menu.file.exit": "終了(&Q)",
        "menu.help": "ヘルプ(&H)",
        "menu.help.about": "バージョン情報(&A)",
        "menu.language": "言語(&L)",
        "menu.settings": "設定(&S)",
        "menu.settings.llm": "LLM設定(&C)",
        "doc.title": "文書管理",
        "doc.upload": "文書をアップロード",
        "doc.uploading": "処理中...",
        "doc.delete": "削除",
        "doc.delete_confirm": "「{filename}」を削除しますか？\n\nすべての段落、座標、保存ファイルが削除されます。\nこの操作は元に戻せません。",
        "doc.deleted": "文書を削除しました。",
        "doc.delete_error": "削除失敗: {error}",
        "codebase.title": "コードリポジトリ",
        "codebase.select": "コードディレクトリを選択",
        "codebase.none": "(未選択)",
        "codebase.preview_hint": "ファイルをクリックしてコードをプレビュー...",
        "codebase.read_error": "読み込みエラー: {error}",
        "pipeline.title": "パイプライン制御",
        "pipeline.parse": "1. DOCX解析",
        "pipeline.render": "2. PDFレンダリング",
        "pipeline.align": "3. テキスト位置合わせ",
        "pipeline.ready": "準備完了 - 文書をアップロードしてください",
        "pipeline.done": "完了",
        "para.title": "段落一覧",
        "para.col_index": "番号",
        "para.col_content": "内容",
        "para.col_style": "スタイル",
        "para.col_highlight": "ハイライト",
        "para.col_revision": "変更履歴",
        "para.image_marker": "[画像]",
        "coord.title": "PDF座標 & スクリーンショット",
        "coord.hint": "左側の段落をクリックして座標とスクリーンショットを表示",
        "coord.not_found": "(座標マッピングが見つかりません)",
        "coord.no_image": "(スクリーンショットなし)",
        "coord.crop_error": "切り取り失敗: {error}",
        "coord.zoom": "ズーム: {zoom:.1f}x",
        "coord.page": "ページ",
        "coord.bbox": "座標",
        "coord.confidence": "信頼度",
        "coord.strategy": "方式",
        "llm.title": "LLM設定",
        "llm.provider": "プロバイダ:",
        "llm.base_url": "ベースURL:",
        "llm.model": "モデル:",
        "llm.api_key": "APIキー:",
        "llm.api_key_placeholder": "sk-...",
        "llm.test": "接続テスト",
        "llm.testing": "テスト中...",
        "llm.connected": "接続済み",
        "llm.failed": "接続失敗",
        "llm.need_key": "APIキーを入力してください",
        "llm.custom": "カスタム",
        "ai.title": "AI分析",
        "ai.analyze": "選択した段落を分析",
        "ai.use_code": "コードコンテキストを含める",
        "ai.hint": "段落一覧で段落をクリックし、「分析」をクリック...",
        "ai.analyzing": "分析中、お待ちください...",
        "ai.no_para": "左側の段落一覧で段落をクリックしてください",
        "ai.need_config": "先にLLMを設定してください",
        "ai.error": "分析失敗: {error}",
        "statusbar.ready": "準備完了",
        "about.title": "WordAgentについて",
        "about.text": (
            "WordAgent - AI要件追跡システム\n\n"
            "Word設計書の解析 → 変更点の特定 → 影響コードの特定\n\n"
            "バージョン 0.1.0"
        ),
        "settings.title": "設定",
        "settings.llm_title": "LLM設定",
        "settings.save": "保存",
        "settings.cancel": "キャンセル",
        "para.expand_all": "すべて展開",
        "para.collapse_all": "すべて折りたたむ",
        "para.section_children": "{count}個の段落",
        "para.orphan_section": "(見出しなし)",
        "coord.section_page": "{start}-{end}ページ",
        "coord.section_info": "セクション: {title} | {count}段落 | {page}ページ",
    },
    "zh": {
        "app.title": "WordAgent - AI 需求变更追踪系统",
        "menu.file": "文件(&F)",
        "menu.file.exit": "退出(&Q)",
        "menu.help": "帮助(&H)",
        "menu.help.about": "关于(&A)",
        "menu.language": "语言(&L)",
        "menu.settings": "设置(&S)",
        "menu.settings.llm": "大模型配置(&C)",
        "doc.title": "文档管理",
        "doc.upload": "上传文档",
        "doc.uploading": "处理中...",
        "doc.delete": "删除",
        "doc.delete_confirm": "确认删除「{filename}」？\n\n将删除所有段落、坐标数据和存储文件。\n此操作不可撤销。",
        "doc.deleted": "文档已删除。",
        "doc.delete_error": "删除失败: {error}",
        "codebase.title": "代码仓库",
        "codebase.select": "选择代码目录",
        "codebase.none": "(未选择)",
        "codebase.preview_hint": "点击文件预览代码...",
        "codebase.read_error": "读取失败: {error}",
        "pipeline.title": "流程控制",
        "pipeline.parse": "1. 解析 DOCX",
        "pipeline.render": "2. 渲染 PDF",
        "pipeline.align": "3. 文本锚点对齐",
        "pipeline.ready": "就绪 - 请上传文档开始",
        "pipeline.done": "完成",
        "para.title": "段落列表",
        "para.col_index": "序号",
        "para.col_content": "内容",
        "para.col_style": "样式",
        "para.col_highlight": "高亮",
        "para.col_revision": "修订",
        "para.image_marker": "[图片]",
        "coord.title": "PDF 坐标 & 截图",
        "coord.hint": "点击左侧段落查看坐标和截图",
        "coord.not_found": "(未找到坐标映射)",
        "coord.no_image": "(无截图)",
        "coord.crop_error": "截图失败: {error}",
        "coord.zoom": "缩放: {zoom:.1f}x",
        "coord.page": "页码",
        "coord.bbox": "坐标",
        "coord.confidence": "置信度",
        "coord.strategy": "策略",
        "llm.title": "大模型配置",
        "llm.provider": "Provider:",
        "llm.base_url": "Base URL:",
        "llm.model": "Model:",
        "llm.api_key": "API Key:",
        "llm.api_key_placeholder": "sk-...",
        "llm.test": "测试连接",
        "llm.testing": "测试中...",
        "llm.connected": "已连接",
        "llm.failed": "连接失败",
        "llm.need_key": "请填写 API Key",
        "llm.custom": "自定义",
        "ai.title": "AI 需求分析",
        "ai.analyze": "分析选中段落",
        "ai.use_code": "包含代码上下文",
        "ai.hint": "点击段落列表中任意行，然后点击「分析选中段落」...",
        "ai.analyzing": "分析中，请稍候...",
        "ai.no_para": "请先在左侧段落列表中点击一个段落",
        "ai.need_config": "请先配置大模型",
        "ai.error": "分析失败: {error}",
        "statusbar.ready": "就绪",
        "about.title": "关于 WordAgent",
        "about.text": (
            "WordAgent - AI 需求变更追踪系统\n\n"
            "自动解析 Word 设计书 → 识别修改点 → 定位影响代码\n\n"
            "Version 0.1.0"
        ),
        "settings.title": "设置",
        "settings.llm_title": "大模型配置",
        "settings.save": "保存",
        "settings.cancel": "取消",
        "para.expand_all": "全部展开",
        "para.collapse_all": "全部折叠",
        "para.section_children": "{count}个段落",
        "para.orphan_section": "(无标题)",
        "coord.section_page": "第{start}-{end}页",
        "coord.section_info": "章节: {title} | {count}个段落 | 第{page}页",
    },
}


class I18n(QObject):
    """Internationalization manager with language switching signal."""

    language_changed = Signal(str)

    _instance = None
    _current_lang = "zh"

    def __init__(self):
        super().__init__()
        I18n._instance = self

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = I18n()
        return cls._instance

    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        text = _translations.get(cls._current_lang, {}).get(
            key, _translations["en"].get(key, key)
        )
        if kwargs:
            text = text.format(**kwargs)
        return text

    @classmethod
    def tr(cls, key: str, **kwargs) -> str:
        """Alias for get()."""
        return cls.get(key, **kwargs)

    @classmethod
    def current_lang(cls) -> str:
        return cls._current_lang

    @classmethod
    def set_language(cls, lang: str):
        if lang in _translations:
            cls._current_lang = lang
            if cls._instance:
                cls._instance.language_changed.emit(lang)

    @classmethod
    def languages(cls):
        return [
            ("en", "English"),
            ("ja", "日本語"),
            ("zh", "中文"),
        ]
