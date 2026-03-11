"""
Configuration for LLM Benchmark Suite.
Models, API settings, and test parameters.
"""

import os
from pathlib import Path

# Load .env if present (no external deps needed)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# ═══════════════════════════════════════════════════════════════
#  REASONING MODELS (thinking / chain-of-thought)
# ═══════════════════════════════════════════════════════════════

# Frontier Reasoning — massima qualità, costo alto
REASONING_FRONTIER = [
    "anthropic/claude-opus-4.6",
    "google/gemini-3.1-pro-preview",
    "deepseek/deepseek-v3.2",
    "qwen/qwen3-max-thinking",
    "openai/gpt-5.4",
]

# Fast Reasoning — reasoning ma più veloci/economici
REASONING_FAST = [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.4",
    "google/gemini-3-flash-preview",
    "bytedance-seed/seed-1.6",
    "bytedance-seed/seed-2.0-mini",
]

# ═══════════════════════════════════════════════════════════════
#  STANDARD MODELS (no explicit reasoning)
# ═══════════════════════════════════════════════════════════════

# Standard Large — modelli grossi senza reasoning esplicito
STANDARD_LARGE = [
    "anthropic/claude-opus-4.5",
    "deepseek/deepseek-v3.2-speciale",
    "mistralai/mistral-large-2512",
    "qwen/qwen3.5-397b-a17b",
    "qwen/qwen3.5-flash-02-23",
]

# Standard Small — modelli compatti/efficienti
STANDARD_SMALL = [
    "mistralai/devstral-2512",
    "mistralai/ministral-14b-2512",
    "liquid/lfm-2-24b-a2b",
    "nvidia/nemotron-3-nano-30b-a3b",
    "google/gemini-3.1-flash-lite-preview",
]

# ═══════════════════════════════════════════════════════════════
#  Grouped views
# ═══════════════════════════════════════════════════════════════
REASONING_MODELS = REASONING_FRONTIER + REASONING_FAST
STANDARD_MODELS = STANDARD_LARGE + STANDARD_SMALL
ALL_MODELS = REASONING_MODELS + STANDARD_MODELS

TIERS = {
    "reasoning_frontier": REASONING_FRONTIER,
    "reasoning_fast":     REASONING_FAST,
    "standard_large":     STANDARD_LARGE,
    "standard_small":     STANDARD_SMALL,
}

# How many times to repeat each test for averaging
REPEAT_RUNS = 1

# Max tokens for responses
MAX_TOKENS = 16384

# Timeout per request (seconds)
REQUEST_TIMEOUT = 300

# ═══════════════════════════════════════════════════════════════
#  Pricing (USD per 1M tokens) — fetched from OpenRouter API, March 2026
#  Source: https://openrouter.ai/api/v1/models → pricing.prompt / pricing.completion
#  OpenRouter returns per-token prices; we store per-1M for readability.
# ═══════════════════════════════════════════════════════════════
PRICING = {
    # model_id:                             (prompt/1M,  completion/1M)
    "anthropic/claude-opus-4.6":            (5.00,  25.00),
    "anthropic/claude-sonnet-4.6":          (3.00,  15.00),
    "anthropic/claude-opus-4.5":            (5.00,  25.00),
    "openai/gpt-5.4":                       (2.50,  15.00),
    "google/gemini-3.1-pro-preview":        (2.00,  12.00),
    "google/gemini-3-flash-preview":        (0.50,   3.00),
    "google/gemini-3.1-flash-lite-preview": (0.25,   1.50),
    "deepseek/deepseek-v3.2":              (0.25,   0.40),
    "deepseek/deepseek-v3.2-speciale":     (0.40,   1.20),
    "qwen/qwen3-max-thinking":             (0.78,   3.90),
    "qwen/qwen3.5-397b-a17b":             (0.39,   2.34),
    "qwen/qwen3.5-flash-02-23":           (0.10,   0.40),
    "mistralai/mistral-large-2512":        (0.50,   1.50),
    "mistralai/devstral-2512":             (0.40,   2.00),
    "mistralai/ministral-14b-2512":        (0.20,   0.20),
    "liquid/lfm-2-24b-a2b":               (0.03,   0.12),
    "nvidia/nemotron-3-nano-30b-a3b":      (0.05,   0.20),
    "bytedance-seed/seed-1.6":             (0.25,   2.00),
    "bytedance-seed/seed-2.0-mini":        (0.10,   0.40),
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in USD for a single API call."""
    if model not in PRICING:
        return 0.0
    p_rate, c_rate = PRICING[model]
    return (prompt_tokens * p_rate + completion_tokens * c_rate) / 1_000_000
