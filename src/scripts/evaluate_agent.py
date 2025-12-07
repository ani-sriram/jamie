#!/usr/bin/env python3
"""
Evaluation runner for the current Jamie API.

Features:
- Runs multi-turn scenarios against the active FastAPI server (src/web/api.py)
- Objective metrics: per-turn latency, scenario totals, p50/p90/p95
- Saves detailed JSON and CSV summaries in logs/
- Optional LLM-as-judge subjective scoring (--judge), if GEMINI_API_KEY is set
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Optional Google Cloud / Vertex AI imports (for service account auth)
try:
    from google.oauth2 import service_account  # type: ignore
    import vertexai  # type: ignore
    from vertexai.generative_models import GenerativeModel  # type: ignore
except Exception:
    service_account = None  # type: ignore
    vertexai = None  # type: ignore
    GenerativeModel = None  # type: ignore

# -----------------------------
# Data models
# -----------------------------

@dataclass
class TurnResult:
    turn_index: int
    user_message: str
    assistant_message: Optional[str]
    elapsed_seconds: float
    error: Optional[str] = None


@dataclass
class ScenarioResult:
    scenario_name: str
    total_time_seconds: float
    avg_turn_seconds: float
    p50_turn_seconds: float
    p90_turn_seconds: float
    p95_turn_seconds: float
    num_turns: int
    conversation: List[TurnResult]
    # Optional subjective scores
    judge_scores: Optional[Dict[str, Any]] = None


@dataclass
class RunSummary:
    timestamp: str
    api_url: str
    user: str
    total_scenarios: int
    total_turns: int
    total_time_seconds: float
    avg_scenario_time_seconds: float
    overall_p50_turn_seconds: float
    overall_p90_turn_seconds: float
    overall_p95_turn_seconds: float


# -----------------------------
# Scenarios
# -----------------------------

# Type aliases for clarity
Scenarios = List[Tuple[str, List[str]]]
ScenariosByUser = Dict[str, Scenarios]


def default_scenarios() -> ScenariosByUser:
    """
    Return scenarios grouped by username.
    Keys are usernames to evaluate; values are lists of (scenario_name, messages).
    """

    data_path = Path("eval_data.json")
    if not data_path.exists():
        raise FileNotFoundError(
            f"Evaluation data file not found: {data_path.resolve()}. "
            "Please create eval_data.json with scenarios."
        )
    with open(data_path, "r") as f:
        raw = json.load(f)
    # Normalize and validate structure: Dict[str, List[[name, [messages...]]]]
    scenarios_by_user: ScenariosByUser = {}
    if not isinstance(raw, dict):
        raise ValueError("eval_data.json root must be an object mapping usernames to scenarios.")
    for username, scenarios in raw.items():
        normalized: Scenarios = []
        if not isinstance(scenarios, list):
            continue
        for item in scenarios:
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                continue
            name, messages = item
            if not isinstance(messages, list):
                continue
            normalized.append((str(name), [str(m) for m in messages]))
        scenarios_by_user[str(username)] = normalized
    return scenarios_by_user


# -----------------------------
# Helpers
# -----------------------------

def generate_dev_token(username: str) -> str:
    """Create the simple dev token the API expects (base64 JSON with username)."""
    payload = {"username": username}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def percentile(values: List[float], p: float) -> float:
    """Compute percentile for a list of floats. p in [0, 100]."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def ensure_logs_dir() -> Path:
    logs = Path("logs")
    logs.mkdir(exist_ok=True)
    return logs


def post_chat(api_url: str, token: str, message: str, session_id: Optional[str], disable_memory: bool = False, http_timeout: float = 60.0) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Call POST /chat and return (assistant_response, new_or_existing_session_id, error_message).
    """
    headers = {"Authorization": f"Bearer {token}"}
    if disable_memory:
        headers["X-Disable-Memory"] = "1"
    payload: Dict[str, Any] = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    # Simple retry on timeout/transient network errors
    for attempt in range(3):
        try:
            resp = requests.post(f"{api_url}/chat", json=payload, headers=headers, timeout=http_timeout)
            break
        except Exception as e:
            if attempt == 2:
                return None, session_id, f"Request error: {e}"
            time.sleep(1.0 * (attempt + 1))

    if resp.status_code != 200:
        return None, session_id, f"HTTP {resp.status_code}: {resp.text}"

    data = resp.json()
    return data.get("response"), data.get("session_id", session_id), None


# -----------------------------
# LLM Judge (optional)
# -----------------------------

def judge_conversation_gemini(messages: List[TurnResult]) -> Optional[Dict[str, Any]]:
    """
    Use Gemini to score the conversation.
    Prefers Google Cloud service account credentials (Vertex AI) if available,
    otherwise falls back to Google AI Studio API key (GEMINI_API_KEY).
    Returns a dict of scores, or None if disabled/unavailable.
    """
    # Build transcript and prompt first (shared across backends)
    transcript_lines = []
    for t in messages:
        transcript_lines.append(f"User: {t.user_message}")
        if t.assistant_message:
            transcript_lines.append(f"Assistant: {t.assistant_message}")
    transcript = "\n".join(transcript_lines)

    prompt = (
        "You are an impartial evaluator for a food assistant conversation.\n"
        "Given the transcript, output STRICT JSON with fields:\n"
        '{\n'
        '  "helpfulness": 1-5,\n'
        '  "specificity": 1-5,\n'
        '  "grounding": 1-5,\n'
        '  "coherence": 1-5,\n'
        '  "safety": 1-5,\n'
        '  "overall": 1-5,\n'
        '  "comments": "one line rationale"\n'
        "}\n\n"
        "Transcript:\n"
        f"{transcript}\n"
    )

    # 1) Try Vertex AI with service account first if available
    #    Looks for GOOGLE_APPLICATION_CREDENTIALS or local 'service-account-key.json'
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        default_key = Path("service-account-key.json")
        if default_key.exists():
            creds_path = str(default_key.resolve())

    if creds_path and service_account and vertexai and GenerativeModel:
        try:
            # Load project_id from the service account file if not provided separately
            project_id: Optional[str] = None
            try:
                with open(creds_path, "r") as f:
                    key_data = json.load(f)
                    project_id = key_data.get("project_id")
            except Exception:
                project_id = None

            region = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            if project_id:
                vertexai.init(project=project_id, location=region, credentials=credentials)
            else:
                # project is required by vertexai.init; if missing, failover to API key path
                raise ValueError("Missing project_id in service account key")

            model_name = os.getenv("JAMIE_GEMINI_MODEL", "gemini-2.0-flash")
            vaimodel = GenerativeModel(model_name)
            try:
                response = vaimodel.generate_content(prompt)
                text = (getattr(response, "text", None) or "").strip()
            except Exception:
                text = ""

            if text:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        obj = json.loads(text[start : end + 1])
                        return obj
                    except Exception:
                        pass
            # If Vertex call didn't yield usable JSON, drop through to API key fallback
        except Exception:
            # If Vertex init/usage failed for any reason, try API key fallback
            pass

    # 2) Fallback: Google AI Studio API with GEMINI_API_KEY
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return None
    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("JAMIE_GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        print("--------------------------------")
        print(response)
        print("--------------------------------")
        text = (response.text or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        obj = json.loads(text[start : end + 1])
        return obj
    except Exception:
        return None


# -----------------------------
# Runner
# -----------------------------

def run_scenario(
    api_url: str,
    username: str,
    scenario_name: str,
    user_messages: List[str],
    enable_judge: bool,
    disable_memory: bool = False,
    http_timeout: float = 60.0,
    turn_sleep: float = 0.0,
) -> ScenarioResult:
    token = generate_dev_token(username)
    session_id: Optional[str] = None
    turn_results: List[TurnResult] = []

    scenario_start = time.time()
    per_turn_times: List[float] = []

    for idx, msg in enumerate(user_messages, start=1):
        turn_start = time.time()
        assistant, session_id, err = post_chat(api_url, token, msg, session_id, disable_memory=disable_memory, http_timeout=http_timeout)
        elapsed = time.time() - turn_start
        per_turn_times.append(elapsed)

        turn_results.append(
            TurnResult(
                turn_index=idx,
                user_message=msg,
                assistant_message=assistant,
                elapsed_seconds=elapsed,
                error=err,
            )
        )
        # Optional spacing between turns (helps avoid bursty load)
        if turn_sleep > 0:
            time.sleep(turn_sleep)

    total_time = time.time() - scenario_start
    avg_turn = sum(per_turn_times) / len(per_turn_times) if per_turn_times else 0.0

    scores = judge_conversation_gemini(turn_results) if enable_judge else None

    return ScenarioResult(
        scenario_name=scenario_name,
        total_time_seconds=total_time,
        avg_turn_seconds=avg_turn,
        p50_turn_seconds=percentile(per_turn_times, 50),
        p90_turn_seconds=percentile(per_turn_times, 90),
        p95_turn_seconds=percentile(per_turn_times, 95),
        num_turns=len(user_messages),
        conversation=turn_results,
        judge_scores=scores,
    )


def run_all(
    api_url: str,
    username: str,
    scenarios: List[Tuple[str, List[str]]],
    enable_judge: bool,
    disable_memory: bool = False,
    http_timeout: float = 60.0,
    turn_sleep: float = 0.0,
) -> Tuple[List[ScenarioResult], RunSummary]:
    results: List[ScenarioResult] = []
    all_turn_times: List[float] = []

    start = time.time()
    for name, messages in scenarios:
        res = run_scenario(
            api_url,
            username,
            name,
            messages,
            enable_judge,
            disable_memory=disable_memory,
            http_timeout=http_timeout,
            turn_sleep=turn_sleep,
        )
        results.append(res)
        print(res)
        all_turn_times.extend([t.elapsed_seconds for t in res.conversation])
    total_time = time.time() - start

    total_turns = sum(r.num_turns for r in results)
    avg_scenario_time = total_time / len(results) if results else 0.0

    summary = RunSummary(
        timestamp=datetime.utcnow().isoformat() + "Z",
        api_url=api_url,
        user=username,
        total_scenarios=len(results),
        total_turns=total_turns,
        total_time_seconds=total_time,
        avg_scenario_time_seconds=avg_scenario_time,
        overall_p50_turn_seconds=percentile(all_turn_times, 50),
        overall_p90_turn_seconds=percentile(all_turn_times, 90),
        overall_p95_turn_seconds=percentile(all_turn_times, 95),
    )
    return results, summary


def compare_runs(
    off_results: List[ScenarioResult],
    on_results: List[ScenarioResult],
) -> List[Dict[str, Any]]:
    """Compute per-scenario deltas between OFF and ON runs."""
    by_name_on = {r.scenario_name: r for r in on_results}
    comparisons: List[Dict[str, Any]] = []
    for off in off_results:
        on = by_name_on.get(off.scenario_name)
        if not on:
            continue
        def delta(a: float, b: float) -> Tuple[float, Optional[float]]:
            d = b - a
            pct = (d / a * 100.0) if a else None
            return d, pct
        judge_off = off.judge_scores.get("overall") if off.judge_scores else None
        judge_on = on.judge_scores.get("overall") if on.judge_scores else None
        comp = {
            "scenario_name": off.scenario_name,
            "num_turns": off.num_turns,
            "total_time_seconds_off": off.total_time_seconds,
            "total_time_seconds_on": on.total_time_seconds,
            "total_time_seconds_delta": delta(off.total_time_seconds, on.total_time_seconds)[0],
            "avg_turn_seconds_off": off.avg_turn_seconds,
            "avg_turn_seconds_on": on.avg_turn_seconds,
            "avg_turn_seconds_delta": delta(off.avg_turn_seconds, on.avg_turn_seconds)[0],
            "p50_turn_seconds_off": off.p50_turn_seconds,
            "p50_turn_seconds_on": on.p50_turn_seconds,
            "p50_turn_seconds_delta": delta(off.p50_turn_seconds, on.p50_turn_seconds)[0],
            "p90_turn_seconds_off": off.p90_turn_seconds,
            "p90_turn_seconds_on": on.p90_turn_seconds,
            "p90_turn_seconds_delta": delta(off.p90_turn_seconds, on.p90_turn_seconds)[0],
            "p95_turn_seconds_off": off.p95_turn_seconds,
            "p95_turn_seconds_on": on.p95_turn_seconds,
            "p95_turn_seconds_delta": delta(off.p95_turn_seconds, on.p95_turn_seconds)[0],
            "judge_overall_off": judge_off,
            "judge_overall_on": judge_on,
            "judge_overall_delta": (judge_on - judge_off) if (judge_on is not None and judge_off is not None) else None,
            "significance_hint": "likely meaningful" if (judge_on and judge_off and abs(judge_on - judge_off) >= 0.5) else "unclear",
        }
        comparisons.append(comp)
    return comparisons


def save_reports(
    results: List[ScenarioResult],
    summary: RunSummary,
    label: Optional[str] = None,
) -> Tuple[Path, Path]:
    logs_dir = ensure_logs_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    label_part = f"{label}_" if label else ""
    json_path = logs_dir / f"eval_results_{label_part}{ts}.json"
    csv_path = logs_dir / f"eval_summary_{label_part}{ts}.csv"

    # JSON (detailed)
    payload = {
        "summary": asdict(summary),
        "scenarios": [
            {
                **asdict(r),
                "conversation": [asdict(t) for t in r.conversation],
            }
            for r in results
        ],
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    # CSV (scenario-level summary)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "scenario_name",
                "num_turns",
                "total_time_seconds",
                "avg_turn_seconds",
                "p50_turn_seconds",
                "p90_turn_seconds",
                "p95_turn_seconds",
                "judge_overall",
            ]
        )
        for r in results:
            judge_overall = (
                r.judge_scores.get("overall") if r.judge_scores else None
            )
            writer.writerow(
                [
                    r.scenario_name,
                    r.num_turns,
                    f"{r.total_time_seconds:.3f}",
                    f"{r.avg_turn_seconds:.3f}",
                    f"{r.p50_turn_seconds:.3f}",
                    f"{r.p90_turn_seconds:.3f}",
                    f"{r.p95_turn_seconds:.3f}",
                    judge_overall,
                ]
            )

        # Add overall summary row
        writer.writerow([])
        writer.writerow(["overall"] + [""] * 7)
        writer.writerow(["timestamp", summary.timestamp] + [""] * 6)
        writer.writerow(["api_url", summary.api_url] + [""] * 6)
        writer.writerow(["user", summary.user] + [""] * 6)
        writer.writerow(["total_scenarios", summary.total_scenarios] + [""] * 6)
        writer.writerow(["total_turns", summary.total_turns] + [""] * 6)
        writer.writerow(
            ["total_time_seconds", f"{summary.total_time_seconds:.3f}"] + [""] * 6
        )
        writer.writerow(
            ["avg_scenario_time_seconds", f"{summary.avg_scenario_time_seconds:.3f}"]
            + [""] * 6
        )
        writer.writerow(
            ["overall_p50_turn_seconds", f"{summary.overall_p50_turn_seconds:.3f}"]
            + [""] * 6
        )
        writer.writerow(
            ["overall_p90_turn_seconds", f"{summary.overall_p90_turn_seconds:.3f}"]
            + [""] * 6
        )
        writer.writerow(
            ["overall_p95_turn_seconds", f"{summary.overall_p95_turn_seconds:.3f}"]
            + [""] * 6
        )

    return json_path, csv_path


def save_ablation_reports(
    off_results: List[ScenarioResult],
    off_summary: RunSummary,
    on_results: List[ScenarioResult],
    on_summary: RunSummary,
    label: Optional[str] = None,
) -> Tuple[Path, Path]:
    logs_dir = ensure_logs_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    label_part = f"{label}_" if label else ""
    json_path = logs_dir / f"eval_ablation_{label_part}{ts}.json"
    csv_path = logs_dir / f"eval_ablation_{label_part}{ts}.csv"

    comparisons = compare_runs(off_results, on_results)

    payload = {
        "off_summary": asdict(off_summary),
        "on_summary": asdict(on_summary),
        "comparisons": comparisons,
        "off_scenarios": [
            {**asdict(r), "conversation": [asdict(t) for t in r.conversation]} for r in off_results
        ],
        "on_scenarios": [
            {**asdict(r), "conversation": [asdict(t) for t in r.conversation]} for r in on_results
        ],
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    # CSV summary (per-scenario deltas)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "scenario_name",
                "num_turns",
                "avg_turn_seconds_off",
                "avg_turn_seconds_on",
                "avg_turn_seconds_delta",
                "p50_turn_seconds_off",
                "p50_turn_seconds_on",
                "p50_turn_seconds_delta",
                "judge_overall_off",
                "judge_overall_on",
                "judge_overall_delta",
                "significance_hint",
            ]
        )
        for c in comparisons:
            writer.writerow(
                [
                    c["scenario_name"],
                    c["num_turns"],
                    f'{c["avg_turn_seconds_off"]:.3f}',
                    f'{c["avg_turn_seconds_on"]:.3f}',
                    f'{c["avg_turn_seconds_delta"]:.3f}',
                    f'{c["p50_turn_seconds_off"]:.3f}',
                    f'{c["p50_turn_seconds_on"]:.3f}',
                    f'{c["p50_turn_seconds_delta"]:.3f}',
                    c["judge_overall_off"] if c["judge_overall_off"] is not None else "",
                    c["judge_overall_on"] if c["judge_overall_on"] is not None else "",
                    f'{c["judge_overall_delta"]:.3f}' if c["judge_overall_delta"] is not None else "",
                    c["significance_hint"],
                ]
            )

        writer.writerow([])
        writer.writerow(["OFF summary"] + [""] * 11)
        writer.writerow(["timestamp", off_summary.timestamp] + [""] * 10)
        writer.writerow(["overall_p50_turn_seconds", f"{off_summary.overall_p50_turn_seconds:.3f}"] + [""] * 10)
        writer.writerow(["overall_p90_turn_seconds", f"{off_summary.overall_p90_turn_seconds:.3f}"] + [""] * 10)
        writer.writerow(["overall_p95_turn_seconds", f"{off_summary.overall_p95_turn_seconds:.3f}"] + [""] * 10)

        writer.writerow([])
        writer.writerow(["ON summary"] + [""] * 11)
        writer.writerow(["timestamp", on_summary.timestamp] + [""] * 10)
        writer.writerow(["overall_p50_turn_seconds", f"{on_summary.overall_p50_turn_seconds:.3f}"] + [""] * 10)
        writer.writerow(["overall_p90_turn_seconds", f"{on_summary.overall_p90_turn_seconds:.3f}"] + [""] * 10)
        writer.writerow(["overall_p95_turn_seconds", f"{on_summary.overall_p95_turn_seconds:.3f}"] + [""] * 10)

    return json_path, csv_path


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Jamie agent via HTTP API")
    parser.add_argument(
        "--api-url",
        default=os.getenv("JAMIE_API_URL", "http://localhost:8000"),
        help="Base URL of the Jamie API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Enable LLM-as-judge scoring (requires GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--ablate-memory",
        action="store_true",
        help="Run A/B ablation: memory OFF (header X-Disable-Memory=1) then ON, and produce a single comparison report",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("JAMIE_HTTP_TIMEOUT", "120")),
        help="HTTP client timeout seconds per request (default from JAMIE_HTTP_TIMEOUT=120)",
    )
    parser.add_argument(
        "--turn-sleep",
        type=float,
        default=float(os.getenv("JAMIE_EVAL_TURN_SLEEP", "0")),
        help="Seconds to sleep between turns (helps avoid burst load).",
    )
    parser.add_argument(
        "--force-disable-memory",
        action="store_true",
        help="Force memory OFF for all requests (overrides ablation).",
    )
    return parser.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv)

    scenarios = default_scenarios()

    from dotenv import load_dotenv
    load_dotenv()

    print("🍽️  Jamie Evaluation Runner")
    print("=" * 50)
    print(f"API URL: {args.api_url}")
    print(f"Judge:   {'enabled' if args.judge else 'disabled'}")
    print(f"Ablation:{'enabled' if args.ablate_memory else 'disabled'}")
    print(f"Turn sleep: {args.turn_sleep}s")
    run_users = list(scenarios.keys())
    total_scenarios = sum(len(scenarios[u]) for u in run_users if u in scenarios)
    print(f"Users:    {', '.join(run_users)}")
    print(f"Per-user scenarios: yes (total {total_scenarios} across {len(run_users)} users)")
    print("=" * 50)

    try:
        # Multi-user evaluation only
        for username in run_users:
            user_scenarios = scenarios.get(username)
            if not user_scenarios:
                print(f"⚠️  Skipping unknown user '{username}' (not present in scenarios mapping)")
                continue

            print(f"\n👤 User: {username} — {len(user_scenarios)} scenarios")
            if args.ablate_memory:
                print("🔧 Run A: Memory OFF")
                off_results, off_summary = run_all(
                    args.api_url,
                    username,
                    user_scenarios,
                    args.judge,
                    disable_memory=True,
                    http_timeout=args.timeout,
                    turn_sleep=args.turn_sleep,
                )

                print("🔧 Run B: Memory ON")
                on_results, on_summary = run_all(
                    args.api_url,
                    username,
                    user_scenarios,
                    args.judge,
                    disable_memory=False,
                    http_timeout=args.timeout,
                    turn_sleep=args.turn_sleep,
                )

                json_path, csv_path = save_ablation_reports(
                    off_results, off_summary, on_results, on_summary, label=username
                )
            else:
                results, summary = run_all(
                    args.api_url,
                    username,
                    user_scenarios,
                    args.judge,
                    http_timeout=args.timeout,
                    turn_sleep=args.turn_sleep,
                )
                json_path, csv_path = save_reports(results, summary, label=username)

        print("\n🎉 Evaluation completed!")
        # When running multiple users, the last run's paths/summary variables will be shown below.
        # We still print them as a convenience; full per-user file names include the username.
        if args.ablate_memory:
            print(f"📝 Ablation JSON (last):   {json_path}")
            print(f"🧾 Ablation CSV (last):    {csv_path}\n")
        # For multi-user, per-user details are in the individual files.
        print(f"📝 Detailed JSON (last):   {json_path}")
        print(f"🧾 Summary CSV (last):     {csv_path}\n")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


