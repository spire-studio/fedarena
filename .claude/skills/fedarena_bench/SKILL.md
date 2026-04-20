---
name: fedarena_bench
description: Run FL benchmark experiments from natural language. Parses user intent,
  plans experiments, runs them via the research runner, and reports comparison results.
argument-hint: "<natural language experiment request> — e.g. 测一下 IPM、Scaling 在 Krum、Median 上的效果"
---

# FL Benchmark Executor

You are an automated FL experiment executor. The user describes experiments in natural language. You plan, run, and report results.

**User request**: $ARGUMENTS

## Step 1 — Understand intent and plan experiments

Parse the user's request to determine what experiments to run. Produce an experiment plan table.

Each experiment is one runner invocation with a specific combination of:
- `attack_method` — which attack to inject (or none)
- `defense_method` — which defense to inject (or none = config default FedAvg)
- `experiment_name` — a short identifier for the results directory

### Alias mapping

Map the user's natural language to registered strategy names:

**Attacks:**

| User says | Registry name |
|---|---|
| IPM, ipm, inner product manipulation | `baseline_ipm` |
| scaling, scale attack, 缩放攻击 | `baseline_scaling` |
| sign-flipping, sign flip, sign-flip, 符号翻转 | `baseline_sign_flip` |
| gaussian, noise, 高斯噪声 | `baseline_gaussian` |
| arena_attack_<name> (user submissions) | use as-is |

**Defenses:**

| User says | Registry name |
|---|---|
| FedAvg, fedavg, 联邦平均, no defense | (do not pass --defense-method; config default is FedAvg) |
| Krum, krum, multi-krum | `baseline_krum` |
| median, 中位数, coordinate-wise median | `baseline_median` |
| trimmed mean, 截断均值 | `baseline_trimmed_mean` |
| claude_def1_vN, etc. | use as-is |

### Planning rules

- If the user mentions multiple attacks AND multiple defenses, generate the **Cartesian product** (all combinations).
- If the user mentions only attacks (no defense specified), test each attack against the config default (FedAvg).
- If the user mentions only defenses (no attack specified), test each defense against the config's default attack (or no attack).
- If the user mentions neither attacks nor defenses (e.g. "跑一下 CIFAR-10 non-IID 联邦"), plan a single vanilla experiment with no attack/defense injection.
- If the user mentions specific config changes (e.g. "IID", "alpha=0.1", "50 rounds"), note them but use the standard bench_baseline.yaml config — config overrides are NOT supported yet. Mention this to the user.

### Output the plan

Print the experiment plan as a markdown table:

```
## Experiment Plan

| # | experiment_name | attack | defense | notes |
|---|---|---|---|---|
| 1 | ipm_vs_fedavg | baseline_ipm | (default) | |
| 2 | ipm_vs_krum | baseline_ipm | baseline_krum | |
| ...
```

If the total number of experiments is > 5, ask the user to confirm before proceeding. Otherwise, proceed directly.

## Step 2 — Run experiments

For each experiment in the plan, run:

```bash
PYTHONPATH=libs:apps/backend/runners uv run python -m fl_core.research.runner \
    --attack-method <attack_method> \
    --defense-method <defense_method> \
    --experiment-name <experiment_name> \
    --config configs/research/bench_baseline.yaml \
    --seeds 0 \
    --results-dir results/bench
```

Rules:
- Omit `--attack-method` if no attack (vanilla FL or defense-only test).
- Omit `--defense-method` if using config default (FedAvg).
- **Wait for each experiment to finish** before starting the next one (do NOT run in background).
- After each experiment finishes, read the summary: `results/bench/<experiment_name>/summary.json`
- Print a brief one-line status after each experiment: `[2/9] ipm_vs_krum: accuracy=0.6512`

## Step 3 — Report results

After all experiments are done, output a results report.

### Always output: results table

```markdown
## Benchmark Results

| Experiment | Attack | Defense | Avg Accuracy | Avg Loss |
|---|---|---|---|---|
| ipm_vs_fedavg | IPM | FedAvg | 0.2341 | 2.85 |
| ipm_vs_krum | IPM | Krum | 0.6512 | 1.23 |
| ... | | | | |
```

### If cross-product (N attacks x M defenses): also output matrix view

```markdown
## Accuracy Matrix (rows=attack, cols=defense)

|              | FedAvg | Krum   | Median |
|--------------|--------|--------|--------|
| IPM          | 0.2341 | 0.6512 | 0.5893 |
| Scaling      | 0.1023 | 0.6234 | 0.5567 |
| Sign-flip    | 0.3456 | 0.6678 | 0.6012 |
```

### Key observations

After the table(s), provide 2-3 bullet points highlighting key findings:
- Which attack is strongest / weakest?
- Which defense is most effective?
- Any surprising results?

## Rules

- **Never modify configs or baseline code** — only run experiments
- **Use bench_baseline.yaml** as the config for all experiments
- **Results go to `results/bench/`** — separate from research results
- **One seed by default** (seed=0) for quick benchmarking. If the user asks for more reliable results, use `--seeds 0,1,2`
- If an experiment crashes, log the error and continue with the next one
- Keep output concise — the user wants results, not verbose logs
