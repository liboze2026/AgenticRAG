# 多模态检索与推理原型系统

基于 ColPali/ColQwen 视觉文档检索 + 商业多模态 API 生成的研究验证平台，用于论文中多模态检索实验的结果验证。

## 架构

- **后端**: FastAPI (Python 3.9+)
- **前端**: Vue 3 + Vite + TypeScript + Element Plus
- **向量数据库**: Qdrant (多向量 MaxSim)
- **文档编码**: ColPali/ColQwen (可切换)
- **生成模型**: GPT-4o / Claude API (可切换)
- **远程算力**: 通过 SSH 隧道访问 GPU 服务器

详见 `docs/superpowers/specs/2026-04-09-multimodal-retrieval-system-design.md`。

## 快速开始

### 1. 环境准备

**本地机器**:
- Python 3.9+ (Windows 用户注意: 使用 `py -3` 而非 `python`)
- Node.js 18+ 和 npm
- OpenSSH 客户端 (用于 SSH 隧道)

**远程 GPU 服务器**:
- CUDA 环境
- Python 3.9+
- 已部署 Qdrant 和 ColPali worker

### 2. 安装依赖

```bash
# 后端
py -3 -m pip install -r requirements.txt

# 前端
cd frontend
npm install
cd ..
```

### 3. 配置

复制环境变量模板并填写:

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY 和 ANTHROPIC_API_KEY
```

编辑 `config/default.yaml` 设置:
- `ssh_tunnel.pem_path`: SSH 私钥路径
- `ssh_tunnel.bastion`: 跳板机地址
- `ssh_tunnel.target`: GPU 服务器地址
- `server.cors_origins`: 允许的前端域名

### 4. 部署远程 Worker

在 GPU 服务器上启动 Qdrant 和 worker (参考 `scripts/deploy_worker.sh`):

```bash
# 在 GPU 服务器
docker run -d -p 6333:6333 qdrant/qdrant
py -3 -m uvicorn worker.main:app --host 0.0.0.0 --port 8001
```

### 5. 启动系统

**方式一: 自动启动 (推荐)**

`run.py` 会自动读取 `config/default.yaml` 并启动 SSH 隧道:

```bash
# 加载 .env 变量 (Windows)
$env:OPENAI_API_KEY=(Get-Content .env | Select-String 'OPENAI_API_KEY=').ToString().Split('=')[1]
# Linux/Mac
export $(cat .env | xargs)

py -3 run.py
```

**方式二: 手动启动**

```bash
# 终端 1: SSH 隧道
bash scripts/start_tunnel.sh

# 终端 2: 后端
py -3 run.py

# 终端 3: 前端开发服务器
cd frontend
npm run dev
```

打开 http://localhost:5173 访问前端。

## 使用指南

### 文档管理
- 上传 PDF 文件 (支持批量),系统自动提取页面图像并编码到 Qdrant
- 状态: pending → indexing → completed/failed

### 检索问答
- 输入自然语言问题,系统检索 Top-K 页面并调用多模态 API 生成回答
- 右侧显示检索证据 (页面缩略图 + 相关度)
- "仅检索" 模式用于调试检索质量

### 实验工作台
- **Pipeline 切换**: 动态切换 processor / encoder / retriever / reranker / generator
- **批量评测**: 上传评测数据 JSON 运行评测,自动计算 Recall@K 和 MRR
- **实验历史**: 每次评测自动持久化,支持回溯和对比

### 评测数据格式

见 `docs/examples/eval_sample.json`:

```json
[
  {
    "query": "什么是注意力机制？",
    "relevant": ["abc12345:3", "abc12345:4"]
  },
  {
    "query": "Transformer 架构的特点？",
    "relevant": ["def67890:1"]
  }
]
```

`relevant` 中的格式为 `{document_id}:{page_number}`,表示该问题的标准答案位于哪些文档的哪些页面。

## 切换 Pipeline 策略

通过修改 `config/default.yaml` 的 `pipeline` 节或在前端实验工作台切换:

```yaml
pipeline:
  processor: "page_screenshot"
  document_encoder:
    name: "colpali"
    options:
      model_name: "vidore/colpali-v1.2"
      batch_size: 8
  query_encoder: "colpali"
  retriever: "multi_vector"
  reranker: "score_filter"   # 可选
  generator: "openai_gpt4o"
```

## 添加新策略

1. 在 `backend/strategies/{processors|encoders|retrievers|rerankers|generators}/` 创建新文件
2. 继承对应的 `Base*` 接口
3. 用 `@*_registry.register("name")` 装饰器注册
4. 在对应的 `__init__.py` 导入新模块
5. 在配置文件中引用

## 测试

```bash
# 后端测试
py -3 -m pytest tests/ -v

# 前端构建验证
cd frontend && npm run build
```

## 项目结构

```
agent/
├── backend/          # FastAPI 后端
│   ├── api/          # HTTP 路由
│   ├── core/         # Pipeline, Registry, Config
│   ├── interfaces/   # 策略抽象接口
│   ├── models/       # Pydantic 数据模型
│   ├── services/     # 业务服务 (文档/评测/实验)
│   └── strategies/   # 可插拔策略实现
├── worker/           # 远程 GPU worker
├── frontend/         # Vue 3 前端
├── config/           # YAML 配置
├── scripts/          # SSH 隧道和部署脚本
├── tests/            # 测试套件
├── docs/             # 设计文档
└── run.py            # 主入口
```

## 故障排查

**`py -3` 命令不可用**: Windows 下确认安装了 Python Launcher (`py --version`)。Linux/Mac 可用 `python3` 替代。

**SSH 隧道失败**: 检查 `.pem` 文件权限 (`chmod 600`),确认跳板机和目标服务器地址正确。

**Worker 连接不上**: 确认端口转发正常:`curl http://localhost:8001/health`

**Qdrant 集合不存在**: `run.py` 会自动创建,若失败检查 Qdrant 是否启动:`curl http://localhost:6333/collections`
