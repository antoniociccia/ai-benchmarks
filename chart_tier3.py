#!/usr/bin/env python3
"""Generate LinkedIn charts for tier 3 (standard large) benchmark results."""

import json
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from collections import defaultdict

with open("results/benchmark_20260313_143605.json") as f:
    data = json.load(f)

ms = defaultdict(lambda: {"total": 0, "max": 0, "lats": [], "cost": 0, "tests": {}})
for r in data:
    m = r["model_short"]
    ms[m]["total"] += r["score"]
    ms[m]["max"] += r["max_score"]
    ms[m]["lats"].append(r["latency_s"])
    ms[m]["cost"] += r.get("cost_usd", 0)
    ms[m]["tests"][r["test_name"]] = r["score"]

ranked = sorted(ms.items(), key=lambda x: x[1]["total"], reverse=True)

friendly = {
    "claude-opus-4.5": "Claude Opus 4.5",
    "deepseek-v3.2": "DeepSeek v3.2",
    "qwen3.5-flash-02-23": "Qwen 3.5 Flash",
    "qwen3.5-397b-a17b": "Qwen 3.5 397B",
    "mistral-large-2512": "Mistral Large",
}

models = [friendly.get(m, m) for m, _ in ranked]
scores = [d["total"] for _, d in ranked]
pcts = [d["total"] / d["max"] * 100 for _, d in ranked]
avg_lats = [sum(d["lats"]) / len(d["lats"]) for _, d in ranked]
costs = [d["cost"] for _, d in ranked]

colors = ["#E07A5F", "#4A90D9", "#F2CC8F", "#5B5EA6", "#81B29A"]

# --- CHART 1: Leaderboard ---
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor("#0D1117")
ax.set_facecolor("#0D1117")

y_pos = np.arange(len(models))
bars = ax.barh(y_pos, scores, color=colors, height=0.6, edgecolor="none")

for i, (bar, score, pct, lat, cost) in enumerate(zip(bars, scores, pcts, avg_lats, costs)):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            f"{score:.1f}/110  ({pct:.0f}%)   {lat:.0f}s avg   ${cost:.3f}",
            va="center", ha="left", fontsize=11, color="white", fontweight="bold")

ax.set_yticks(y_pos)
ax.set_yticklabels(models, fontsize=13, fontweight="bold", color="white")
ax.invert_yaxis()
ax.set_xlim(0, 130)
ax.tick_params(axis="x", colors="#555555")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color("#333333")
ax.spines["left"].set_color("#333333")
ax.xaxis.set_major_formatter(mticker.NullFormatter())

ax.set_title("Tier 3 — Standard Large (no reasoning)\n11 tests  |  automated scoring  |  temperature 0",
             fontsize=16, fontweight="bold", color="white", pad=20)

fig.text(0.98, 0.02, "github.com/antoniociccia/ai-benchmarks", ha="right",
         fontsize=9, color="#666666", style="italic")

plt.tight_layout()
plt.savefig("chart_tier3_leaderboard.png", dpi=200, facecolor="#0D1117",
            bbox_inches="tight", pad_inches=0.3)
print("Saved: chart_tier3_leaderboard.png")

# --- CHART 2: Heatmap ---
test_names_ordered = [
    "Multi-step Combinatorics",
    "N-Queens Solver",
    "Dijkstra 3-Bug Fix",
    "Einstein's Riddle (Extended)",
    "Messy Email \u2192 Structured JSON",
    "Legal IT\u2192EN Translation",
    "Constrained Creative Writing",
    "Exact Instruction Following",
    "Advanced Factual Knowledge",
    "DP Optimization Challenge",
    "K-Harmonic Graph Coloring (Custom Problem)",
]

short_names = [
    "Combinatorics",
    "N-Queens",
    "Dijkstra Debug",
    "Einstein's Riddle",
    "Email \u2192 JSON",
    "Legal Translation",
    "Creative Writing",
    "Instruction Following",
    "Factual Knowledge",
    "DP Optimization",
    "Graph Coloring",
]

fig2, ax2 = plt.subplots(figsize=(14, 7))
fig2.patch.set_facecolor("#0D1117")
ax2.set_facecolor("#0D1117")

matrix = []
for m, d in ranked:
    row = [d["tests"].get(tn, 0) for tn in test_names_ordered]
    matrix.append(row)

matrix = np.array(matrix)

im = ax2.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=10)

for i in range(len(models)):
    for j in range(len(short_names)):
        val = matrix[i, j]
        color = "white" if val < 4 else "black"
        ax2.text(j, i, f"{val:.0f}" if val == int(val) else f"{val:.1f}",
                 ha="center", va="center", fontsize=10, fontweight="bold", color=color)

ax2.set_xticks(np.arange(len(short_names)))
ax2.set_xticklabels(short_names, rotation=45, ha="right", fontsize=10, color="white")
ax2.set_yticks(np.arange(len(models)))
ax2.set_yticklabels(models, fontsize=12, fontweight="bold", color="white")

ax2.set_title("Tier 3 — Per Test Breakdown (score out of 10)",
              fontsize=16, fontweight="bold", color="white", pad=20)

ax2.tick_params(axis="both", which="both", length=0)
for spine in ax2.spines.values():
    spine.set_visible(False)

cbar = plt.colorbar(im, ax=ax2, shrink=0.6, pad=0.02)
cbar.ax.tick_params(colors="white")
cbar.set_label("Score", color="white", fontsize=11)

fig2.text(0.98, 0.02, "github.com/antoniociccia/ai-benchmarks", ha="right",
          fontsize=9, color="#666666", style="italic")

plt.tight_layout()
plt.savefig("chart_tier3_heatmap.png", dpi=200, facecolor="#0D1117",
            bbox_inches="tight", pad_inches=0.3)
print("Saved: chart_tier3_heatmap.png")
