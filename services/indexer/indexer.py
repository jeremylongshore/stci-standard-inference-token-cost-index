"""
STCI Indexer - Computes daily reference rates from observations.
"""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

import yaml


class Indexer:
    """
    Main indexer class for computing STCI values.

    Implements the STCI methodology:
    1. Filter observations to basket
    2. Apply weighting
    3. Compute aggregates
    4. Generate verification hash
    """

    def __init__(self, methodology_path: Optional[Path] = None):
        """
        Initialize indexer with methodology configuration.

        Args:
            methodology_path: Path to methodology YAML file
        """
        if methodology_path is None:
            methodology_path = (
                Path(__file__).parent.parent.parent
                / "data"
                / "fixtures"
                / "methodology.yaml"
            )

        with open(methodology_path) as f:
            self.methodology = yaml.safe_load(f)

    def compute(
        self,
        observations: List[dict],
        target_date: Optional[date] = None,
        spread: Optional[dict] = None,
    ) -> dict:
        """
        Compute STCI indices from observations.

        Args:
            observations: List of observation dictionaries
            target_date: Date for index (default: from observations)
            spread: That day's neocloud spread document, needed by baskets
                whose filter sets min_endpoints (2.0.0 STCI-OPEN)

        Returns:
            STCI daily output dictionary
        """
        target_date = target_date or self._infer_date(observations)
        observations = [obs for obs in observations if self._eligible(obs)]
        self._endpoint_counts = {
            m["model_id"]: m["endpoints"] for m in (spread or {}).get("models", [])
        }
        self._spread_used = False

        # Compute each index
        indices = {}
        for index_name, index_config in self.methodology.get("indices", {}).items():
            index_value = self._compute_single_index(
                observations,
                index_name,
                index_config,
            )
            if index_value:
                indices[index_name] = index_value

        # Generate verification hash
        verification_hash = self._compute_hash(
            observations,
            target_date,
            self._endpoint_counts if self._spread_used else None,
        )

        result = {
            "date": target_date.isoformat(),
            "indices": indices,
            "methodology_version": self.methodology.get("methodology_version", "1.0.0"),
            "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "verification_hash": verification_hash,
            "observation_count": len(observations),
        }

        return result

    def _compute_single_index(
        self,
        observations: List[dict],
        index_name: str,
        config: dict,
    ) -> Optional[dict]:
        """
        Compute a single index value.

        Args:
            observations: All observations
            index_name: Name of the index
            config: Index configuration

        Returns:
            Index value dictionary or None if insufficient data
        """
        # Filter to basket
        basket_models = config.get("models", [])
        rule = config.get("filter") or {}
        if basket_models:
            # Explicit basket - filter to listed models
            filtered = [
                obs for obs in observations
                if obs.get("model_id") in basket_models
                or f"{obs.get('provider')}/{obs.get('model_id')}" in basket_models
            ]
        elif "open_weights" in rule or "min_endpoints" in rule:
            # Rule basket (2.0.0): published weights, optionally screened for
            # liquidity by the number of priced provider endpoints that day
            min_endpoints = rule.get("min_endpoints")
            if min_endpoints is not None:
                if not self._endpoint_counts:
                    return None  # no spread file, so the screen cannot run
                self._spread_used = True
            filtered = [
                obs for obs in observations
                if (not rule.get("open_weights") or obs.get("open_weights"))
                and (
                    min_endpoints is None
                    or self._endpoint_counts.get(obs.get("model_id"), 0) >= min_endpoints
                )
            ]
        else:
            # No explicit basket - use all observations
            filtered = observations

        if not filtered:
            return None

        # Check minimum coverage
        min_coverage = self.methodology.get("min_basket_coverage", 0.5)
        if basket_models and len(filtered) / len(basket_models) < min_coverage:
            return None

        # Extract rates
        input_rates = [obs["input_rate_usd_per_1m"] for obs in filtered]
        output_rates = [obs["output_rate_usd_per_1m"] for obs in filtered]

        # Compute aggregates (equal weighting for MVP)
        avg_input = mean(input_rates)
        avg_output = mean(output_rates)

        # Blended rate: assumes output_ratio:1 output:input ratio
        output_ratio = self.methodology.get("output_ratio", 3.0)
        blended = (avg_input + output_ratio * avg_output) / (1 + output_ratio)

        # Dispersion (standard deviation)
        dispersion = None
        if len(input_rates) > 1:
            dispersion = stdev(input_rates)

        # Round to configured precision
        output_decimals = self.methodology.get("decimal_places", {}).get("output", 2)

        result = {
            "input_rate": round(avg_input, output_decimals),
            "output_rate": round(avg_output, output_decimals),
            "blended_rate": round(blended, output_decimals),
            "model_count": len(filtered),
            "models_included": [
                obs.get("model_id") or f"{obs.get('provider')}/unknown"
                for obs in filtered
            ],
        }

        if dispersion is not None:
            result["dispersion"] = round(dispersion, output_decimals)

        if basket_models:
            present = {obs.get("model_id") for obs in filtered}
            result["constituents_missing"] = sorted(m for m in basket_models if m not in present)

        return result

    def _eligible(self, obs: dict) -> bool:
        """Re-apply the methodology's eligibility rules to one observation."""
        rules = self.methodology.get("eligibility") or {}
        model_id = obs.get("model_id") or ""
        alias_prefix = rules.get("exclude_alias_prefix")
        if alias_prefix and model_id.startswith(alias_prefix):
            return False
        separator = rules.get("exclude_variant_separator")
        if separator and separator in model_id:
            return False
        if rules.get("exclude_negative_prices") and (
            obs.get("input_rate_usd_per_1m", 0) < 0 or obs.get("output_rate_usd_per_1m", 0) < 0
        ):
            return False
        return True

    def _compute_hash(
        self,
        observations: List[dict],
        target_date: date,
        endpoint_counts: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Compute verification hash for determinism check.

        Hash = SHA256(sorted observations JSON + methodology version + date),
        plus the per-model endpoint counts when a liquidity screen used them.
        """
        # Sort observations deterministically
        sorted_obs = sorted(observations, key=lambda x: x.get("observation_id", ""))

        # Create hash input
        hash_input = {
            "date": target_date.isoformat(),
            "methodology_version": self.methodology.get("methodology_version"),
            "observations": sorted_obs,
        }
        if endpoint_counts is not None:
            hash_input["endpoint_counts"] = dict(sorted(endpoint_counts.items()))

        hash_str = json.dumps(hash_input, sort_keys=True, default=str)
        return hashlib.sha256(hash_str.encode()).hexdigest()[:16]

    def _infer_date(self, observations: List[dict]) -> date:
        """Infer date from observations."""
        for obs in observations:
            if effective_date := obs.get("effective_date"):
                if isinstance(effective_date, str):
                    return date.fromisoformat(effective_date)
                return effective_date
        return date.today()


def compute_index(
    observations: List[dict],
    methodology_path: Optional[Path] = None,
    target_date: Optional[date] = None,
    spread: Optional[dict] = None,
) -> dict:
    """
    Convenience function to compute STCI index.

    Args:
        observations: List of observation dictionaries
        methodology_path: Path to methodology file
        target_date: Date for index

    Returns:
        STCI daily output dictionary
    """
    indexer = Indexer(methodology_path)
    return indexer.compute(observations, target_date, spread)


def main():
    """CLI entry point for indexer."""
    import argparse

    parser = argparse.ArgumentParser(description="STCI Indexer")
    parser.add_argument(
        "--observations",
        type=str,
        required=True,
        help="Path to observations JSON file",
    )
    parser.add_argument(
        "--methodology",
        type=str,
        help="Path to methodology YAML file",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date for index (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path",
    )

    args = parser.parse_args()

    # Load observations
    with open(args.observations) as f:
        observations = json.load(f)

    # Compute index
    methodology_path = Path(args.methodology) if args.methodology else None
    target_date = date.fromisoformat(args.date) if args.date else None

    result = compute_index(observations, methodology_path, target_date)

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Wrote index to {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
