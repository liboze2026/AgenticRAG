# 多模态检索与推理原型系统设计文档

## 概述

构建一个模块化、可插拔的多模态文档检索与推理系统，用于验证论文中多模态检索实验的结果。系统基于双塔架构，支持灵活切换检索策略、编码模型和生成模型，便于研究实验对比。

### 核心特征

- **数据源**：PDF 文档（包含文本、图像、表格）
- **检索方案**：以 ColPali/ColQwen 视觉文档检索为基础，支持策略替换
- **生成方案**：商业多模态 API（GPT-4o / Claude 等）
- **架构风格**：双塔 + 管道（Pipeline），模块可插拔
- **技术栈**：FastAPI 后端 + Vue 前端 + Qdrant 向量数据库
- **数据规模**：上千篇 PDF

---

## 1. 部署架构

### 1.1 拓扑

```
┌──────────────────────────────┐
│         本地机器               │
│  ┌───────┐  ┌──────────────┐ │
│  │  Vue  │  │  FastAPI 主服务│ │
│  │ 前端   │  │  (调度/API)   │ │
│  └───────┘  └──────┬───────┘ │
└────────────────────┼─────────┘
                     │ SSH 隧道 (pem → 跳板机 → GPU服务器)
┌────────────────────▼─────────┐
│       远程 GPU 服务器          │
│  ┌──────────────────────────┐│
│  │  Worker API (FastAPI)    ││
│  │  - 模型编码推理           ││
│  │  端口: 8001              ││
│  └──────────────────────────┘│
│  ┌──────────────────────────┐│
│  │  Qdrant                  ││
│  │  端口: 6333              ││
│  └──────────────────────────┘│
└──────────────────────────────┘
```

### 1.2 通信方案

通过 SSH 端口转发经跳板机建立隧道，主服务访问 `localhost` 映射端口：

```bash
ssh -i key.pem -J user@跳板机 user@服务器 \
    -L 8001:localhost:8001 \
    -L 6333:localhost:6333 \
    -N
```

### 1.3 配置

```yaml
worker:
  host: "localhost"
  port: 8001

qdrant:
  host: "localhost"
  port: 6333

ssh_tunnel:
  enabled: true
  pem_path: "~/.ssh/key.pem"
  bastion: "user@跳板机地址"
  target: "user@服务器地址"
  forwards:
    - local: 8001
      remote: 8001
    - local: 6333
      remote: 6333
```

---

## 2. 核心模块设计

### 2.1 抽象接口体系

每层定义抽象基类，具体实现可替换：

- **BaseProcessor**：文档处理（页面截图 / PDF解析 / 混合）
- **BaseEncoder**：编码器（ColPali / ColQwen / CLIP / BGE 等），双塔共用接口
  - `encode_documents(inputs) -> List[Embedding]`
  - `encode_query(query: str) -> Embedding`
- **BaseRetriever**：检索器（多向量 MaxSim / 单向量余弦 / 混合）
  - `retrieve(query, top_k) -> List[RetrievalResult]`
- **BaseReranker**：重排序器（可选环节，如 Cross-Encoder）
- **BaseGenerator**：生成器（GPT-4o / Claude / 本地多模态模型）
  - `generate(query, context: List[RetrievalResult]) -> Answer`

### 2.2 Pipeline 编排

通过 YAML 配置组装 Pipeline：

```yaml
pipeline:
  processor: "page_screenshot"
  document_encoder: "colpali"
  query_encoder: "colpali"
  retriever: "multi_vector"
  reranker: null
  generator: "openai_gpt4o"
```

### 2.3 策略注册机制

注册表模式，新增策略只需实现接口 + 装饰器注册：

```python
@register_encoder("colpali")
class ColPaliEncoder(BaseEncoder): ...
```

Pipeline 根据配置字符串自动实例化对应实现。

---

## 3. 数据流

### 3.1 索引流（上传 PDF 时触发，异步执行）

```
PDF上传 → Processor(按页截图/解析) → Document Encoder(远程Worker)
    → Qdrant存储向量 + 文件系统存储原始页面图像
```

### 3.2 查询流（用户提问时触发）

```
Query → Query Encoder(远程Worker) → Retriever(Qdrant检索)
    → [Reranker(可选)] → 取回Top-K页面图像+元数据
    → Generator(商业API, query+图像) → 回答
```

---

## 4. API 设计

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/documents/upload | 上传PDF，触发异步索引 |
| GET | /api/documents | 文档列表 |
| GET | /api/documents/{id}/status | 索引进度 |
| DELETE | /api/documents/{id} | 删除文档及其索引 |

### 检索问答

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/query | 提问，返回回答+检索证据 |
| POST | /api/retrieve | 仅检索，不生成（实验调试用） |

### 实验管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/pipelines | 查看可用Pipeline配置 |
| PUT | /api/pipelines/active | 切换当前Pipeline策略 |
| POST | /api/experiments/evaluate | 批量评测（计算Recall@K、MRR等） |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查（含Worker状态） |

---

## 5. 前端页面

### 5.1 文档管理页

- PDF 上传（支持批量）
- 文档列表 + 索引状态（进行中/完成/失败）
- 文档预览 + 删除

### 5.2 检索问答页

- 输入框（提问）
- 回答展示区
- 检索证据面板（Top-K 页面缩略图 + 相关度分数，点击可放大）

### 5.3 实验工作台

- Pipeline 配置切换（下拉选择各模块策略）
- 仅检索模式（查看检索结果，不走生成）
- 批量评测（上传 query 集 + ground truth，展示指标）
- 结果对比（不同策略的指标对比表/图表）

### 5.4 系统状态页

- Worker 连接状态
- Qdrant 状态
- 已索引文档统计

---

## 6. 项目目录结构

```
agent/
├── config/
│   ├── default.yaml
│   └── experiments/
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── documents.py
│   │   ├── query.py
│   │   ├── experiments.py
│   │   └── system.py
│   ├── core/
│   │   ├── pipeline.py
│   │   ├── registry.py
│   │   └── config.py
│   ├── interfaces/
│   │   ├── processor.py
│   │   ├── encoder.py
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── generator.py
│   ├── strategies/
│   │   ├── processors/
│   │   │   └── page_screenshot.py
│   │   ├── encoders/
│   │   │   ├── colpali.py
│   │   │   └── colqwen.py
│   │   ├── retrievers/
│   │   │   └── multi_vector.py
│   │   ├── rerankers/
│   │   └── generators/
│   │       ├── openai_gpt4o.py
│   │       └── claude.py
│   ├── services/
│   │   ├── document_service.py
│   │   ├── worker_client.py
│   │   └── evaluation.py
│   └── models/
│       └── schemas.py
├── worker/
│   ├── main.py
│   ├── model_manager.py
│   └── endpoints/
│       └── encode.py
├── frontend/
│   └── (Vue 项目)
├── scripts/
│   ├── start_tunnel.sh
│   └── deploy_worker.sh
├── tests/
├── requirements.txt
└── README.md
```

---

## 7. 技术选型汇总

| 层次 | 选型 |
|------|------|
| 后端框架 | FastAPI |
| 前端框架 | Vue 3 |
| 向量数据库 | Qdrant |
| 文档编码 | ColPali / ColQwen（可切换） |
| 生成模型 | GPT-4o / Claude API（可切换） |
| 远程通信 | SSH 端口转发 |
| 异步任务 | FastAPI BackgroundTasks（后续可升级 Celery） |
| 配置管理 | YAML |
