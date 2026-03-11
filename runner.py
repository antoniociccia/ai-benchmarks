"""
OpenRouter API runner — sends prompts, measures timing, collects results.
Includes retry with exponential backoff for 429/5xx errors.
"""

import time
import requests
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MAX_TOKENS, REQUEST_TIMEOUT

MAX_RETRIES = 3
RETRY_BACKOFF = [10, 30, 60]  # seconds to wait per retry


def call_model(model: str, prompt: str) -> dict:
    """
    Call a model via OpenRouter with automatic retry on 429/5xx.
    Returns:
    {
        "model": str,
        "response": str,
        "latency_s": float,
        "tokens_prompt": int,
        "tokens_completion": int,
        "error": str | None
    }
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/benchmark-llm",
        "X-Title": "LLM Benchmark Suite",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,  # deterministic for reproducibility
    }

    result = {
        "model": model,
        "response": "",
        "latency_s": 0.0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "error": None,
    }

    for attempt in range(MAX_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            resp = requests.post(
                OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            result["latency_s"] = round(time.perf_counter() - t0, 3)

            # Retry on 429 (rate limit) or 5xx (server error)
            if resp.status_code in (429, 500, 502, 503, 529) and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"[retry {attempt+1}/{MAX_RETRIES} in {wait}s — HTTP {resp.status_code}]", end=" ", flush=True)
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
                return result

            data = resp.json()

            if "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))[:300] if isinstance(data["error"], dict) else str(data["error"])[:300]
                # Retry on provider errors (often transient)
                if attempt < MAX_RETRIES and any(kw in err_msg.lower() for kw in ["rate", "limit", "overload", "capacity", "429"]):
                    wait = RETRY_BACKOFF[attempt]
                    print(f"[retry {attempt+1}/{MAX_RETRIES} in {wait}s — {err_msg[:60]}]", end=" ", flush=True)
                    time.sleep(wait)
                    continue
                result["error"] = err_msg
                return result

            choice = data.get("choices", [{}])[0]
            result["response"] = choice.get("message", {}).get("content", "") or ""

            usage = data.get("usage", {})
            result["tokens_prompt"] = usage.get("prompt_tokens", 0)
            result["tokens_completion"] = usage.get("completion_tokens", 0)
            return result

        except requests.exceptions.Timeout:
            result["latency_s"] = round(time.perf_counter() - t0, 3)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"[retry {attempt+1}/{MAX_RETRIES} in {wait}s — timeout]", end=" ", flush=True)
                time.sleep(wait)
                continue
            result["error"] = f"TIMEOUT after {REQUEST_TIMEOUT}s (all retries exhausted)"
        except requests.exceptions.ConnectionError as e:
            result["latency_s"] = round(time.perf_counter() - t0, 3)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"[retry {attempt+1}/{MAX_RETRIES} in {wait}s — connection error]", end=" ", flush=True)
                time.sleep(wait)
                continue
            result["error"] = f"Connection error: {str(e)[:300]}"
        except requests.exceptions.RequestException as e:
            result["latency_s"] = round(time.perf_counter() - t0, 3)
            result["error"] = str(e)[:300]
            return result

    return result
