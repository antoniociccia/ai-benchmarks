#!/usr/bin/env python3
"""
Main benchmark orchestrator.
Usage:
    python benchmark.py                     # run all models, all tests
    python benchmark.py --tier reasoning_frontier  # run one tier
    python benchmark.py --model anthropic/claude-sonnet-4.6  # run one model
    python benchmark.py --test 1 3 5        # run specific tests (1-indexed)
    python benchmark.py --dry-run           # show what would run, no API calls
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import ALL_MODELS, TIERS, REPEAT_RUNS, cost_usd
from tests import get_all_tests
from runner import call_model
from report import print_summary, save_results


def _run_single(model: str, test: dict, run_i: int) -> dict:
    """Run a single model×test combination. Thread-safe."""
    model_short = model.split("/")[-1]
    api_result = call_model(model, test["prompt"])

    if api_result["error"]:
        validation = {"score": 0, "max_score": 10, "details": f"API error: {api_result['error'][:200]}"}
    elif not api_result["response"]:
        validation = {"score": 0, "max_score": 10, "details": "empty response from model"}
    else:
        try:
            validation = test["validate"](api_result["response"])
        except Exception as e:
            validation = {"score": 0, "max_score": 10, "details": f"validation error: {str(e)[:200]}"}

    tok_p = api_result["tokens_prompt"]
    tok_c = api_result["tokens_completion"]
    usd = cost_usd(model, tok_p, tok_c)

    return {
        "model": model,
        "model_short": model_short,
        "test_name": test["name"],
        "category": test["category"],
        "prompt": test["prompt"],
        "run": run_i + 1,
        "score": validation["score"],
        "max_score": validation["max_score"],
        "latency_s": api_result["latency_s"],
        "tokens_prompt": tok_p,
        "tokens_completion": tok_c,
        "cost_usd": round(usd, 6),
        "error": api_result["error"],
        "validation_details": validation["details"],
        "response_full": api_result["response"] or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_benchmark(models: list[str], tests: list[dict], repeats: int = 1,
                  parallel: bool = True, max_workers: int = 5) -> list[dict]:
    """Run all tests against all models. Parallel by default (1 thread per model)."""
    import threading

    # Build all jobs
    jobs = []
    for model in models:
        for test in tests:
            for run_i in range(repeats):
                jobs.append((model, test, run_i))

    total = len(jobs)
    results = []
    lock = threading.Lock()
    done_count = [0]  # mutable for closure

    if not parallel:
        # Sequential fallback
        for model, test, run_i in jobs:
            done_count[0] += 1
            model_short = model.split("/")[-1]
            print(f"  [{done_count[0]}/{total}] {model_short} × {test['name']}", end=" ... ", flush=True)
            r = _run_single(model, test, run_i)
            if r["error"]:
                print(f"ERROR: {r['error'][:60]}")
            else:
                print(f"{r['score']}/{r['max_score']}  ({r['latency_s']}s)")
            results.append(r)
        return results

    # Parallel execution
    print(f"\n  Running {total} jobs with {max_workers} parallel workers...\n")

    def _worker(model, test, run_i):
        r = _run_single(model, test, run_i)
        with lock:
            done_count[0] += 1
            n = done_count[0]
            model_short = model.split("/")[-1]
            if r["error"]:
                status = f"ERROR: {r['error'][:50]}"
            else:
                cost_str = f"${r['cost_usd']:.4f}" if r['cost_usd'] > 0 else ""
                status = f"{r['score']}/{r['max_score']}  ({r['latency_s']}s) {cost_str}"
            print(f"  [{n}/{total}] {model_short:<30} × {test['name']:<45} {status}")
            results.append(r)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for model, test, run_i in jobs:
            futures.append(executor.submit(_worker, model, test, run_i))
        # Wait for all to complete
        for f in futures:
            f.result()  # raises exceptions if any

    return results


def main():
    parser = argparse.ArgumentParser(description="LLM Benchmark Suite")
    parser.add_argument("--tier", choices=list(TIERS.keys()), help="Run only one tier")
    parser.add_argument("--model", type=str, nargs="+", help="Run specific model(s)")
    parser.add_argument("--test", type=int, nargs="+", help="Run specific tests (1-indexed)")
    parser.add_argument("--repeats", type=int, default=REPEAT_RUNS, help="Repeats per test")
    parser.add_argument("--dry-run", action="store_true", help="Show plan, no API calls")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument("--sequential", action="store_true", help="Run sequentially (default: parallel)")
    parser.add_argument("--workers", type=int, default=5, help="Max parallel workers (default: 5)")
    args = parser.parse_args()

    # Resolve models
    if args.model:
        models = args.model
    elif args.tier:
        models = TIERS[args.tier]
    else:
        models = ALL_MODELS

    # Resolve tests
    all_tests = get_all_tests()
    if args.test:
        tests = [all_tests[i - 1] for i in args.test if 1 <= i <= len(all_tests)]
    else:
        tests = all_tests

    # Check API key
    from config import OPENROUTER_API_KEY
    if not OPENROUTER_API_KEY and not args.dry_run:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.")
        print("  export OPENROUTER_API_KEY='sk-or-...'")
        sys.exit(1)

    # Summary
    print(f"\n{'#'*60}")
    print(f"  LLM BENCHMARK SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#'*60}")
    print(f"\n  Models:  {len(models)}")
    print(f"  Tests:   {len(tests)}")
    print(f"  Repeats: {args.repeats}")
    print(f"  Total API calls: {len(models) * len(tests) * args.repeats}")
    print()

    for i, t in enumerate(tests, 1):
        print(f"  Test {i:2d}: {t['name']} [{t['category']}]")
    print()
    for m in models:
        tier_name = next((k for k, v in TIERS.items() if m in v), "unknown")
        print(f"  • {m}  ({tier_name})")

    if args.dry_run:
        print("\n  [DRY RUN — no API calls made]")
        return

    print(f"\n{'─'*60}")
    if not args.dry_run and sys.stdin.isatty():
        input("  Press ENTER to start (Ctrl+C to abort)... ")
    print()

    # Run
    results = run_benchmark(
        models, tests,
        repeats=args.repeats,
        parallel=not args.sequential,
        max_workers=args.workers,
    )

    # Save
    os.makedirs(args.output, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = save_results(results, args.output, ts)

    # Print summary
    print_summary(results)

    print(f"\n  Full results: {filepath}")


if __name__ == "__main__":
    main()
