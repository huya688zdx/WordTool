# WordAgent - AI 需求变更追踪系统

AI 驱动的需求变更分析系统：自动解析 Word 设计书，识别修改点，定位影响代码。

## 系统架构

```
                    ┌─────────────────┐
                    │   Word / PDF    │
                    └────────┬────────┘
                             │
                ┌────────────▼────────────┐
                │  Word COM → PDF 渲染    │  ← 视觉坐标系统
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  DOCX XML 结构解析      │  ← 语义结构系统
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  文本锚点映射引擎       │  ← 双系统对齐
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  段落 ↔ PDF 坐标映射    │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  高亮/修订检测          │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  章节层级视图 + 截图     │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  AI 需求分析            │
                └─────────────────────────┘
```

## 核心设计：双系统架构

系统的核心难点在于 DOCX 文件没有真实的页面坐标，只有 XML 语义结构。但截图需要像素级坐标。

**解决方案：双系统对齐**

| 系统 | 职责 | 技术 |
|------|------|------|
| 系统1：语义结构 | 段落、修订、高亮、章节层级 | python-docx + lxml |
| 系统2：视觉坐标 | 页面、坐标、截图 | Word COM + PyMuPDF |
| 映射层 | paragraph ↔ PDF bbox | 文本锚点定位 |

**映射算法：四策略级联**

1. **全文搜索**：短段落直接 `page.search_for(text)`，置信度 1.0
2. **分块搜索**：长段落按50字符分块，逐块搜索合并
3. **词序列模糊匹配**：取段落前10词，滑动窗口 + SequenceMatcher 兜底
4. **位置兜底**：当 PDF 文本不可搜索时（CJK 乱码），按垂直间隙聚类分配坐标

**章节层级**

基于标题样式（Heading 1-9 / 标题 1-9 / outlineLvl）自动构建章节树，支持：
- 可展开/折叠的层级视图
- 章节级别的合并截图（union bbox）
- 层级导航与快速定位

## 功能特性

- **桌面 GUI**（PySide6）：文档管理、段落/章节浏览、PDF 截图、AI 分析
- **REST API**（FastAPI）：文档上传、解析、渲染、对齐、查询
- **三语支持**：中文 / English / 日本語
- **多模型支持**：GPT-4o / DeepSeek / Gemini 等 OpenAI 兼容 API

## 目录结构

```
wordagent/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── config/
│   │   └── settings.py            # 配置管理
│   ├── api/
│   │   └── routes/
│   │       ├── documents.py       # 文档上传/查询
│   │       └── analysis.py        # 解析/渲染/对齐
│   ├── parser/                    # 系统1：语义结构
│   │   ├── docx_parser.py         # DOCX 结构解析（含标题检测）
│   │   ├── highlight_parser.py    # 高亮检测
│   │   ├── revision_parser.py     # 修订解析
│   │   ├── comment_parser.py      # 批注解析
│   │   └── style_analyzer.py      # 样式分析
│   ├── render/                    # 系统2：视觉坐标
│   │   ├── word_renderer.py       # Word COM 渲染
│   │   ├── pdf_parser.py          # PyMuPDF 解析
│   │   ├── text_anchor.py         # 核心：文本锚点映射
│   │   └── page_cropper.py        # 页面截图
│   ├── gui/                       # 桌面 GUI
│   │   ├── main_window.py         # 主窗口
│   │   ├── paragraph_view.py      # 章节树视图（QTreeWidget）
│   │   ├── coordinate_view.py     # 截图显示
│   │   ├── ai_analysis.py         # AI 分析面板
│   │   ├── llm_config.py          # LLM 配置
│   │   ├── i18n.py                # 国际化（中/英/日）
│   │   └── worker.py              # 后台流水线
│   ├── ai/
│   │   └── requirement_analyzer.py # AI 需求分析
│   ├── layout/
│   │   └── page_model.py          # 数据结构（含 SectionNode）
│   ├── models/                    # SQLAlchemy 模型
│   ├── schemas/                   # Pydantic Schema
│   ├── storage/
│   │   └── local_fs.py            # 本地文件存储
│   └── utils/
│       ├── text_normalize.py      # 文本归一化
│       ├── xml_helpers.py         # XML 工具
│       └── retry.py               # COM 重试装饰器
├── scripts/
│   ├── seed_test_data.py          # 生成测试 DOCX
│   └── test_full_pipeline.py      # 端到端测试
├── tests/
│   └── fixtures/                  # 测试文件
├── pyproject.toml
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+
- Microsoft Word（用于 COM 渲染）
- Windows 系统

### 安装

```bash
git clone https://github.com/huya688zdx/WordTool.git
cd wordagent

pip install -r requirements.txt
```

### 启动 GUI

```bash
set PYTHONPATH=.
python -m app.main
```

### 启动 API 服务

```bash
set PYTHONPATH=.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### API 使用

```bash
# 1. 上传文档
curl -X POST http://127.0.0.1:8000/documents/upload \
  -F "file=@design_doc.docx"

# 2. 运行完整流程（解析 → 渲染 → 对齐）
curl -X POST http://127.0.0.1:8000/documents/{document_id}/full-pipeline

# 3. 查询段落
curl http://127.0.0.1:8000/documents/{document_id}/paragraphs

# 4. 查询坐标映射
curl http://127.0.0.1:8000/documents/{document_id}/coordinates
```

## 数据库

使用 SQLite，数据文件位于 `data/wordagent.db`。

### 核心表

| 表 | 说明 |
|---|---|
| documents | 文档元信息和状态 |
| paragraphs | 段落（含样式、标题级别、高亮、修订标记） |
| runs | 文本 Run（最小格式单元） |
| pdf_coordinates | 段落 ↔ PDF 坐标映射 |

### 文档状态流转

```
uploaded → parsing → parsed → rendering → rendered → aligning → aligned
                                                            ↓
                                                          error
```

## 技术栈

| 功能 | 技术 |
|------|------|
| GUI | PySide6 |
| Word 渲染 | pywin32 (COM) |
| PDF 解析 | PyMuPDF |
| DOCX 解析 | python-docx + lxml |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy |
| 配置 | Pydantic Settings |
| AI | OpenAI 兼容 API（GPT-4o / DeepSeek / Gemini） |

## License

MIT
