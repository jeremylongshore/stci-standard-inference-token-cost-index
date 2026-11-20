"""
STCI Neocloud Spread - what the same open-weight model costs across providers.

An open-weight model is sold by many inference providers at once. OpenRouter
lists each provider endpoint with its own price and serving precision
(fp4, fp8, bf16, ...). The spread between the cheapest and the dearest
endpoint for one model is a direct read on how commoditized that model is,
and the precision of the cheapest endpoint shows that a cheaper token is not
always the same token.

Methodology 2.1.0: facets, not verdicts. Each model's endpoints are cut into
cells by reported precision, context bucket and tool support; no grade is ever
written at collection time. Outputs:

    data/spread/{date}.json       public spread with facet cells
    data/endpoints/{date}.jsonl   PRIVATE canonical endpoint snapshot (git-ignored);
                                  its sha256 is recorded in the spread file

Usage:
    python -m services.collector.spread                    # today, from observations
    python -m services.collector.spread --date 2026-11-19
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import quote

from services.indexer.rules import (
    active_rule,
    read_methodology_version,
    resolve_methodology_path,
    uses_facets,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model_id}/endpoints"
METHODOLOGY_VERSION = "2.1.0"  # default for callers that do not resolve a rulebook
# Keys that exist only from methodology 2.1.0.
FACET_MODEL_KEYS = ("snapshot", "precision_disclosure", "cells", "observed")
DEFAULT_OUTPUT_RATIO = 3.0
DEFAULT_MIN_ENDPOINTS = 4
DECIMALS = 4
MIN_CELL_N = 3
UNDISCLOSED = "undisclosed"
CONTEXT_BUCKETS = ["<=32k", "32-128k", "128k+", "1M+", "unknown"]
# A dated snapshot id ends in -MMDD, -YYMM, -YYYYMMDD or -YYYY-MM-DD.
DATED_SNAPSHOT = re.compile(r"-(\d{4}|\d{8}|\d{4}-\d{2}-\d{2})$")


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


def precision_of(quantization) -> str:
    """Precision as reported. Missing/unknown is its own bucket, never folded."""
    value = str(quantization).strip().lower() if quantization is not None else ""
    return UNDISCLOSED if value in ("", "unknown", "none", "null", "undisclosed") else value


def context_bucket(context_length) -> str:
    try:
        n = int(context_length)
    except (TypeError, ValueError):
        return "unknown"
    if n >= 1_000_000:
        return "1M+"
    if n > 131_072:
        return "128k+"
    if n > 32_768:
        return "32-128k"
    return "<=32k"


def snapshot_kind(model_id: str) -> str:
    """'dated' for ids carrying a snapshot suffix, else 'undated'. Never pooled."""
    return "dated" if DATED_SNAPSHOT.search(model_id) else "undated"


def _number(value) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("p50")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stats(rates: List[float]) -> dict:
    """Cell statistics; null when n < MIN_CELL_N (n is still reported)."""
    n = len(rates)
    if n < MIN_CELL_N:
        return {"n": n, "min": None, "p25": None, "median": None, "p75": None,
                "max": None, "p75_p25_ratio": None}
    rates = sorted(rates)
    p25, p75 = percentile(rates, 0.25), percentile(rates, 0.75)
    return {
        "n": n,
        "min": round(rates[0], DECIMALS),
        "p25": round(p25, DECIMALS),
        "median": round(percentile(rates, 0.5), DECIMALS),
        "p75": round(p75, DECIMALS),
        "max": round(rates[-1], DECIMALS),
        "p75_p25_ratio": round(p75 / p25, 2) if p25 > 0 else None,
    }


def build_cells(priced: List[dict]) -> List[dict]:
    """Facet cells: precision x context bucket x tools. Facets, not grades."""
    groups: Dict[tuple, List[float]] = {}
    for e in priced:
        key = (e["precision"], e["context_bucket"], e["tools"])
        groups.setdefault(key, []).append(e["blended"])
    cells = []
    for (precision, bucket, tools), rates in groups.items():
        cells.append({"precision": precision, "context_bucket": bucket, "tools": tools,
                      **_stats(rates)})
    cells.sort(key=lambda c: (c["precision"], CONTEXT_BUCKETS.index(c["context_bucket"]),
                              c["tools"]))
    return cells


def _snapshot_row(model_id: str, endpoint: dict, precision: str) -> dict:
    pricing = endpoint.get("pricing") or {}
    return {
        "model_id": model_id,
        "provider": endpoint.get("provider_name") or "unknown",
        "tag": endpoint.get("tag"),
        "quantization": precision,
        "context_length": endpoint.get("context_length"),
        "max_completion_tokens": endpoint.get("max_completion_tokens"),
        "supported_parameters": sorted(endpoint.get("supported_parameters") or []),
        "price_in": pricing.get("prompt"),
        "price_out": pricing.get("completion"),
        "cache_read": pricing.get("input_cache_read"),
    }


def collect_model(
    model_id: str,
    endpoints: List[dict],
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    min_endpoints: int = DEFAULT_MIN_ENDPOINTS,
    rule: Optional[dict] = None,
) -> Optional[tuple]:
    """
    Summarize one model's provider endpoints: (summary, private snapshot rows),
    or None if too few are priced.

    Endpoints with a missing, non-numeric, negative or all-zero price are
    ignored: they are free tiers or routers, not a price anyone pays. An
    endpoint that names a different model id is ignored too, so dated
    snapshots are never pooled with undated ids.
    """
    priced, rows = [], []
    for endpoint in endpoints:
        named = endpoint.get("model_id")
        if named and named != model_id:
            continue
        pricing = endpoint.get("pricing") or {}
        try:
            input_rate = float(pricing["prompt"]) * 1_000_000
            output_rate = float(pricing["completion"]) * 1_000_000
        except (KeyError, TypeError, ValueError):
            continue
        if input_rate < 0 or output_rate < 0 or (input_rate == 0 and output_rate == 0):
            continue
        precision = precision_of(endpoint.get("quantization"))
        params = endpoint.get("supported_parameters") or []
        priced.append(
            {
                "provider": endpoint.get("provider_name") or "unknown",
                "quantization": precision,
                "precision": precision,
                "context_bucket": context_bucket(endpoint.get("context_length")),
                "tools": "tools" in params,
                "blended": blended(input_rate, output_rate, output_ratio),
                "observed": {
                    "uptime": _number(endpoint.get("uptime_last_30m")),
                    "latency": _number(endpoint.get("latency_last_30m")),
                    "throughput": _number(endpoint.get("throughput_last_30m")),
                },
            }
        )
        rows.append(_snapshot_row(model_id, endpoint, precision))

    if len(priced) < min_endpoints:
        return None

    priced.sort(key=lambda e: (e["blended"], e["provider"], e["quantization"]))
    rates = [e["blended"] for e in priced]
    low, high = rates[0], rates[-1]
    p25, p75 = percentile(rates, 0.25), percentile(rates, 0.75)

    mix: Dict[str, int] = {}
    for e in priced:
        mix[e["quantization"]] = mix.get(e["quantization"], 0) + 1

    undisclosed_values = set((rule or {}).get("undisclosed_values") or [UNDISCLOSED])
    undisclosed = sum(n for k, n in mix.items() if k in undisclosed_values)

    observed = {}
    for key in ("uptime", "latency", "throughput"):
        values = sorted(e["observed"][key] for e in priced if e["observed"][key] is not None)
        if values:
            observed[f"median_{key}"] = round(percentile(values, 0.5), 4)

    cheapest = priced[0]
    summary = {
        "model_id": model_id,
        "snapshot": snapshot_kind(model_id),
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
        "precision_disclosure": {
            "disclosed": len(priced) - undisclosed,
            "undisclosed": undisclosed,
        },
        "cells": build_cells(priced),
        "cheapest": {
            "provider": cheapest["provider"],
            "quantization": cheapest["quantization"],
            "blended": round(cheapest["blended"], DECIMALS),
        },
        # Not part of any hash: it moves minute to minute.
        "observed": observed,
    }
    return summary, rows


def summarize_endpoints(
    model_id: str,
    endpoints: List[dict],
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    min_endpoints: int = DEFAULT_MIN_ENDPOINTS,
    rule: Optional[dict] = None,
) -> Optional[dict]:
    """Summary half of :func:`collect_model`."""
    collected = collect_model(model_id, endpoints, output_ratio, min_endpoints, rule)
    return collected[0] if collected else None


def canonical_snapshot(rows: List[dict]) -> bytes:
    """Sorted, canonical-JSON JSONL bytes of the private endpoint snapshot."""
    lines = sorted(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows)
    return ("\n".join(lines) + "\n").encode() if lines else b""


def snapshot_sha256(rows: List[dict]) -> str:
    return hashlib.sha256(canonical_snapshot(rows)).hexdigest()


def compute_spread(
    target_date: date,
    summaries: List[dict],
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    errors: Optional[List[str]] = None,
    snapshot_rows: Optional[List[dict]] = None,
    rule: Optional[dict] = None,
    methodology_version: str = METHODOLOGY_VERSION,
) -> dict:
    """Assemble the daily spread document from per-model summaries."""
    facets = uses_facets(methodology_version)
    if facets:
        rule = rule if rule is not None else active_rule(target_date)
    else:
        rule, snapshot_rows = None, []
        summaries = [{k: v for k, v in m.items() if k not in FACET_MODEL_KEYS} for m in summaries]
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

    doc = {
        "date": target_date.isoformat(),
        "methodology_version": methodology_version,
        "blend": {"output_ratio": output_ratio},
        "source": "OpenRouter /api/v1/models/{id}/endpoints",
        "summary": summary,
        "models": models,
    }
    if facets:
        keyed = list(doc.items())
        keyed.insert(3, ("rule_id", rule["rule_id"] if rule else None))
        keyed.insert(4, ("endpoint_snapshot_sha256", snapshot_sha256(snapshot_rows or [])))
        doc = dict(keyed)
    return doc


def split_observed(doc: dict) -> tuple:
    """(committed document without ``observed`` blocks, {model_id: observed})."""
    observed = {m["model_id"]: m["observed"] for m in doc["models"] if m.get("observed")}
    public = dict(doc, models=[{k: v for k, v in m.items() if k != "observed"} for m in doc["models"]])
    return public, observed


def fetch_spread(*args, **kwargs) -> dict:
    """Spread document only; see :func:`fetch_spread_with_snapshot`."""
    return fetch_spread_with_snapshot(*args, **kwargs)[0]


def fetch_spread_with_snapshot(
    observations: List[dict],
    target_date: date,
    output_ratio: float = DEFAULT_OUTPUT_RATIO,
    min_endpoints: int = DEFAULT_MIN_ENDPOINTS,
    get: Optional[Callable] = None,
    pause_seconds: float = 0.25,
    methodology_version: str = METHODOLOGY_VERSION,
) -> tuple:
    """
    Fetch provider endpoints for every open-weight observation and summarize.

    Returns (spread document, private snapshot rows). ``get`` is injectable for tests; it defaults to ``requests.get``.
    """
    if get is None:
        import requests

        get = requests.get

    candidates = sorted({o["model_id"] for o in observations if o.get("open_weights")})
    rule = active_rule(target_date) if uses_facets(methodology_version) else None
    summaries, errors, snapshot_rows = [], [], []
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
        collected = collect_model(model_id, endpoints, output_ratio, min_endpoints, rule)
        if collected:
            summaries.append(collected[0])
            snapshot_rows.extend(collected[1])

    doc = compute_spread(
        target_date, summaries, output_ratio, errors, snapshot_rows, rule, methodology_version
    )
    return doc, snapshot_rows


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

    methodology_path = resolve_methodology_path(target_date, args.data_dir)
    methodology = yaml.safe_load(methodology_path.read_text())
    version = read_methodology_version(methodology_path)
    output_ratio = float(methodology.get("output_ratio", DEFAULT_OUTPUT_RATIO))

    result, snapshot_rows = fetch_spread_with_snapshot(
        observations, target_date, output_ratio, args.min_endpoints, methodology_version=version
    )
    s = result["summary"]
    print(f"Spread {target_date}: {s['models_measured']} models, {s['fetch_errors']} fetch errors")
    if "widest" in s:
        print(f"  median max/min {s['median_max_min_ratio']}x; widest {s['widest']}")

    if not args.dry_run:
        public, observed = split_observed(result)
        out = args.data_dir / "spread" / f"{target_date.isoformat()}.json"
        if out.exists() and json.loads(out.read_text()).get("methodology_version") != version:
            print(f"Refusing to overwrite {out}: published under another methodology", file=sys.stderr)
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(public, indent=2) + "\n")
        print(f"  written: {out}")
        if uses_facets(version):
            snap = args.data_dir / "endpoints" / f"{target_date.isoformat()}.jsonl"
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_bytes(canonical_snapshot(snapshot_rows))
            side = snap.with_suffix(".observed.json")
            side.write_text(json.dumps(observed, indent=2, sort_keys=True) + "\n")
            print(f"  private snapshot: {snap} sha256 {result['endpoint_snapshot_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
