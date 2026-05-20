# WordAgent - AI 需求变更追踪系统

AI 驱动的需求变更分析系统：自动解析 Word 设计书，识别修改点，恢复完整段落，理解需求语义，关联代码仓库，定位影响代码，生成修改建议。

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
                │  截图 + AI 分析         │
                └─────────────────────────┘
```

## 核心设计：双系统架构

系统的核心难点在于 DOCX 文件没有真实的页面坐标，只有 XML 语义结构（paragraph、run、style）。但截图需要像素级坐标。

**解决方案：双系统对齐**

| 系统 | 职责 | 技术 |
|------|------|------|
| 系统1：语义结构 | 段落、修订、高亮、批注 | python-docx + lxml |
| 系统2：视觉坐标 | 页面、坐标、截图 | Word COM + PyMuPDF |
| 映射层 | paragraph ↔ PDF bbox | 文本锚点定位 |

**映射算法：三策略级联**

1. **Strategy 1 - 全文搜索**：短段落直接 `page.search_for(text)`，置信度 1.0
2. **Strategy 2 - 分块搜索**：长段落按50字符分块，逐块搜索合并，支持跨页
3. **Strategy 3 - 词序列模糊匹配**：取段落前10词，滑动窗口 + SequenceMatcher 兜底

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
│   │   ├── docx_parser.py         # DOCX 结构解析
│   │   ├── highlight_parser.py    # 高亮检测
│   │   ├── revision_parser.py     # 修订解析
│   │   ├── comment_parser.py      # 批注解析
│   │   └── style_analyzer.py      # 样式分析
│   ├── render/                    # 系统2：视觉坐标
│   │   ├── word_renderer.py       # Word COM 渲染
│   │   ├── pdf_parser.py          # PyMuPDF 解析
│   │   ├── text_anchor.py         # 核心：文本锚点映射
│   │   └── page_cropper.py        # 页面截图
│   ├── layout/
│   │   └── page_model.py          # 数据结构
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

- Python 3.8+
- Microsoft Word（已安装，用于 COM 渲染）
- Windows 系统

### 安装

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/wordagent.git
cd wordagent

# 安装依赖
pip install python-docx lxml pymupdf pywin32 fastapi uvicorn sqlalchemy pydantic pydantic-settings python-multipart
```

### 启动服务

```bash
# 设置 Python 路径并启动
set PYTHONPATH=.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### API 使用

```bash
# 1. 上传文档
curl -X POST http://127.0.0.1:8000/documents/upload \
  -F "file=@design_doc.docx"

# 返回: {"document_id": "xxx", "filename": "design_doc.docx", "status": "uploaded"}

# 2. 运行完整流程（解析 → 渲染 → 对齐）
curl -X POST http://127.0.0.1:8000/documents/{document_id}/full-pipeline

# 返回: {"status": "aligned", "parse": {...}, "render": {...}, "align": {...}}

# 3. 查询段落
curl http://127.0.0.1:8000/documents/{document_id}/paragraphs

# 4. 查询坐标映射
curl http://127.0.0.1:8000/documents/{document_id}/coordinates
```

### 测试脚本

```bash
# 生成测试 DOCX 文件
python scripts/seed_test_data.py

# 运行端到端测试
PYTHONPATH=. python scripts/test_full_pipeline.py
```

## 数据库

Phase 1 使用 SQLite，数据文件位于 `data/wordagent.db`。

### 核心表

| 表 | 说明 |
|---|---|
| documents | 文档元信息和状态 |
| paragraphs | 段落（含样式、高亮、修订标记） |
| runs | 文本 Run（最小格式单元） |
| pdf_coordinates | 段落 ↔ PDF 坐标映射 |

### 文档状态流转

```
uploaded → parsing → parsed → rendering → rendered → aligning → aligned
                                                            ↓
                                                          error（任何阶段可进入）
```

## 技术栈

| 功能 | 技术 |
|------|------|
| Word 渲染 | pywin32 (COM) |
| PDF 解析 | PyMuPDF |
| DOCX 解析 | python-docx + lxml |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy |
| 配置 | Pydantic Settings |

## 后续规划

- **Phase 2**：AI 需求语义分析（GPT-4 / Gemini）
- **Phase 3**：代码索引 + 向量召回（AST + FAISS）
- **Phase 4**：Patch 生成（libcst）

## License

MIT
