# MedPharm RAG Assistant

医学教材知识整合智能体：将 7 本教材压缩到 30% 精华，并提供基于教材来源的 RAG 精准问答。

## 功能特性

- 多格式教材上传与解析：支持 PDF、DOCX、TXT、Markdown。
- 章节结构识别：按页解析正文，保留章节、页码和字数统计。
- LLM 知识点抽取：从教材章节中抽取概念、方法、规律和现象。
- 知识图谱构建：生成知识节点和 prerequisite、contains、parallel、applies_to 等关系。
- 跨教材语义对齐：Embedding 初筛 + LLM 精确验证，识别同义和高度重复知识。
- 智能压缩整合：输出 merge、keep、remove 决策，目标压缩比 ≤ 30%。
- RAG 精准问答：混合检索（向量 + BM25 + RRF）并返回教材、章节、页码引用。
- 多轮对话优化：教师可通过对话反馈修改整合偏好。
- 可视化工作台：React + ECharts 展示知识图谱、整合统计、问答和报告。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+、FastAPI、Uvicorn、Pydantic |
| 前端 | React 18、TypeScript、Vite |
| PDF 解析 | PyMuPDF |
| LLM | LiteLLM 代理 + mimo-v2.5-pro |
| Embedding | BGE-small-zh-v1.5 |
| 向量数据库 | ChromaDB |
| 关键词检索 | rank-bm25 |
| 可视化 | ECharts、echarts-for-react |
| 存储 | JSON 文件 + ChromaDB 本地持久化 |

## 环境依赖

- Python 3.11+
- Node.js 18+
- npm 9+

## 安装步骤

### 1. 克隆并进入项目

```bash
cd /home/henry/tempprojects/hackathlon
```

### 2. 安装后端依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

`.env` 字段说明：

| 字段 | 说明 | 默认值 |
|---|---|---|
| LITELLM_API_KEY | LiteLLM API Key | sk-lit-your-key-here |
| LITELLM_BASE_URL | LiteLLM 服务地址 | https://litellm.cyhkbl.qzz.io |
| LITELLM_MODEL | LLM 模型名 | mimo-v2.5-pro |
| EMBEDDING_MODEL | 本地 Embedding 模型 | BAAI/bge-small-zh-v1.5 |
| BACKEND_HOST | 后端监听地址 | 0.0.0.0 |
| BACKEND_PORT | 后端端口 | 8100 |
| FRONTEND_URL | 前端地址，用于 CORS | http://localhost:8200 |
| DATA_DIR | 本地数据目录 | ./data |

前端也可配置 `frontend/.env`：

```bash
VITE_API_URL=http://localhost:8100
```

## 启动命令

### 后端

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8100 --reload
```

后端 API 文档：

```text
http://localhost:8100/docs
```

### 前端

```bash
cd frontend
npm run dev
```

前端访问地址：

```text
http://localhost:8200
```

## Docker 一键部署

若项目根目录存在 `docker-compose.yml`，可使用：

```bash
docker compose up --build
```

推荐容器环境变量：

```env
LITELLM_API_KEY=sk-lit-your-key-here
LITELLM_BASE_URL=https://litellm.cyhkbl.qzz.io
LITELLM_MODEL=mimo-v2.5-pro
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
DATA_DIR=/app/data
FRONTEND_URL=http://localhost:8200
```

若未使用 Docker，直接按“启动命令”分别启动后端和前端即可。

## 使用说明

1. 打开前端页面 `http://localhost:8200`。
2. 上传 7 本医学教材文件。
3. 等待系统解析章节并生成结构化教材 JSON。
4. 对每本教材构建知识图谱。
5. 执行跨教材整合，查看 merge、keep、remove 决策和压缩比。
6. 如有需要，通过前端手动覆盖整合决策。
7. 构建 RAG 索引。
8. 在问答窗口提问，检查答案和引用来源。
9. 查看报告页面，导出或展示整合结果。

## 项目结构

```text
hackathlon/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 环境变量配置
│   ├── api/                     # 上传、图谱、整合、RAG、对话、报告接口
│   ├── core/
│   │   ├── parser/              # PDF/DOCX/TXT/Markdown 解析
│   │   ├── kg/                  # 知识抽取、图谱构建、语义对齐、整合
│   │   ├── rag/                 # 分块、Embedding、向量库、检索、生成
│   │   └── llm/                 # LLM 客户端和 Prompt
│   ├── models/                  # Pydantic 模型和本地数据操作
│   └── utils/                   # 文本工具和 Benchmark
├── frontend/
│   ├── src/
│   │   ├── components/          # 上传、图谱、整合、问答、对话、报告组件
│   │   └── api/                 # 前端 API 客户端
│   └── package.json
├── docs/
│   ├── 需求分析.md
│   ├── 系统设计.md
│   └── Agent架构说明.md
├── data/                        # 本地数据与索引，默认不提交
├── requirements.txt
├── .env.example
└── README.md
```

## API 文档

启动后端后访问：

```text
http://localhost:8100/docs
```

主要接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/upload | 上传并解析教材 |
| GET | /api/textbooks | 获取教材列表 |
| GET | /api/textbooks/{id}/chapters | 获取章节结构 |
| DELETE | /api/textbooks/{id} | 删除教材 |
| POST | /api/kg/build/{id} | 构建单本教材知识图谱 |
| GET | /api/kg/{id} | 获取单本教材图谱 |
| GET | /api/kg/all | 获取合并图谱 |
| POST | /api/integrate | 执行跨教材整合 |
| GET | /api/integrate/decisions | 获取整合决策 |
| POST | /api/integrate/override | 手动覆盖整合决策 |
| GET | /api/integrate/stats | 获取压缩统计 |
| POST | /api/rag/index | 构建 RAG 索引 |
| POST | /api/rag/query | RAG 问答 |
| GET | /api/rag/status | 获取索引状态 |
| POST | /api/dialogue/chat | 多轮对话 |
| GET | /api/dialogue/history | 获取对话历史 |
| GET | /api/report | 获取整合报告 |

## 设计文档

- [需求分析](docs/需求分析.md)
- [系统设计](docs/系统设计.md)
- [Agent 架构说明](docs/Agent架构说明.md)

## 开源许可

本项目用于黑客松竞赛展示和教学研究。若后续开源，建议采用 MIT License；在正式发布前请确认教材数据、模型服务和第三方依赖的授权边界。

