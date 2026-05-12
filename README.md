<div align="center">
  <img src="icon.png" alt="FedArena" width="360" />
  <br />
  <p><em>A standardized attack/defense evaluation arena for federated learning security research</em></p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React">
    <img src="https://img.shields.io/badge/PyTorch-2.5-EE4C2C?logo=pytorch&logoColor=white" alt="PyTorch">
    <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  </p>
  <p>
    <strong>English</strong> | <a href="./README.zh-CN.md">简体中文</a>
  </p>
</div>

---

**FedArena** is a research platform where you submit FL attack or defense algorithms — via natural language prompt or code — and the system automatically evaluates them against a standardized benchmark matrix and ranks them on a leaderboard.

Built on **FastAPI + React + PyTorch**, with an OpenAI-compatible LLM integration for prompt-based code generation and experiment planning.

## News

- **2026-04-28** — **v0.2.0 released.** Phase 1 complete: task queue with concurrency control, draft persistence for prompt mode, training curve visualization, Markdown/PDF report export, failure diagnostics in UI, 72 backend tests.
- **2026-04-20** — **v0.1.0 released.** Core arena loop complete: LLM-powered prompt mode with code review, benchmark matrix evaluation, leaderboard ranking, CI with 40+ backend tests.

## Key Features

**Arena** — Submit a new attack or defense (describe it in natural language or paste code). The system generates the implementation, validates it, evaluates it against all opponents in the benchmark matrix, and ranks it on the leaderboard.

**Bench** — Describe experiments in natural language (e.g. *"Compare IPM and Scaling against Krum and Median"*). The system parses the intent, plans the M×N experiment matrix, runs them sequentially, and reports results.

**Leaderboard** — Unified ranking of user submissions alongside baseline methods, with a "Compare in Matrix" feature that overlays any submission onto the baseline heatmap.

**LLM Agent** — OpenAI-compatible API integration. The agent generates attack/defense code from natural language descriptions, validates it via AST analysis, and triggers evaluation automatically.

**CLI Mode** — Everything also works via Claude Code skills (`/fedarena_arena`, `/fedarena_bench`) or direct Python module invocation, no web UI required.

## What You Can Do

```
Arena prompt: "Design an attack that adaptively scales poisoned updates based on the global model's gradient norm"
→ Agent generates code → AST validation → evaluates vs 7 defenses → ranked on leaderboard
```

```
Bench prompt: "Compare IPM and Scaling against Krum and Median"
→ Parses to 2×2 = 4 experiments → runs sequentially → results table
```

```python
# Or submit code directly:
class MyAttack(ResearchAttackStrategy):
    method_name = "arena_attack_my_method"
    def attack(self, local_model_params, global_model_params, **kwargs):
        return poisoned_params
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                      │
│    (Dashboard · Arena · Bench · Leaderboard · Jobs · Detail) │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST + polling
┌───────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                          │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────┐     │
│   │ LLM Agent    │  │  Submission  │  │  Bench Worker  │     │
│   │ (code gen)   │  │  Validator   │  │ (M×N runner)   │     │
│   └──────┬───────┘  └──────┬───────┘  └───────┬────────┘     │
│          │                 │                  │              │
│   ┌──────▼─────────────────▼──────────────────▼──────────┐   │
│   │              Arena Evaluation Engine                  │   │
│   │    (registry · runner · matrix · ranking)            │   │
│   └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│   ┌──────────────┐    ┌──────▼───────┐    ┌──────────────┐   │
│   │   SQLite     │    │  fl_core     │    │ OpenAI API   │   │
│   │  (jobs, subs)│    │  (FL engine) │    │ (LLM calls)  │   │
│   └──────────────┘    └──────────────┘    └──────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Table of Contents

- [News](#news)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Quick Start](#quick-start)
- [Benchmark Matrix](#benchmark-matrix)
- [Built-in Methods](#built-in-methods)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

## Setup

```bash
git clone git@github.com:spire-studio/fedarena.git
cd fedarena
uv sync
```

For the LLM agent (prompt mode), create a `.env` file:
```bash
cp .env.example .env
# Edit .env and set:
#   OPENAI_API_KEY=your-api-key
#   OPENAI_API_BASE=https://api.openai.com/v1  (or any compatible endpoint)
#   DEFAULT_LLM_MODEL=gpt-4o
```

## Quick Start

**Backend** (terminal 1):
```bash
PYTHONPATH=libs:apps/backend/runners uv run uvicorn apps.backend.app.main:app \
    --host 0.0.0.0 --port 8000 --reload --reload-dir apps/backend/app
```

**Frontend** (terminal 2):
```bash
cd apps/frontend && pnpm install && pnpm dev --host 0.0.0.0
```

**Access**:
- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`

### CLI alternative

```bash
# Arena: evaluate a submission
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena evaluate \
    --method arena_attack_my_method --role attack \
    --config configs/research/bench_baseline.yaml \
    --matrix results/arena/benchmark_matrix.json

# Bench: run specific experiments
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.runner \
    --attack-method baseline_ipm --defense-method baseline_krum \
    --config configs/research/bench_baseline.yaml --seeds 0
```

## Benchmark Matrix

Arena pre-computes every combination of baseline attacks × baseline defenses on a fixed FL configuration (CIFAR-10 non-IID, 10 clients, FedAvg).

```
            FedAvg    Krum  Median  TrimMean  Bulyan  CentClip     DnC
no_attack   0.6180  0.4808  0.5470    0.6186  0.5389    0.6185  0.6012
gaussian    0.6289  0.4717  0.5620    0.6162  0.5477    0.6476  0.6172
ipm         0.6221  0.4739  0.5780    0.6092  0.5633    0.6229  0.6027
scaling     0.6247  0.4712  0.5738    0.6221  0.5442    0.6225  0.5957
sign_flip   0.6230  0.4676  0.5725    0.6103  0.5482    0.6098  0.6050
alie        0.6223  0.4565  0.5463    0.6118  0.5485    0.6060  0.5974
```

Generate or refresh:
```bash
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena generate \
    --config configs/research/bench_baseline.yaml --seeds 0 --output results/arena
```

## Built-in Methods

### Attacks

| Method | Type | Description |
|--------|------|-------------|
| `gaussian` | Model poisoning | Gaussian noise injection |
| `scaling` | Model poisoning | Parameter scaling ([Bagdasaryan et al., AISTATS '20](https://proceedings.mlr.press/v108/bagdasaryan20a.html)) |
| `ipm` | Model poisoning | Inner-product manipulation ([Xie et al., ICML '20](https://proceedings.mlr.press/v119/xie20a.html)) |
| `sign_flip` | Model poisoning | Sign flipping ([Li et al., '19](https://arxiv.org/abs/1903.03936)) |
| `alie` | Model poisoning | A Little Is Enough ([Baruch et al., NeurIPS '19](https://proceedings.neurips.cc/paper/2019/hash/ec1c59141046cd1866bbbcdfb6ae31d4-Abstract.html)) |

### Defenses

| Method | Description | Paper |
|--------|-------------|-------|
| `krum` | Distance-score selection | [Blanchard et al., NeurIPS '17](https://proceedings.neurips.cc/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html) |
| `median` | Coordinate-wise median | [Yin et al., ICML '18](https://proceedings.mlr.press/v80/yin18a.html) |
| `trimmed_mean` | Trimmed mean | [Yin et al., ICML '18](https://proceedings.mlr.press/v80/yin18a.html) |
| `bulyan` | Krum selection + coordinate clipping | [Mhamdi et al., ICML '18](https://proceedings.mlr.press/v80/mhamdi18a.html) |
| `centered_clipping` | Momentum-based clipping | [Karimireddy et al., ICML '21](https://proceedings.mlr.press/v139/karimireddy21a.html) |
| `dnc` | SVD-based anomaly detection | [Shejwalkar & Houmansadr, NDSS '21](https://www.ndss-symposium.org/ndss-paper/manipulating-the-byzantine-optimizing-model-poisoning-attacks-and-defenses-for-federated-learning/) |

## Project Structure

```
fedarena/
├── apps/
│   ├── backend/
│   │   ├── app/                 # FastAPI application
│   │   │   ├── api/v1/          # REST endpoints (submissions, leaderboard, matrix, bench, agent)
│   │   │   ├── services/        # Business logic (evaluation worker, code validation, LLM agent)
│   │   │   ├── models.py        # SQLModel tables (Submission, EvaluationJob, BenchJob)
│   │   │   └── config.py        # Pydantic settings (.env loading)
│   │   └── runners/             # FL runtime (core_runtime.py)
│   └── frontend/                # React + Vite + Tailwind + Radix UI
│       └── src/pages/           # Dashboard, Arena, Bench, Leaderboard, Jobs, Detail
├── libs/fl_core/                # FL core library
│   ├── research/                # Arena engine (registry, runner, arena, base classes)
│   │   ├── attacks/             # Baseline + user submissions
│   │   └── defenses/            # Baseline + user submissions
│   ├── federated/               # Server / Client / Aggregation
│   ├── models/                  # CNN / ResNet
│   ├── data/                    # Dataset loading & partitioning
│   ├── privacy/                 # CKKS encryption
│   └── compression/             # Top-K sparsification
├── configs/research/            # Experiment configs
├── results/arena/               # Benchmark matrix + evaluation results
└── .claude/skills/              # CLI skills (fedarena_arena, fedarena_bench)
```

## Roadmap

### Phase 1: Stabilize Core Loop

- [x] Arena evaluation pipeline (submit → validate → evaluate → rank)
- [x] LLM Agent prompt mode with code review step
- [x] Benchmark matrix generation & heatmap visualization
- [x] Leaderboard (attack / defense ranking)
- [x] Bench: natural-language experiment planning & execution
- [x] CI pipeline (lint, type-check, 40+ backend tests)
- [x] Incremental result saving & stale job recovery
- [x] Task queue & concurrency control (replace bare threads)
- [x] Training round logs viewable in detail page
- [x] Auto-generated evaluation reports (Markdown / PDF export)
- [x] Failure diagnostics — surface error reasons & failed experiment details in UI

### Phase 2: Range / Scenario System

- [x] Scenario library — multiple datasets, non-IID levels, malicious client ratios, model architectures
- [x] Multi-metric scoring — Accuracy Drop, Convergence Speed, Stability, Runtime Cost, Max Accuracy, per-opponent and summary aggregation
- [x] Multi-dimensional leaderboard — Avg Accuracy, Accuracy Drop, Worst Case, Convergence, Stability columns with sort_by support
- [x] Per-scenario leaderboards
- [x] Method versioning — track iterations of the same attack/defense, side-by-side comparison
- [x] Experiment comparison — cross-run overlay charts, side-by-side metrics
- [x] Analytical reports — LLM-generated strengths/weaknesses, baseline comparison, recommendations, cached per evaluation
- [x] Dashboard page — live arena status, active jobs, top methods, recent submissions
- [x] Navigation restructure — Dashboard / Scenarios / Arena / Bench / Leaderboard / Reports / Methods / Jobs
- [x] Arena UX improvements — left/right layout, template mode, evaluation intensity selection
- [x] Matrix interaction — filter by scenario, click cell for run details & per-seed breakdown

### Phase 3: Platform

- [ ] Sandbox execution — container isolation, timeout, network & filesystem restrictions for user-submitted code
- [ ] User & team accounts with permissions
- [ ] Challenge mode — fixed scenarios, time-limited competitions, hidden test sets
- [ ] Course mode — guided exercises for FL security education
- [ ] Resource quotas & scheduling (multi-GPU, multi-user)
- [ ] Audit logging
- [ ] Dataset & model plugin system for new FL scenarios
- [ ] Public leaderboards & embeddable widgets

<p align="center">
  <sub>FedArena is for research and educational use.</sub>
</p>
