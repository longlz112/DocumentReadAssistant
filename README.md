# 论文智能助手

基于大语言模型（通义千问 Qwen）的学术论文分析平台，支持论文上传、RAG 智能问答、多论文对比分析、知识图谱构建等功能，并提供完整的管理后台。

---

## 功能概览

### 用户端
| 功能 | 说明 |
|------|------|
| **论文管理** | 上传 PDF，自动提取标题、作者、摘要、关键词等元数据 |
| **智能问答** | 基于 RAG（检索增强生成）对单篇论文进行流式问答；摘要类问题自动走元数据通道，跳过向量检索 |
| **多论文对比** | 同时选中多篇论文，通过两阶段检索进行对比分析，结果流式输出 |
| **对话记忆** | 基于 MongoDB 持久化会话，大模型自动带入最近历史上下文 |
| **知识图谱** | 从论文全文抽取实体与关系，生成可交互的 ECharts 力导向图 |
| **会话历史** | 查看、导出（Markdown）、删除历史会话；支持一键「继续对话」恢复上下文 |
| **个人中心** | 修改昵称、邮箱、密码 |

### 管理后台
| 功能 | 说明 |
|------|------|
| **数据概览** | 用户数、论文数、7 日增长趋势 |
| **用户管理** | 搜索、启用/禁用、设置管理员权限 |
| **论文管理** | 批量确认元数据、标记已处理、关键词词频统计 |
| **系统监控** | 实时 CPU、内存、磁盘、网络指标 |
| **大模型消耗** | Token 用量趋势、操作分布、请求明细 |
| **操作日志** | 记录用户登录、上传、提问、删除等操作，支持筛选查询 |

---

## 技术栈

### 后端
- **框架**：Django 5.2 + Django REST Framework
- **LLM**：阿里云 DashScope（通义千问 `qwen-plus`）
- **LLM 编排**：LangChain / LangChain-Experimental
- **向量数据库**：Chroma（本地持久化，每篇论文独立索引）
- **文档嵌入**：DashScope `text-embedding-v4`
- **会话存储**：MongoDB（`pymongo`）
- **知识图谱**：LLMGraphTransformer → Neo4j（可选）
- **关系数据库**：SQLite（用户、论文、日志、LLM 记录）
- **认证**：Token 认证（DRF）
- **系统监控**：psutil

### 前端
- **框架**：Vue 3（Composition API）+ Vite 7
- **UI 组件库**：Element Plus 2
- **图表**：ECharts 6
- **PDF 预览**：PDF.js
- **Markdown 渲染**：marked + DOMPurify
- **HTTP 客户端**：Axios + 原生 Fetch（流式响应）
- **路由**：Vue Router 5

---

## 项目结构

```
.
├── back/                        # Django 后端
│   ├── api/
│   │   ├── models.py            # Paper / LLMUsageRecord / OperationLog
│   │   ├── views.py             # 用户端 API（论文、会话、问答）
│   │   ├── admin_views.py       # 管理后台 API
│   │   ├── ai_service.py        # LLM / RAG / 知识图谱核心逻辑
│   │   ├── mongo.py             # MongoDB 连接封装
│   │   ├── urls.py              # 用户端路由 /api/
│   │   └── admin_urls.py        # 管理端路由 /admin-api/
│   ├── paper_assistant/
│   │   ├── settings.py
│   │   └── urls.py
│   ├── chroma_db/               # 向量数据库（运行时生成）
│   ├── media/                   # 上传的 PDF 文件
│   ├── .env                     # 环境变量（不提交）
│   ├── .env.example
│   └── requirements.txt
│
└── front/                       # Vue 前端
    └── src/
        ├── api/
        │   ├── index.js         # 用户端 API 封装
        │   └── admin.js         # 管理端 API 封装
        ├── views/
        │   ├── Dashboard.vue    # 主工作台
        │   ├── Workspace.vue    # 单篇论文问答（流式）
        │   ├── MultiAnalysis.vue# 多论文对比分析（流式）
        │   ├── SessionList.vue  # 会话历史列表
        │   ├── SessionDetail.vue# 会话详情 + 继续对话
        │   ├── UserCenter.vue   # 个人中心
        │   └── admin/           # 管理后台页面
        ├── router/index.js
        └── main.js
```

---

## 快速开始

### 环境要求

| 软件 | 版本要求 |
|------|---------|
| Python | 3.11+ |
| Node.js | 20.19+ 或 22.12+ |
| MongoDB | 6.0+（本地或远程） |
| Neo4j | 5.x（可选，不配置则跳过知识图谱写入） |

### 1. 克隆项目

```bash
git clone <仓库地址>
cd <项目目录>
```

### 2. 后端配置

```bash
cd back

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DASHSCOPE_API_KEY 等配置项

# 初始化数据库
python manage.py migrate

# 创建超级管理员账号
python manage.py createsuperuser

# 启动开发服务器
python manage.py runserver
```

后端默认运行在 `http://localhost:8000`。

### 3. 前端配置

```bash
cd front

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:5173`。

---

## 环境变量说明

在 `back/.env` 中配置以下变量：

```env
# 必填：阿里云 DashScope API Key（用于 LLM 和嵌入模型）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# MongoDB 连接（用于会话历史存储）
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=paper_assistant

# Neo4j（可选，不填则知识图谱仅在前端展示，不写入图数据库）
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

## 核心流程说明

### 论文处理流程

```
上传 PDF
  → 保存文件（media/papers/）
  → 后台线程异步处理
    → PyPDFLoader 解析全文
    → 文本分块（1000字/块，150字重叠）
    → DashScope text-embedding-v4 向量化
    → 存入本地 Chroma 向量库（chroma_db/paper_{id}/）
    → LLM 提取元数据（标题、作者、摘要、关键词、期刊、年份）
    → 写入 SQLite
```

### 问答意图识别流程

```
用户提问
  → LLM 意图识别（是否摘要类问题）
  ├─ 是摘要类 → 直接读取 meta_abstract 字段 → LLM 作答（流式）
  └─ 否 → RAG 向量检索（Top-3）→ LLM 作答（流式）
```

### 多论文分析流程

```
用户选择多篇论文并提问
  → 阶段1：LLM 根据问题和各论文元数据生成 3-5 个检索关键词
  → 阶段2：并行检索各论文向量库，合并去重上下文
  → 阶段3：LLM 综合对比分析，流式输出结果
```

### 会话记忆机制

每次问答时，后端从 MongoDB 中读取该会话最近 6 条消息（3轮对话），拼入提示词的历史对话区，使模型感知上下文。

---

## API 接口概览

### 用户端 `/api/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/` | 登录 / 注册 |
| GET/POST | `/api/papers/` | 获取论文列表 / 上传论文 |
| DELETE | `/api/papers/{id}/` | 删除论文 |
| POST | `/api/papers/{id}/ask/` | 单论文问答（普通） |
| POST | `/api/papers/{id}/ask_stream/` | 单论文问答（SSE 流式） |
| POST | `/api/papers/analyze_multi/` | 多论文分析（普通） |
| POST | `/api/papers/analyze_multi_stream/` | 多论文分析（SSE 流式） |
| POST | `/api/papers/{id}/build_knowledge_graph/` | 触发知识图谱构建 |
| GET | `/api/papers/{id}/knowledge_graph/` | 获取知识图谱数据 |
| GET/POST | `/api/sessions/` | 会话列表 / 新建会话 |
| GET | `/api/sessions/{id}/` | 会话详情（含消息） |
| POST | `/api/sessions/{id}/add_message/` | 追加消息 |

### 管理端 `/admin-api/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin-api/auth/login/` | 管理员登录 |
| GET | `/admin-api/stats/` | 数据概览 |
| GET/PUT | `/admin-api/users/` | 用户列表 / 修改状态 |
| GET | `/admin-api/papers/` | 论文列表 |
| GET | `/admin-api/system/` | 系统监控 |
| GET | `/admin-api/llm/stats/` | LLM 用量统计 |
| GET | `/admin-api/llm/records/` | LLM 调用记录 |
| GET | `/admin-api/logs/` | 操作日志 |

---

## 注意事项

- **CORS**：开发环境已开启 `CORS_ALLOW_ALL_ORIGINS = True`，生产环境请替换为白名单配置。
- **SECRET_KEY**：`settings.py` 中的密钥仅供开发使用，生产部署前必须替换。
- **SQLite**：适合单机开发，高并发生产环境建议迁移至 PostgreSQL。
- **流式响应**：前端使用原生 `fetch` + `ReadableStream` 读取 SSE，Nginx 反代需关闭缓冲（`proxy_buffering off`）。
- **Neo4j 可选**：不配置 `NEO4J_PASSWORD` 时，知识图谱构建结果仅缓存在 SQLite JSONField 中，前端仍可正常展示。
