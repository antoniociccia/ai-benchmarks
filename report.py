"""
Report generation — terminal summary, JSON/CSV export.
"""

import json
import csv
import os
from collections import defaultdict


def print_summary(results: list[dict]):
    """Print a formatted summary table to terminal."""
    model_scores = defaultdict(lambda: {
        "total": 0, "max": 0, "tests": {}, "latencies": [], "cost": 0.0,
        "tokens_prompt": 0, "tokens_completion": 0,
    })

    for r in results:
        m = r["model_short"]
        model_scores[m]["total"] += r["score"]
        model_scores[m]["max"] += r["max_score"]
        model_scores[m]["latencies"].append(r["latency_s"])
        model_scores[m]["tests"][r["test_name"]] = r["score"]
        model_scores[m]["cost"] += r.get("cost_usd", 0)
        model_scores[m]["tokens_prompt"] += r.get("tokens_prompt", 0)
        model_scores[m]["tokens_completion"] += r.get("tokens_completion", 0)

    ranked = sorted(model_scores.items(), key=lambda x: x[1]["total"], reverse=True)

    test_names = []
    seen = set()
    for r in results:
        if r["test_name"] not in seen:
            test_names.append(r["test_name"])
            seen.add(r["test_name"])

    # Leaderboard
    print(f"\n{'='*90}")
    print(f"  LEADERBOARD")
    print(f"{'='*90}")
    print(f"  {'Rank':<5} {'Model':<30} {'Score':>8} {'Avg Lat':>9} {'Tokens':>12} {'Cost':>10}")
    print(f"  {'─'*5} {'─'*30} {'─'*8} {'─'*9} {'─'*12} {'─'*10}")

    total_cost = 0.0
    for rank, (model, data) in enumerate(ranked, 1):
        avg_lat = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0
        pct = (data["total"] / data["max"] * 100) if data["max"] else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        tok_total = data["tokens_prompt"] + data["tokens_completion"]
        cost = data["cost"]
        total_cost += cost
        print(f"  {rank:<5} {model:<30} {data['total']:>5.1f}/{data['max']:<3} {avg_lat:>7.1f}s {tok_total:>10,} ${cost:>8.4f}")
        print(f"        {bar} {pct:.0f}%")

    print(f"\n  {'TOTAL COST':>50} ${total_cost:.4f}")
    print(f"  {'Total tokens':>50} {sum(d['tokens_prompt']+d['tokens_completion'] for _,d in ranked):,}")

    # Per-test breakdown
    print(f"\n{'='*80}")
    print(f"  PER-TEST BREAKDOWN")
    print(f"{'='*80}")

    for test_name in test_names:
        print(f"\n  📋 {test_name}")
        test_results = [(r["model_short"], r["score"], r["max_score"], r["latency_s"],
                         r.get("cost_usd", 0), r.get("tokens_prompt", 0) + r.get("tokens_completion", 0),
                         r["validation_details"])
                        for r in results if r["test_name"] == test_name]
        test_results.sort(key=lambda x: x[1], reverse=True)
        for model, score, max_s, lat, cost, toks, details in test_results:
            marker = "✅" if score == max_s else "⚠️" if score > 0 else "❌"
            cost_str = f"${cost:.4f}" if cost > 0 else "$-.----"
            print(f"    {marker} {model:<30} {score:>5.1f}/{max_s}  {lat:>6.1f}s  {toks:>8,} tok  {cost_str}")
            if score < max_s:
                print(f"       └─ {details[:120]}")

    # Best model per category
    print(f"\n{'='*80}")
    print(f"  BEST MODEL PER CATEGORY")
    print(f"{'='*80}")

    cat_scores = defaultdict(list)
    for r in results:
        cat_scores[r["category"]].append((r["model_short"], r["score"], r["latency_s"]))

    for cat, entries in sorted(cat_scores.items()):
        best = max(entries, key=lambda x: (x[1], -x[2]))
        print(f"  {cat:<25} → {best[0]} ({best[1]:.1f}/10, {best[2]:.1f}s)")


def save_results(results: list[dict], output_dir: str, timestamp: str) -> str:
    """Save results as JSON (with full responses) and CSV. Returns JSON path."""
    os.makedirs(output_dir, exist_ok=True)

    # JSON — everything, including full model responses
    json_path = os.path.join(output_dir, f"benchmark_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # CSV — summary for quick analysis
    csv_path = os.path.join(output_dir, f"benchmark_{timestamp}.csv")
    fields = [
        "model", "model_short", "test_name", "category",
        "score", "max_score", "latency_s",
        "tokens_prompt", "tokens_completion", "cost_usd",
        "error", "validation_details", "timestamp",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})

    # Per-model response dump — one file per model with full responses
    responses_dir = os.path.join(output_dir, f"responses_{timestamp}")
    os.makedirs(responses_dir, exist_ok=True)
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model_short"]].append(r)
    for model_short, model_results in by_model.items():
        safe_name = model_short.replace("/", "_").replace(" ", "_")
        model_path = os.path.join(responses_dir, f"{safe_name}.json")
        with open(model_path, "w") as f:
            json.dump(model_results, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {json_path}")
    print(f"  Saved: {csv_path}")
    print(f"  Saved: {responses_dir}/ (full responses per model)")
    return json_path
