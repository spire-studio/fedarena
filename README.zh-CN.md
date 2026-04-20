<div align="center">
  <img src="icon.png" alt="FedArena" width="360" />
  <br />
  <p><em>面向联邦学习安全研究的标准化攻防评测平台</em></p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React">
    <img src="https://img.shields.io/badge/PyTorch-2.5-EE4C2C?logo=pytorch&logoColor=white" alt="PyTorch">
    <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  </p>
  <p>
    <a href="./README.md">English</a> | <strong>简体中文</strong>
  </p>
</div>

---

**FedArena** 是一个联邦学习安全研究平台。研究人员可以通过自然语言描述或直接提交代码的方式，提交新的攻击/防御算法，系统会自动评测并与基准矩阵对比排名。

基于 **FastAPI + React + PyTorch** 构建，集成 OpenAI 兼容 LLM 接口，支持自然语言驱动的代码生成和实验规划。

## 动态

- **2026-04-16** — Web UI 上线：Leaderboard、Arena（Prompt + 代码上传）、Bench（自然语言实验执行）三个标签页。
- **2026-04-15** — 新增防御端提交通道，攻防双向对称。
- **2026-04-15** — 移除 AutoResearch，FedArena 定位为纯 Arena 平台。

## 核心功能

**Arena** — 提交新的攻击或防御算法（自然语言描述或粘贴代码）。系统自动生成实现、校验、评测并排名。

**Bench** — 用自然语言描述实验（如"对比 IPM 和 Scaling 在 Krum 和 Median 上的效果"）。系统解析意图，规划 M×N 实验矩阵，顺序执行，输出结果表。

**排行榜** — 用户提交与基线方法统一排名，支持"Compare in Matrix"将任意提交叠加到基准热力图上对比。

**LLM Agent** — OpenAI 兼容接口。Agent 根据自然语言描述生成攻防代码，通过 AST 分析校验，自动触发评测。

**CLI 模式** — 所有功能也可通过 Claude Code skills（`/fedarena_arena`、`/fedarena_bench`）或直接调用 Python 模块使用，无需 Web UI。

## 使用示例

```
Arena prompt: "设计一个根据全局模型梯度范数自适应缩放投毒更新的攻击"
→ Agent 生成代码 → AST 校验 → 对 7 个防御评测 → 排名上榜
```

```
Bench prompt: "对比 IPM 和 Scaling 在 Krum 和 Median 上的效果"
→ 解析为 2×2 = 4 个实验 → 顺序执行 → 结果表
```

```python
# 也可以直接提交代码：
class MyAttack(ResearchAttackStrategy):
    method_name = "arena_attack_my_method"
    def attack(self, local_model_params, global_model_params, **kwargs):
        return poisoned_params
```

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│                    React + Vite 前端                          │
│         (排行榜 · Arena · Bench · 详情页)                     │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST + 轮询
┌───────────────────────────▼──────────────────────────────────┐
│                      FastAPI 后端                             │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────┐     │
│   │ LLM Agent    │  │  提交校验    │  │  Bench Worker  │     │
│   │ (代码生成)   │  │  (AST 分析)  │  │ (M×N 执行器)   │     │
│   └──────┬───────┘  └──────┬───────┘  └───────┬────────┘     │
│          │                 │                  │              │
│   ┌──────▼─────────────────▼──────────────────▼──────────┐   │
│   │              Arena 评测引擎                           │   │
│   │    (注册表 · 执行器 · 矩阵 · 排名)                   │   │
│   └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│   ┌──────────────┐    ┌──────▼───────┐    ┌──────────────┐   │
│   │   SQLite     │    │  fl_core     │    │ OpenAI API   │   │
│   │ (任务/提交)  │    │ (FL 引擎)    │    │ (LLM 调用)   │   │
│   └──────────────┘    └──────────────┘    └──────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 环境配置

```bash
git clone git@github.com:spire-studio/fedarena.git
cd fedarena
uv sync
```

如需使用 LLM Agent（Prompt 模式），创建 `.env` 文件：
```bash
cp .env.example .env
# 编辑 .env，设置：
#   OPENAI_API_KEY=你的密钥
#   OPENAI_API_BASE=https://api.openai.com/v1（或任意兼容端点）
#   DEFAULT_LLM_MODEL=gpt-4o
```

## 快速开始

**后端**（终端 1）：
```bash
PYTHONPATH=libs:apps/backend/runners uv run uvicorn apps.backend.app.main:app \
    --host 0.0.0.0 --port 8000 --reload --reload-dir apps/backend/app
```

**前端**（终端 2）：
```bash
cd apps/frontend && pnpm install && pnpm dev --host 0.0.0.0
```

**访问**：
- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`

### CLI 方式

```bash
# Arena：评测一个提交
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena evaluate \
    --method arena_attack_my_method --role attack \
    --config configs/research/bench_baseline.yaml \
    --matrix results/arena/benchmark_matrix.json

# Bench：运行指定实验
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.runner \
    --attack-method baseline_ipm --defense-method baseline_krum \
    --config configs/research/bench_baseline.yaml --seeds 0
```

## 基准矩阵

Arena 预计算所有基线攻击 × 基线防御的组合结果（CIFAR-10 non-IID, 10 客户端, FedAvg）。

```
            FedAvg    Krum  Median  TrimMean  Bulyan  CentClip     DnC
no_attack   0.6180  0.4808  0.5470    0.6186  0.5389    0.6185  0.6012
gaussian    0.6289  0.4717  0.5620    0.6162  0.5477    0.6476  0.6172
ipm         0.6221  0.4739  0.5780    0.6092  0.5633    0.6229  0.6027
scaling     0.6247  0.4712  0.5738    0.6221  0.5442    0.6225  0.5957
sign_flip   0.6230  0.4676  0.5725    0.6103  0.5482    0.6098  0.6050
alie        0.6223  0.4565  0.5463    0.6118  0.5485    0.6060  0.5974
```

生成或刷新矩阵：
```bash
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena generate \
    --config configs/research/bench_baseline.yaml --seeds 0 --output results/arena
```

## 内置方法

### 攻击

| 方法 | 类型 | 描述 |
|------|------|------|
| `gaussian` | 模型投毒 | 高斯噪声注入 |
| `scaling` | 模型投毒 | 参数缩放（[Bagdasaryan et al., AISTATS '20](https://proceedings.mlr.press/v108/bagdasaryan20a.html)） |
| `ipm` | 模型投毒 | 内积操纵（[Xie et al., ICML '20](https://proceedings.mlr.press/v119/xie20a.html)） |
| `sign_flip` | 模型投毒 | 符号翻转（[Li et al., '19](https://arxiv.org/abs/1903.03936)） |
| `alie` | 模型投毒 | A Little Is Enough（[Baruch et al., NeurIPS '19](https://proceedings.neurips.cc/paper/2019/hash/ec1c59141046cd1866bbbcdfb6ae31d4-Abstract.html)） |

### 防御

| 方法 | 描述 | 论文 |
|------|------|------|
| `krum` | 基于距离的选择 | [Blanchard et al., NeurIPS '17](https://proceedings.neurips.cc/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html) |
| `median` | 坐标级中位数 | [Yin et al., ICML '18](https://proceedings.mlr.press/v80/yin18a.html) |
| `trimmed_mean` | 截断均值 | [Yin et al., ICML '18](https://proceedings.mlr.press/v80/yin18a.html) |
| `bulyan` | Krum 选择 + 坐标裁剪 | [Mhamdi et al., ICML '18](https://proceedings.mlr.press/v80/mhamdi18a.html) |
| `centered_clipping` | 基于动量的裁剪 | [Karimireddy et al., ICML '21](https://proceedings.mlr.press/v139/karimireddy21a.html) |
| `dnc` | 基于 SVD 的异常检测 | [Shejwalkar & Houmansadr, NDSS '21](https://www.ndss-symposium.org/ndss-paper/manipulating-the-byzantine-optimizing-model-poisoning-attacks-and-defenses-for-federated-learning/) |

## 项目结构

```
fedarena/
├── apps/
│   ├── backend/
│   │   ├── app/                 # FastAPI 应用
│   │   │   ├── api/v1/          # REST 端点（提交、排行榜、矩阵、Bench、Agent）
│   │   │   ├── services/        # 业务逻辑（评测 worker、代码校验、LLM agent）
│   │   │   ├── models.py        # SQLModel 表定义
│   │   │   └── config.py        # Pydantic 配置（.env 加载）
│   │   └── runners/             # FL 运行时
│   └── frontend/                # React + Vite + Tailwind + Radix UI
│       └── src/pages/           # Leaderboard, Arena, Bench, Detail
├── libs/fl_core/                # FL 核心库
│   ├── research/                # Arena 引擎（注册表、执行器、矩阵、基类）
│   │   ├── attacks/             # 基线 + 用户提交
│   │   └── defenses/            # 基线 + 用户提交
│   ├── federated/               # 服务端 / 客户端 / 聚合
│   ├── models/                  # CNN / ResNet
│   ├── data/                    # 数据集加载与划分
│   ├── privacy/                 # CKKS 同态加密
│   └── compression/             # Top-K 稀疏化
├── configs/research/            # 实验配置
├── results/arena/               # 基准矩阵 + 评测结果
└── .claude/skills/              # CLI skills（fedarena_arena / fedarena_bench）
```

## 路线图

欢迎贡献！FedArena 致力于成为简洁、可扩展的联邦学习安全研究平台。

- [ ] **多配置矩阵** — 支持多数据集 / IID / 客户端数配置，拓宽评测覆盖面
- [ ] **Markdown 报告生成** — 可导出的逐提交对比报告
- [ ] **用户认证** — 简单的账号系统，关联提交归属
- [ ] **Docker 部署** — 一键 `docker-compose` 启动后端 + 前端 + GPU
- [ ] **更多攻防方法** — 数据投毒、自适应裁剪、几何中位数等
- [ ] **可复现性保障** — 固定种子、配置哈希校验、环境指纹
- [ ] **CI 流水线** — 自动化测试：注册表发现、提交校验、API 端点

<p align="center">
  <sub>FedArena 仅供研究和教学用途。</sub>
</p>
