#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

METRICS = ["helpfulness", "specificity", "grounding", "coherence", "safety", "overall"]

@dataclass
class UserAggregate:
    user: str
    num_scenarios: int
    turns_off: int
    turns_on: int
    weighted_avg_turn_off: float
    weighted_avg_turn_on: float
    latency_improvement_pct: Optional[float]
    p50_off: Optional[float]
    p50_on: Optional[float]
    p50_improvement_pct: Optional[float]
    p90_off: Optional[float]
    p90_on: Optional[float]
    p90_improvement_pct: Optional[float]
    p95_off: Optional[float]
    p95_on: Optional[float]
    p95_improvement_pct: Optional[float]
    # Per-metric judge means and deltas
    judge_means_off: Dict[str, float]
    judge_means_on: Dict[str, float]
    judge_delta_means: Dict[str, float]
    # Internal counts to enable weighted overall aggregation
    judge_counts_off: Dict[str, int]
    judge_counts_on: Dict[str, int]
    memory_check_judge_delta: Optional[float]
    scenario_success_rate_off: Optional[float]
    scenario_success_rate_on: Optional[float]
    success_rate_delta_pct: Optional[float]


def safe_pct_improvement(off: Optional[float], on: Optional[float]) -> Optional[float]:
    if off is None or on is None:
        return None
    if off == 0:
        return None
    return (off - on) / off * 100.0


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def compute_user_metrics(payload: Dict[str, Any], user_from_filename: str) -> UserAggregate:
    comparisons: List[Dict[str, Any]] = payload.get("comparisons", [])
    off_summary: Dict[str, Any] = payload.get("off_summary", {})
    on_summary: Dict[str, Any] = payload.get("on_summary", {})
    off_scenarios: List[Dict[str, Any]] = payload.get("off_scenarios", [])
    on_scenarios: List[Dict[str, Any]] = payload.get("on_scenarios", [])

    # Weighted average per-turn latency using scenario avg weighted by num_turns
    total_turns = 0
    sum_off = 0.0
    sum_on = 0.0
    memory_check_judge_delta: Optional[float] = None

    for comp in comparisons:
        num_turns = int(comp.get("num_turns", 0))
        total_turns += num_turns
        avg_off = float(comp.get("avg_turn_seconds_off", 0.0))
        avg_on = float(comp.get("avg_turn_seconds_on", 0.0))
        sum_off += avg_off * num_turns
        sum_on += avg_on * num_turns

        if comp.get("scenario_name") == "User Memory Check":
            j_off = comp.get("judge_overall_off")
            j_on = comp.get("judge_overall_on")
            if isinstance(j_off, (int, float)) and isinstance(j_on, (int, float)):
                memory_check_judge_delta = float(j_on) - float(j_off)

    weighted_avg_off = (sum_off / total_turns) if total_turns > 0 else 0.0
    weighted_avg_on = (sum_on / total_turns) if total_turns > 0 else 0.0
    latency_improvement_pct = safe_pct_improvement(weighted_avg_off, weighted_avg_on)

    # Percentiles from summaries (if present)
    p50_off = off_summary.get("overall_p50_turn_seconds")
    p50_on = on_summary.get("overall_p50_turn_seconds")
    p90_off = off_summary.get("overall_p90_turn_seconds")
    p90_on = on_summary.get("overall_p90_turn_seconds")
    p95_off = off_summary.get("overall_p95_turn_seconds")
    p95_on = on_summary.get("overall_p95_turn_seconds")

    p50_improv = safe_pct_improvement(p50_off, p50_on) if isinstance(p50_off, (int, float)) and isinstance(p50_on, (int, float)) else None
    p90_improv = safe_pct_improvement(p90_off, p90_on) if isinstance(p90_off, (int, float)) and isinstance(p90_on, (int, float)) else None
    p95_improv = safe_pct_improvement(p95_off, p95_on) if isinstance(p95_off, (int, float)) and isinstance(p95_on, (int, float)) else None

    # Judge per-metric means (averaged over scenarios)
    def collect_means_and_counts(scenarios: List[Dict[str, Any]]) -> Tuple[Dict[str, float], Dict[str, int]]:
        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for s in scenarios:
            scores = s.get("judge_scores")
            if isinstance(scores, dict):
                for k in METRICS:
                    v = scores.get(k)
                    if isinstance(v, (int, float)):
                        sums[k] = sums.get(k, 0.0) + float(v)
                        counts[k] = counts.get(k, 0) + 1
        means: Dict[str, float] = {}
        for k, total in sums.items():
            c = counts.get(k, 0)
            if c > 0:
                means[k] = total / c
        return means, counts

    judge_means_off, judge_counts_off = collect_means_and_counts(off_scenarios)
    judge_means_on, judge_counts_on = collect_means_and_counts(on_scenarios)
    judge_delta_means: Dict[str, float] = {}
    for k in METRICS:
        if k in judge_means_off and k in judge_means_on:
            judge_delta_means[k] = judge_means_on[k] - judge_means_off[k]

    # Scenario success: scenario considered successful if all turns have no error
    def scenario_success_rate(scenarios: List[Dict[str, Any]]) -> Optional[float]:
        if not scenarios:
            return None
        successes = 0
        for s in scenarios:
            conv = s.get("conversation", [])
            ok = True
            for t in conv:
                if t.get("error") is not None:
                    ok = False
                    break
            if ok:
                successes += 1
        return successes / len(scenarios) * 100.0

    success_off = scenario_success_rate(off_scenarios)
    success_on = scenario_success_rate(on_scenarios)
    success_delta_pct = safe_pct_improvement(success_off, success_on) if (success_off is not None and success_on is not None) else None

    return UserAggregate(
        user=user_from_filename,
        num_scenarios=len(comparisons),
        turns_off=int(off_summary.get("total_turns", 0)),
        turns_on=int(on_summary.get("total_turns", 0)),
        weighted_avg_turn_off=weighted_avg_off,
        weighted_avg_turn_on=weighted_avg_on,
        latency_improvement_pct=latency_improvement_pct,
        p50_off=float(p50_off) if isinstance(p50_off, (int, float)) else None,
        p50_on=float(p50_on) if isinstance(p50_on, (int, float)) else None,
        p50_improvement_pct=p50_improv,
        p90_off=float(p90_off) if isinstance(p90_off, (int, float)) else None,
        p90_on=float(p90_on) if isinstance(p90_on, (int, float)) else None,
        p90_improvement_pct=p90_improv,
        p95_off=float(p95_off) if isinstance(p95_off, (int, float)) else None,
        p95_on=float(p95_on) if isinstance(p95_on, (int, float)) else None,
        p95_improvement_pct=p95_improv,
        judge_means_off=judge_means_off,
        judge_means_on=judge_means_on,
        judge_delta_means=judge_delta_means,
        judge_counts_off=judge_counts_off,
        judge_counts_on=judge_counts_on,
        memory_check_judge_delta=memory_check_judge_delta,
        scenario_success_rate_off=success_off,
        scenario_success_rate_on=success_on,
        success_rate_delta_pct=success_delta_pct,
    )


def aggregate_overall(users: List[UserAggregate]) -> UserAggregate:
    # Weighted by turns where applicable
    total_turns_off = sum(u.turns_off for u in users)
    total_turns_on = sum(u.turns_on for u in users)
    total_scenarios = sum(u.num_scenarios for u in users)
    if total_turns_off == 0:
        weighted_avg_off = 0.0
    else:
        weighted_avg_off = sum(u.weighted_avg_turn_off * u.turns_off for u in users) / total_turns_off
    if total_turns_on == 0:
        weighted_avg_on = 0.0
    else:
        weighted_avg_on = sum(u.weighted_avg_turn_on * u.turns_on for u in users) / total_turns_on
    latency_improvement_pct = safe_pct_improvement(weighted_avg_off, weighted_avg_on)

    # Percentiles: simple average where present
    def avg_or_none(values: List[Optional[float]]) -> Optional[float]:
        vals = [v for v in values if isinstance(v, (int, float))]
        return (sum(vals) / len(vals)) if vals else None

    p50_off = avg_or_none([u.p50_off for u in users])
    p50_on = avg_or_none([u.p50_on for u in users])
    p90_off = avg_or_none([u.p90_off for u in users])
    p90_on = avg_or_none([u.p90_on for u in users])
    p95_off = avg_or_none([u.p95_off for u in users])
    p95_on = avg_or_none([u.p95_on for u in users])

    p50_improv = safe_pct_improvement(p50_off, p50_on)
    p90_improv = safe_pct_improvement(p90_off, p90_on)
    p95_improv = safe_pct_improvement(p95_off, p95_on)

    # Judge per-metric: weighted by scenario counts per user
    off_totals: Dict[str, float] = {}
    off_counts: Dict[str, int] = {}
    on_totals: Dict[str, float] = {}
    on_counts: Dict[str, int] = {}
    for u in users:
        for k, mean in u.judge_means_off.items():
            c = u.judge_counts_off.get(k, 0)
            if c > 0:
                off_totals[k] = off_totals.get(k, 0.0) + mean * c
                off_counts[k] = off_counts.get(k, 0) + c
        for k, mean in u.judge_means_on.items():
            c = u.judge_counts_on.get(k, 0)
            if c > 0:
                on_totals[k] = on_totals.get(k, 0.0) + mean * c
                on_counts[k] = on_counts.get(k, 0) + c
    judge_means_off: Dict[str, float] = {}
    judge_means_on: Dict[str, float] = {}
    judge_delta_means: Dict[str, float] = {}
    for k in METRICS:
        off_mean = (off_totals.get(k, 0.0) / off_counts.get(k, 0)) if off_counts.get(k, 0) > 0 else None
        on_mean = (on_totals.get(k, 0.0) / on_counts.get(k, 0)) if on_counts.get(k, 0) > 0 else None
        if isinstance(off_mean, (int, float)):
            judge_means_off[k] = float(off_mean)
        if isinstance(on_mean, (int, float)):
            judge_means_on[k] = float(on_mean)
        if isinstance(off_mean, (int, float)) and isinstance(on_mean, (int, float)):
            judge_delta_means[k] = float(on_mean) - float(off_mean)

    # Memory-check deltas: average where present
    mem_deltas = [u.memory_check_judge_delta for u in users if isinstance(u.memory_check_judge_delta, (int, float))]
    mem_delta_avg = (sum(mem_deltas) / len(mem_deltas)) if mem_deltas else None

    # Success rates: average across users (scenario-level percentage)
    success_off = avg_or_none([u.scenario_success_rate_off for u in users])
    success_on = avg_or_none([u.scenario_success_rate_on for u in users])
    success_delta_pct = safe_pct_improvement(success_off, success_on) if (success_off is not None and success_on is not None) else None

    return UserAggregate(
        user="OVERALL",
        num_scenarios=total_scenarios,
        turns_off=total_turns_off,
        turns_on=total_turns_on,
        weighted_avg_turn_off=weighted_avg_off,
        weighted_avg_turn_on=weighted_avg_on,
        latency_improvement_pct=latency_improvement_pct,
        p50_off=p50_off,
        p50_on=p50_on,
        p50_improvement_pct=p50_improv,
        p90_off=p90_off,
        p90_on=p90_on,
        p90_improvement_pct=p90_improv,
        p95_off=p95_off,
        p95_on=p95_on,
        p95_improvement_pct=p95_improv,
        judge_means_off=judge_means_off,
        judge_means_on=judge_means_on,
        judge_delta_means=judge_delta_means,
        judge_counts_off={k: off_counts.get(k, 0) for k in METRICS},
        judge_counts_on={k: on_counts.get(k, 0) for k in METRICS},
        memory_check_judge_delta=mem_delta_avg,
        scenario_success_rate_off=success_off,
        scenario_success_rate_on=success_on,
        success_rate_delta_pct=success_delta_pct,
    )


def write_csv(path: Path, rows: List[UserAggregate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "user",
                "num_scenarios",
                "turns_off",
                "turns_on",
                "weighted_avg_turn_off",
                "weighted_avg_turn_on",
                "latency_improvement_pct",
                "p50_off",
                "p50_on",
                "p50_improvement_pct",
                "p90_off",
                "p90_on",
                "p90_improvement_pct",
                "p95_off",
                "p95_on",
                "p95_improvement_pct",
                # Judge metrics (means over scenarios)
                *[f"judge_{m}_off_mean" for m in METRICS],
                *[f"judge_{m}_on_mean" for m in METRICS],
                *[f"judge_{m}_delta_mean" for m in METRICS],
                "memory_check_judge_delta",
                "scenario_success_rate_off",
                "scenario_success_rate_on",
                "success_rate_delta_pct",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.user,
                    r.num_scenarios,
                    r.turns_off,
                    r.turns_on,
                    f"{r.weighted_avg_turn_off:.3f}",
                    f"{r.weighted_avg_turn_on:.3f}",
                    f"{r.latency_improvement_pct:.2f}" if r.latency_improvement_pct is not None else "",
                    f"{r.p50_off:.3f}" if r.p50_off is not None else "",
                    f"{r.p50_on:.3f}" if r.p50_on is not None else "",
                    f"{r.p50_improvement_pct:.2f}" if r.p50_improvement_pct is not None else "",
                    f"{r.p90_off:.3f}" if r.p90_off is not None else "",
                    f"{r.p90_on:.3f}" if r.p90_on is not None else "",
                    f"{r.p90_improvement_pct:.2f}" if r.p90_improvement_pct is not None else "",
                    f"{r.p95_off:.3f}" if r.p95_off is not None else "",
                    f"{r.p95_on:.3f}" if r.p95_on is not None else "",
                    f"{r.p95_improvement_pct:.2f}" if r.p95_improvement_pct is not None else "",
                    # Judge metric means
                    *[
                        (f"{r.judge_means_off.get(m, float('nan')):.3f}" if m in r.judge_means_off else "")
                        for m in METRICS
                    ],
                    *[
                        (f"{r.judge_means_on.get(m, float('nan')):.3f}" if m in r.judge_means_on else "")
                        for m in METRICS
                    ],
                    *[
                        (f"{r.judge_delta_means.get(m, float('nan')):.3f}" if m in r.judge_delta_means else "")
                        for m in METRICS
                    ],
                    f"{r.memory_check_judge_delta:.3f}" if r.memory_check_judge_delta is not None else "",
                    f"{r.scenario_success_rate_off:.2f}" if r.scenario_success_rate_off is not None else "",
                    f"{r.scenario_success_rate_on:.2f}" if r.scenario_success_rate_on is not None else "",
                    f"{r.success_rate_delta_pct:.2f}" if r.success_rate_delta_pct is not None else "",
                ]
            )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile ablation evaluation results to a single CSV.")
    parser.add_argument("--results-dir", default="results", help="Directory containing eval_ablation_*.json files")
    parser.add_argument("--output", default=None, help="Output CSV path (default: results/compiled_metrics_<ts>.csv)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir.resolve()}")

    files = sorted(results_dir.glob("eval_ablation_*.json"))
    if not files:
        raise FileNotFoundError(f"No ablation files found in {results_dir.resolve()}")

    per_user: List[UserAggregate] = []
    for path in files:
        payload = read_json(path)
        # Infer user from filename: eval_ablation_<user>_YYYYMMDD_*.json
        name = path.stem
        parts = name.split("_")
        user = parts[2] if len(parts) >= 3 else parts[-1]
        per_user.append(compute_user_metrics(payload, user))

    overall = aggregate_overall(per_user)
    rows = per_user + [overall]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(args.output) if args.output else results_dir / f"compiled_metrics_{ts}.csv"
    write_csv(output_path, rows)

    print(f"Wrote compiled metrics to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

