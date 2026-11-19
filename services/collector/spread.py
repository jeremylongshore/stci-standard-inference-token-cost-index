"""
STCI Neocloud Spread - what the same open-weight model costs across providers.

An open-weight model is sold by many inference providers at once. OpenRouter
lists each provider endpoint with its own price and serving precision
(fp4, fp8, bf16, ...). The spread between the cheapest and the dearest
endpoint for one model is a direct read on how commoditized that model is,
and the precision of the cheapest endpoint shows that a cheaper token is not
always the same token.

Methodology 2.0.0. Output: data/spread/{date}.json

Usage:
    python -m services.collector.spread                    # today, from observations
    python -m services.collector.spread --date 2026-11-19
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model_id}/endpoints"
METHODOLOGY_VERSION = "2.0.0"
DEFAULT_OUTPUT_RATIO = 3.0
DEFAULT_MIN_ENDPOINTS = 4
DECIMALS = 4


def blended(input_rate: float, output_rate: float, output_ratio: float) -> float:
    """Blended $/1M at output_ratio:1 output:input, as the indexer computes it."""
    return (input_rate + output_ratio * output_rate) / (1 + output_ratio)


def percentile(sorted_values: List[float], fraction: float) -> float:
    """Linear-interpolated percentile of an ascending list (deterministic)."""
    if not sorted_values:
        raise ValueError("percentile of empty list")
    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize_endpoints(
    model_id: str,
    endpoints: List[dict],
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    min_endpoints: int = DEFAULT_MIN_ENDPOINTS,
) -> Optional[dict]:
    """
    Summarize one model's provider endpoints, or None if too few are priced.

    Endpoints with a missing, non-numeric, negative or all-zero price are
    ignored: they are free tiers or routers, not a price anyone pays.
    """
    priced = []
    for endpoint in endpoints:
        pricing = endpoint.get("pricing") or {}
        try:
            input_rate = float(pricing["prompt"]) * 1_000_000
            output_rate = float(pricing["completion"]) * 1_000_000
        except (KeyError, TypeError, ValueError):
            continue
        if input_rate < 0 or output_rate < 0 or (input_rate == 0 and output_rate == 0):
            continue
        priced.append(
            {
                "provider": endpoint.get("provider_name") or "unknown",
                "quantization": endpoint.get("quantization") or "unknown",
                "blended": blended(input_rate, output_rate, output_ratio),
            }
        )

    if len(priced) < min_endpoints:
        return None

    priced.sort(key=lambda e: (e["blended"], e["provider"], e["quantization"]))
    rates = [e["blended"] for e in priced]
    low, high = rates[0], rates[-1]
    p25, p75 = percentile(rates, 0.25), percentile(rates, 0.75)

    mix: Dict[str, int] = {}
    for e in priced:
        mix[e["quantization"]] = mix.get(e["quantization"], 0) + 1

    cheapest = priced[0]
    return {
        "model_id": model_id,
        "endpoints": len(priced),
        "providers": len({e["provider"] for e in priced}),
        "min_blended": round(low, DECIMALS),
        "p25_blended": round(p25, DECIMALS),
        "median_blended": round(percentile(rates, 0.5), DECIMALS),
        "p75_blended": round(p75, DECIMALS),
        "max_blended": round(high, DECIMALS),
        "max_min_ratio": round(high / low, 2) if low > 0 else None,
        "p75_p25_ratio": round(p75 / p25, 2) if p25 > 0 else None,
        "quantization_mix": dict(sorted(mix.items())),
        "cheapest": {
            "provider": cheapest["provider"],
            "quantization": cheapest["quantization"],
            "blended": round(cheapest["blended"], DECIMALS),
        },
    }


def compute_spread(
    target_date: date,
    summaries: List[dict],
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    errors: Optional[List[str]] = None,
) -> dict:
    """Assemble the daily spread document from per-model summaries."""
    models = sorted(summaries, key=lambda m: (-m["endpoints"], m["model_id"]))
    ratios = sorted(m["max_min_ratio"] for m in models if m["max_min_ratio"] is not None)
    iqr = sorted(m["p75_p25_ratio"] for m in models if m["p75_p25_ratio"] is not None)

    summary: dict = {"models_measured": len(models), "fetch_errors": len(errors or [])}
    if ratios:
        widest = max(
            (m for m in models if m["max_min_ratio"] is not None),
            key=lambda m: (m["max_min_ratio"], m["endpoints"]),
        )
        summary["median_max_min_ratio"] = round(percentile(ratios, 0.5), 2)
        summary["median_p75_p25_ratio"] = round(percentile(iqr, 0.5), 2) if iqr else None
        summary["widest"] = {
            "model_id": widest["model_id"],
            "max_min_ratio": widest["max_min_ratio"],
            "endpoints": widest["endpoints"],
        }
        summary["most_endpoints"] = {
            "model_id": models[0]["model_id"],
            "endpoints": models[0]["endpoints"],
            "providers": models[0]["providers"],
            "max_min_ratio": models[0]["max_min_ratio"],
        }

    return {
        "date": target_date.isoformat(),
        "methodology_version": METHODOLOGY_VERSION,
        "blend": {"output_ratio": output_ratio},
        "source": "OpenRouter /api/v1/models/{id}/endpoints",
        "summary": summary,
        "models": models,
    }


def fetch_spread(
    observations: List[dict],
    target_date: date,
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    min_endpoints: int = DEFAULT_MIN_ENDPOINTS,
    get: Optional[Callable] = None,
    pause_seconds: float = 0.25,
) -> dict:
    """
    Fetch provider endpoints for every open-weight observation and summarize.

    ``get`` is injectable for tests; it defaults to ``requests.get``.
    """
    if get is None:
        import requests

        get = requests.get

    candidates = sorted({o["model_id"] for o in observations if o.get("open_weights")})
    summaries, errors = [], []
    for index, model_id in enumerate(candidates):
        if index and pause_seconds:
            time.sleep(pause_seconds)
        url = ENDPOINTS_URL.format(model_id=quote(model_id, safe="/"))
        try:
            response = get(url, timeout=20)
            response.raise_for_status()
            endpoints = (response.json().get("data") or {}).get("endpoints") or []
        except Exception as error:  # one failed model must not sink the day
            errors.append(f"{model_id}: {type(error).__name__}")
            continue
        summary = summarize_endpoints(model_id, endpoints, output_ratio, min_endpoints)
        if summary:
            summaries.append(summary)

    return compute_spread(target_date, summaries, output_ratio, errors)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute the STCI neocloud spread")
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--min-endpoints", type=int, default=DEFAULT_MIN_ENDPOINTS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target_date = args.date or date.today()
    obs_path = args.data_dir / "observations" / f"{target_date.isoformat()}.jsonl"
    if not obs_path.exists():
        print(f"No observations for {target_date}: {obs_path}", file=sys.stderr)
        return 1
    observations = [json.loads(line) for line in obs_path.read_text().splitlines() if line.strip()]

    import yaml

    methodology = yaml.safe_load((args.data_dir / "fixtures" / "methodology.yaml").read_text())
    output_ratio = float(methodology.get("output_ratio", DEFAULT_OUTPUT_RATIO))

    result = fetch_spread(observations, target_date, output_ratio, args.min_endpoints)
    s = result["summary"]
    print(f"Spread {target_date}: {s['models_measured']} models, {s['fetch_errors']} fetch errors")
    if "widest" in s:
        print(f"  median max/min {s['median_max_min_ratio']}x; widest {s['widest']}")

    if not args.dry_run:
        out = args.data_dir / "spread" / f"{target_date.isoformat()}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
