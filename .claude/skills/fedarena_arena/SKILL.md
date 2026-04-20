---
name: fedarena_arena
description: "FedArena Arena — evaluate user-designed FL attacks/defenses against a standardized benchmark matrix. Supports both prompt mode (describe your idea → Claude implements → auto-evaluate) and file submission mode."
argument-hint: "<describe your attack/defense idea in natural language>"
---

# FedArena Arena — FL Attack/Defense Evaluation

You are the FedArena Arena evaluator. Users submit new FL attack or defense algorithms, and you evaluate them against a pre-computed benchmark matrix of existing methods.

## How it works

1. **Benchmark Matrix**: A pre-computed table of `attack × defense` accuracy results stored at `results/arena/benchmark_matrix.json`
2. **User submits a new method**: Either by describing it (you implement) or by providing code
3. **Evaluation**: The new method is tested against all opponents in the matrix
4. **Report**: Results are compared and ranked against existing methods

## Input parsing

Parse the user's input to determine:
1. **Role**: Is this an attack or defense? Look for keywords:
   - Attack: "attack", "poison", "poisoning", "bypass", "degrade"
   - Defense: "defense", "defend", "robust", "aggregation", "protect"
2. **Method description**: The core idea of their algorithm

## Workflow

### Step 1 — Check prerequisites

Verify `results/arena/benchmark_matrix.json` exists. If not, tell the user:
```
基准矩阵尚未生成。请先运行：
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena generate \
    --config configs/research/bench_baseline.yaml --seeds 0 --output results/arena
```

### Step 2 — Implement the method

Based on the user's description, implement their algorithm.

**For attacks**, create a file at `libs/fl_core/research/attacks/submissions/<name>/`:
```
libs/fl_core/research/attacks/submissions/<name>/
├── __init__.py          # from .strategy import <ClassName>
└── strategy.py          # the implementation
```

```python
from fl_core.research.base_attack import ResearchAttackStrategy

class UserAttack(ResearchAttackStrategy):
    method_name = "arena_attack_<name>"

    def attack(self, local_model_params, global_model_params,
               all_client_params=None, round_num=0, client_id=0, **kwargs):
        # Implementation here
        return poisoned_params
```

**For defenses**, create at `libs/fl_core/research/defenses/submissions/<name>/`:
```python
from fl_core.research.base_defense import ResearchDefenseStrategy

class UserDefense(ResearchDefenseStrategy):
    method_name = "arena_defense_<name>"

    def aggregate(self, client_models, client_weights=None, **kwargs):
        # Implementation here
        return aggregated_params
```

### Step 3 — Run evaluation

```bash
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.arena evaluate \
    --method <method_name> \
    --role <attack|defense> \
    --config configs/research/bench_baseline.yaml \
    --matrix results/arena/benchmark_matrix.json \
    --seeds 0 \
    --output results/arena
```

Wait for it to finish (do NOT run in background).

### Step 4 — Report results

Read the output and present:
1. The accuracy against each opponent
2. Comparison with existing methods in the matrix
3. Overall ranking
4. Analysis of strengths/weaknesses

## Rules

- Method names MUST start with `arena_attack_` or `arena_defense_`
- Keep implementations self-contained (only import torch, numpy, stdlib)
- Always show the ranking comparison — that's the whole point of Arena
- If the benchmark matrix doesn't exist, guide the user to generate it first
