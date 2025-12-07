## Evaluation Guide for Jamie

This document explains how evaluation works in `src/scripts/evaluate_agent.py`, how to run it, what it measures, and how to troubleshoot common issues.

### Overview

- Sends multi-turn scenarios to the running Jamie API (`/chat`) and captures per-turn latency and overall scenario stats.
- Optionally runs an LLM-as-judge pass on the conversation (requires `GEMINI_API_KEY`).
- Can run an ablation comparing memory ON vs OFF and produce side-by-side reports.
- Saves detailed JSON and CSV outputs in `logs/`.

### Prerequisites

- API server is running (e.g. in another terminal):
  - `uv run src/main.py` (defaults to `http://localhost:8000`)
- Environment is configured via `.env` (loaded by `src/config.py`):
  - `GEMINI_API_KEY`, `PLACES_API_KEY`, `BASE_BUCKET`, etc.
  - Server-side LLM settings:
    - `JAMIE_LLM_TIMEOUT_SECONDS` (per-call LLM timeout)
    - `JAMIE_LLM_MAX_CONCURRENCY` (Gemini thread pool size)
- Judge mode (optional): `GEMINI_API_KEY` must be set in the shell for the eval process if you enable `--judge`.

### Scenarios

- Default scenarios are embedded in the script and are grouped by user (per-user mappings).
- Each scenario is run sequentially; within a scenario, messages are posted as turns to the same session for that user.

### Key CLI Flags

- `--api-url`: Base URL for the API (default `http://localhost:8000`).
- (no `--user`): Evaluator runs all users found in the built-in scenarios mapping.
- `--timeout`: HTTP client timeout (seconds) for each `/chat` call from the evaluator.
- `--turn-sleep`: Optional pause (seconds) between turns to avoid burst load.
- `--judge`: Enable LLM-as-judge scoring of the final transcripts (requires `GEMINI_API_KEY` in the eval process).
- `--ablate-memory`: Run A/B evaluation (Memory OFF, then Memory ON) and write a single comparison report.
- `--force-disable-memory`: Force memory OFF for all requests (useful to avoid extra LLM calls during eval). When set with `--ablate-memory`, it runs a single OFF pass.

Important: The evaluator’s `--timeout` is an HTTP client timeout. The model’s per-call timeout is configured server-side via `.env` as `JAMIE_LLM_TIMEOUT_SECONDS` and logged at server startup.

### What It Measures

For each scenario:
- Per-turn latency (seconds)
- Scenario totals: total time, average turn time, p50/p90/p95 turn times
- Optional judge scores (`overall`, `helpfulness`, etc.) when `--judge` is enabled

### Outputs

- Per-user run artifacts (no ablation):
  - `logs/eval_results_<user>_<timestamp>.json`: Full results with all scenarios and conversations for that user.
  - `logs/eval_summary_<user>_<timestamp>.csv`: Scenario-level summary for that user.

- Ablation (`--ablate-memory`):
  - `logs/eval_ablation_<user>_<timestamp>.json`: Contains both ON and OFF results and a computed comparison for a given user.
  - `logs/eval_ablation_<user>_<timestamp>.csv`: Per-scenario deltas (time and judge) for a given user.

### Memory Behavior in Eval

- Memory can add extra LLM calls (preference extraction, summaries). This affects latency and stability.
- Use `--force-disable-memory` to turn memory off completely during evaluation.
- With `--ablate-memory`, the script runs OFF then ON (current order), so you can quantify the impact of memory.

### Example Commands

- Basic run:

```bash
uv run python src/scripts/evaluate_agent.py
```

- Multi-user: uses built-in defaults (runs all defined users) or all users in a provided multi-user scenario file.

- Increase HTTP timeout and add spacing between turns:

```bash
uv run python src/scripts/evaluate_agent.py --timeout 300 --turn-sleep 1.5
```

- Ablation (OFF then ON) with spacing:

```bash


```

- Single pass with memory forced OFF:

```bash
uv run python src/scripts/evaluate_agent.py --timeout 300 --turn-sleep 1.5 --force-disable-memory
```

- Use a custom scenario file:

```bash
uv run python src/scripts/evaluate_agent.py --scenarios path/to/scenarios.json
```

Where `scenarios.json` must be a per-user mapping:

```json
{
  "sarah": [
    {"name": "Restaurant Basic", "messages": ["Find ice cream near me", "I'm in downtown San Francisco"]},
    {"name": "User Memory Check", "messages": ["Hi, I'm Sarah.", "Remind me what we discussed?"]}
  ],
  "alex": [
    {"name": "Recipe Basic", "messages": ["I want to make pasta"]}
  ]
}
```

### How It Works (Flow)

1. The evaluator creates a dev token for each user (simple base64 JSON).
2. For each scenario, it POSTs messages to `/chat`, preserving a `session_id` to keep turns in the same session.
3. If `--ablate-memory` is enabled, it runs both OFF and ON (current order: OFF first, then ON). Memory OFF uses the header `X-Disable-Memory: 1`.
4. Optional judge pass runs locally in the evaluator using Gemini (if `--judge` and `GEMINI_API_KEY` are set).
5. Writes results to `logs/` as JSON and CSV.

### Timeouts and Retries

- Evaluator:
  - `--timeout` is the HTTP request timeout per `/chat` call.
  - Network retries are applied to the HTTP call (basic 3-attempt loop).

- Server:
  - LLM per-call timeout is `JAMIE_LLM_TIMEOUT_SECONDS` (from `.env`), enforced in the Gemini client.
  - The Gemini client also retries transient timeouts with exponential backoff.
  - Concurrency is limited by `JAMIE_LLM_MAX_CONCURRENCY`.

### Troubleshooting

- Seeing “LLM generation timed out”:
  - Increase server `.env` `JAMIE_LLM_TIMEOUT_SECONDS`.
  - Reduce `JAMIE_LLM_MAX_CONCURRENCY`.
  - In the evaluator, increase `--timeout` and add `--turn-sleep`.
  - Try `--force-disable-memory` to avoid extra LLM calls during eval.

- Judge not running:
  - Ensure `GEMINI_API_KEY` is set in the evaluator’s environment (the server’s environment is separate).

- Requests failing intermittently:
  - Increase `--timeout` and use `--turn-sleep` to reduce burstiness.

### Notes

- The evaluator does not change server-side configuration. Make sure your server is started with the intended `.env` settings. The Gemini client logs effective LLM timeout and concurrency at startup.

