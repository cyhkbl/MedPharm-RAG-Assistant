# MedDistill — 医学教材知识蒸馏智能体

## 项目概述

为全栈极速黑客松开发的医学教材知识整合系统。目标：将7本医学教材压缩到≤30%精华，构建可视化知识图谱，实现RAG精准问答，支持多轮对话迭代优化。**追求第一。**

## 技术栈

- **后端**: Python 3.11 + FastAPI + Uvicorn
- **前端**: React 18 + TypeScript + Vite
- **知识图谱可视化**: ECharts 5 (graph + sankey + heatmap 多视图)
- **向量数据库**: ChromaDB (嵌入式，零配置)
- **Embedding**: BGE-small-zh-v1.5 (sentence-transformers，本地运行，免费，中文优化)
- **PDF解析**: PyMuPDF (fitz) — 逐页解析，正则+字号识别章节
- **LLM调用**: 通过 LiteLLM 代理 (https://litellm.cyhkbl.qzz.io) 调用 mimo-v2.5-pro
- **部署**: 赛方推荐方式 — 魔搭创空间（免费 CPU，支持 Gradio/Streamlit）或 Vercel + Railway 组合
  - 后端 API 部署到 Railway / Render / 魔搭创空间
  - 前端静态文件部署到 Vercel / 魔搭创空间
  - 若需长期运行的后端服务（如向量索引、embedding），优先 Railway 或 Render（支持持久化）
  - 开发阶段在 WSL 本机运行调试

## 目录结构

```
MedDistill/
├── CLAUDE.md                    # 本文件 — Claude Code 项目指南
├── README.md                    # 项目说明（可复现性）
├── .gitignore                   # 排除 PDF、data/、__pycache__ 等
├── .dockerignore                # Docker 构建排除
├── docker-compose.yml           # 一键部署配置
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖
├── package.json                 # 前端依赖（如有独立前端）
│
├── backend/
│   ├── main.py                  # FastAPI 入口（含 trace ID 中间件）
│   ├── config.py                # 配置管理（从 .env 读取）
│   ├── middleware.py            # API Key 认证中间件
│   ├── logging_config.py        # 结构化日志配置
│   ├── api/
│   │   ├── upload.py            # 文件上传与解析 API（含 magic bytes 校验）
│   │   ├── knowledge_graph.py   # 知识图谱构建与查询 API
│   │   ├── integration.py       # 跨教材整合 API
│   │   ├── rag.py               # RAG 索引（增量）与问答 API
│   │   ├── dialogue.py          # 多轮对话 API
│   │   └── report.py            # 整合报告生成 API
│   ├── core/
│   │   ├── parser/
│   │   │   ├── pdf_parser.py    # PDF 解析（章节识别、页眉过滤）
│   │   │   ├── md_parser.py     # Markdown 解析
│   │   │   ├── txt_parser.py    # TXT 解析
│   │   │   └── docx_parser.py   # Word 解析（加分）
│   │   ├── kg/
│   │   │   ├── extractor.py     # LLM 知识点提取（健壮 JSON 解析）
│   │   │   ├── graph_builder.py # 知识图谱构建
│   │   │   ├── aligner.py       # 跨教材语义对齐（Embedding + LLM 双重）
│   │   │   └── integrator.py    # 整合决策引擎（merge/keep/remove）
│   │   ├── rag/
│   │   │   ├── chunker.py       # 文档分块（段落感知 + 章节前缀注入）
│   │   │   ├── embedder.py      # 向量嵌入
│   │   │   ├── vectorstore.py   # ChromaDB 封装
│   │   │   ├── retriever.py     # 混合检索（向量 + BM25 + 查询扩展）
│   │   │   └── generator.py     # RAG 回答生成（编号引用解析）
│   │   └── llm/
│   │       ├── client.py        # LLM 调用封装（并发控制 + 智能重试）
│   │       └── prompts.py       # 所有 Prompt 模板
│   ├── models/
│   │   ├── schemas.py           # Pydantic 数据模型
│   │   └── database.py          # 本地数据持久化（原子写入）
│   └── utils/
│       ├── text_utils.py        # 文本清理、计数
│       └── benchmark.py         # RAG 评测工具
│
├── frontend/
│   ├── index.html               # 入口
│   ├── src/
│   │   ├── App.tsx              # 主应用（SPA 布局）
│   │   ├── components/
│   │   │   ├── FileUpload.tsx   # 左侧：教材上传管理
│   │   │   ├── KnowledgeGraph.tsx  # 中间：ECharts 图谱可视化
│   │   │   ├── IntegrationPanel.tsx # 右侧：整合操作面板
│   │   │   ├── RAGChat.tsx      # RAG 问答界面
│   │   │   ├── Dialogue.tsx     # 多轮对话界面
│   │   │   └── Report.tsx       # 整合报告展示
│   │   ├── hooks/               # React Hooks
│   │   ├── api/                 # API 调用封装
│   │   └── styles/              # 全局样式
│   └── vite.config.ts
│
├── docs/
│   ├── 需求分析.md
│   ├── 系统设计.md
│   ├── Agent架构说明.md         # 核心评分文档
│   └── 接口文档.md
│
├── report/
│   └── 整合报告.md              # 7本教材整合报告
│
└── data/                        # 本地数据（gitignore）
    ├── textbooks/               # 教材文件（不上传）
    ├── parsed/                  # 解析后的结构化数据
    ├── kg/                      # 知识图谱数据
    └── vectors/                 # 向量索引
```

## 核心 API 设计

### 文件解析
- `POST /api/upload` — 上传教材文件，返回解析结果
- `GET /api/textbooks` — 获取已上传教材列表
- `GET /api/textbooks/{id}/chapters` — 获取章节结构

### 知识图谱
- `POST /api/kg/build/{textbook_id}` — 为单本教材构建知识图谱
- `GET /api/kg/{textbook_id}` — 获取单本教材图谱数据（nodes + edges）
- `GET /api/kg/all` — 获取所有教材的合并图谱

### 跨教材整合
- `POST /api/integrate` — 执行跨教材整合（语义对齐 + 决策）
- `GET /api/integrate/decisions` — 获取整合决策列表
- `POST /api/integrate/override` — 用户手动覆盖整合决策
- `GET /api/integrate/stats` — 压缩比统计

### RAG 问答
- `POST /api/rag/index` — 建立/增量更新向量索引（支持 `?force_rebuild=true`）
- `POST /api/rag/query` — 提问，返回带引用的回答
- `GET /api/rag/status` — 索引状态

### 多轮对话
- `POST /api/dialogue/chat` — 发送消息（支持上下文）
- `GET /api/dialogue/history` — 获取对话历史

### 报告
- `GET /api/report` — 获取整合报告数据

## 关键技术决策

### 1. PDF 章节识别策略
- 主策略：正则匹配 `第[一二三四五六七八九十百]+章`、`Chapter \d+` 等模式
- 辅策略：检测字号突变（大号字 = 标题）
- 页眉页脚过滤：识别重复出现的页码、书名行
- 大文件处理：逐页解析，chunk 迭代，不一次性加载

### 2. 知识图谱提取 Prompt 设计
- 每次只处理一个章节（避免上下文过长）
- Few-shot 示例引导
- 严格 JSON 输出格式约束
- 防幻觉：要求引用原文定位

### 3. 跨教材语义对齐 — 双重策略
- **第一层**：Embedding 余弦相似度 ≥ 0.85 → 候选对
- **第二层**：LLM 判断候选对是否真正等价（处理"白细胞"="白血细胞"="leukocyte"）
- 阈值可调，前端支持用户手动修正

### 4. RAG Pipeline
- **分块**：1000字/chunk，150字重叠，段落感知切分 + 章节标题前缀注入
- **Embedding**：BGE-small-zh-v1.5（中文优化，本地运行）
- **检索**：向量 Top-10（含查询扩展）+ BM25 Top-10 → RRF 融合 → Top-5
- **生成**：严格 Prompt 约束 — 只用上下文，编号引用 [1][2] 映射回来源
- **索引**：增量更新（content hash 检测变更），支持 `force_rebuild` 全量重建

### 5. 压缩策略
- 相似度 ≥ 0.85 的知识点 → merge（保留最完整版本）
- 高度重复（3本以上出现）→ 保留1个 + 删除其余
- 唯一知识点 → keep
- 目标：总字数 ≤ 原始30%

## 开发约定

### 代码风格
- Python: type hints 全量，Google docstring，ruff 格式化
- TypeScript: 严格模式，函数式组件，hooks 优先
- 中文注释（因为是医学教材系统）

### Git 提交规范
- feat: 新功能
- fix: 修复
- docs: 文档
- refactor: 重构
- style: 样式

### API Key 配置
通过 .env 文件配置，不在代码中硬编码：
```
LITELLM_API_KEY=sk-lit...2026
LITELLM_BASE_URL=https://litellm.cyhkbl.qzz.io
LITELLM_MODEL=mimo-v2.5-pro
API_KEY=                 # 可选，空=无认证(开发模式)
```

### 日志配置
- 开发模式：人类可读格式（默认）
- 生产模式：`LOG_FORMAT=json` 启用结构化 JSON 日志
- 每个请求自动分配 `X-Trace-ID`，可在响应头中查看

### Claude Code 设置文件
Claude Code 使用独立的模型配置（与应用本身的 LLM 调用无关）：
- 优先使用: `~/.claude/settings.openai.json` (GPT-5.5 via LiteLLM)
- 备用: `~/.claude/settings.json` (默认配置)
- 所有编码任务必须通过 Claude Code 完成（print mode 或 tmux interactive）

## 部署方案

### 开发阶段
- WSL 本机运行（后端 `uvicorn` + 前端 `vite dev`），快速迭代调试

### 生产部署：赛方推荐方式
1. **后端 API** → Railway 或 Render（免费 tier，支持 Python 长驻服务）
   - 包含 FastAPI + ChromaDB 向量索引 + Embedding 模型
   - 环境变量通过平台 dashboard 配置（LITELLM_API_KEY 等）
2. **前端** → Vercel（免费，全球 CDN，自动 HTTPS）
   - Vite build 产出静态文件，零配置部署
   - API 请求通过环境变量 `VITE_API_URL` 指向后端地址
3. **备选：魔搭创空间**（ModelScope 免费 CPU）
   - 适合打包为 Gradio/Streamlit 单体应用
   - 局限：无持久化存储，重启丢失索引；但教材可重新上传构建

### 端口规划（本地开发）
- 后端 API: 8100
- 前端 dev server: 8200

## 评分攻略（100分目标分解）

| 维度 | 目标分 | 关键动作 |
|------|--------|----------|
| A 文档 (15) | 14+ | README可复现、需求分析深入、系统设计有图、整合报告完整 |
| B 功能 (25) | 23+ | 全格式解析、完整RAG pipeline、混合检索+Rerank、多轮对话修改决策 |
| C 可视化 (13) | 12+ | ECharts 多视图（力导向+桑基+热力图）、搜索/筛选/悬停、频次映射 |
| D 架构 (20) | 18+ | Mermaid架构图、设计决策论证、RAG量化对比实验、Prompt工程文档 |
| E 代码 (17) | 16+ | 模块化彻底、类型注解完整、Docker一键部署、.env.example |
| F 创新 (10) | 8+ | 多视图切换、RAG Benchmark、Token统计、学习路径推荐 |
| P2 附加 | +10 | RAG分块策略对比实验报告（飞书文档） |

## 执行顺序

1. **Phase 1**: 后端骨架 + 文件解析（PDF/MD/TXT）
2. **Phase 2**: 知识图谱提取 + ECharts 可视化
3. **Phase 3**: 跨教材语义对齐 + 整合决策 + 压缩
4. **Phase 4**: RAG Pipeline（分块+嵌入+检索+生成）
5. **Phase 5**: 多轮对话 + 整合报告
6. **Phase 6**: 前端完善 + Docker 部署
7. **Phase 7**: 文档（需求分析、系统设计、Agent架构说明）
8. **Phase 8**: RAG Benchmark + P2 技术报告
