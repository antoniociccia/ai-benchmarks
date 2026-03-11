# AI Benchmarks

Open-source benchmark suite for comparing LLM models head-to-head. 11 hard tests, automated validation, cost tracking.

All models receive the same prompt at temperature 0. Scoring is fully automated — no subjective evaluation.

## Tests

| # | Test | Category | Validation |
|---|------|----------|------------|
| 1 | Multi-step Combinatorics | Math/Logic | Exact numerical answer |
| 2 | N-Queens Solver | Code Generation | Code execution + assertions (n=1,4,8,10,12) |
| 3 | Dijkstra 3-Bug Fix | Code Debugging | Code execution + 4 test cases |
| 4 | Einstein's Riddle | Logic Reasoning | 25 cells verified individually |
| 5 | Messy Email → JSON | Data Extraction | Schema + 8 value checks with FX conversion |
| 6 | Legal Translation IT→EN | Translation | 19 technical terms matched |
| 7 | Constrained Creative Writing | Creative | 9 formal constraints checked |
| 8 | Exact Instruction Following | Instruction | 7 lines validated (IPv4 primes, NATO, MD5, 2^64) |
| 9 | Advanced Factual Knowledge | Knowledge | 10 questions, exact answers |
| 10 | DP Optimization | Code Optimization | Correctness + performance under 2s |
| 11 | K-Harmonic Graph Coloring | Advanced Reasoning | Custom problem + self-verification code + optimality proof |

Test 11 is a **custom constraint-satisfaction problem** designed to test autonomous reasoning. The model must solve it, write verification code, and prove optimality by exhaustive search.

## Models (20 across 4 tiers)

| Tier | Models |
|------|--------|
| **Reasoning Frontier** | Claude Opus 4.6, Gemini 3.1 Pro, DeepSeek v3.2, Qwen3 Max Thinking, GPT-5.4 |
| **Reasoning Fast** | Claude Sonnet 4.6, GPT-5.4, Gemini 3 Flash, Seed 1.6, Seed 2.0 Mini |
| **Standard Large** | Claude Opus 4.5, DeepSeek v3.2, Mistral Large, Qwen 3.5 397B, Qwen 3.5 Flash |
| **Standard Small** | Devstral, Ministral 14B, Liquid LFM2 24B, Nemotron Nano 30B, Gemini Flash Lite |

**Notes:**
- DeepSeek v3.2 Speciale was excluded due to persistent rate limiting (HTTP 429) on OpenRouter, making reliable benchmarking impractical.
- GPT-5.4-pro was excluded because response times exceeded the 300s timeout on most tests, making it unsuitable for automated benchmarking.

## Quick Start

```bash
# Clone
git clone https://github.com/antoniociccia/ai-benchmarks.git
cd ai-benchmarks

# Setup
pip install -r requirements.txt
echo "OPENROUTER_API_KEY=sk-or-..." > .env

# Run
python benchmark.py --tier reasoning_frontier    # one tier (5 models × 11 tests)
python benchmark.py                              # all 20 models (220 API calls)
python benchmark.py --dry-run                    # preview without API calls
```

## Options

```
--tier {reasoning_frontier,reasoning_fast,standard_large,standard_small}
--model provider/model-name        # specific model(s)
--test 1 5 11                      # specific tests (1-indexed)
--workers 5                        # parallel workers (default: 5)
--sequential                       # disable parallelism
--repeats 3                        # repeat each test for averaging
```

## Output

Results are saved to `results/` as JSON (full responses) and CSV (summary).

Each result includes: score, latency, token counts, cost in USD, full model response, and validation details.

## Cost Tracking

Pricing is fetched from the OpenRouter API. Each API call is tracked with prompt/completion tokens and cost in USD.

## How It Works

1. **benchmark.py** — orchestrator, runs models in parallel
2. **runner.py** — OpenRouter client with retry + exponential backoff on 429/5xx
3. **tests.py** — 11 test definitions with validation functions
4. **config.py** — models, tiers, pricing, settings
5. **report.py** — terminal summary, JSON/CSV export

## Contributing

Add new tests in `tests.py` following the existing pattern. Each test returns a dict with `name`, `category`, `prompt`, and `validate(response)` function.

Add new models in `config.py` by adding the OpenRouter model ID to the appropriate tier.

## License

MIT
