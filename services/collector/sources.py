"""
STCI Data Sources - Implementations for fetching pricing data.
"""

import json
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Requests import is optional - graceful fallback if not installed
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class BaseSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    def fetch(self, target_date: date) -> List[dict]:
        """
        Fetch observations for a given date.

        Args:
            target_date: Date to fetch data for

        Returns:
            List of observation dictionaries
        """
        pass

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Return source identifier."""
        pass

    @property
    @abstractmethod
    def source_tier(self) -> str:
        """Return source tier (T1-T4)."""
        pass


class OpenRouterSource(BaseSource):
    """
    OpenRouter API source.

    Fetches model pricing from OpenRouter's public models endpoint.
    See: https://openrouter.ai/docs/api/api-reference/models/get-models
    """

    API_URL = "https://openrouter.ai/api/v1/models"

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or self.API_URL
        self.last_exclusions: Dict[str, List[str]] = {}

    @property
    def source_id(self) -> str:
        return "openrouter"

    @property
    def source_tier(self) -> str:
        return "T1"

    def fetch(self, target_date: date) -> List[dict]:
        """
        Fetch pricing data from OpenRouter API.

        Args:
            target_date: Date for the observation

        Returns:
            List of normalized observation dictionaries
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required for OpenRouter source")

        response = requests.get(self.api_url, timeout=30)
        response.raise_for_status()

        collected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return self.normalize(response.json().get("data", []), target_date, collected_at)

    def normalize(self, models: List[dict], target_date: date, collected_at: str) -> List[dict]:
        """
        Turn OpenRouter catalog entries into observations (methodology 2.0.0).

        Listings that are not a separately priced model are excluded, each with
        a reason recorded in ``self.last_exclusions``:

        - ``alias``: ``~provider/...-latest`` IDs, which point at another listing
        - ``router``: negative sentinel prices (routers priced at -1/token)
        - ``free``: ``:free`` variants and listings priced at zero
        - ``batch``: ``:batch`` variants; their rates are attached to the base
          model as ``batch_rate_input``/``batch_rate_output`` instead
        - ``unpriced``: missing or non-numeric prompt/completion prices

        Without these rules 92 half-price batch duplicates and 14 free
        listings (2026-11-19) would drag the equal-weighted indices down.
        """
        observations: Dict[str, dict] = {}
        batch_rates: Dict[str, Tuple[float, float]] = {}
        excluded: Dict[str, List[str]] = {}

        def exclude(reason: str, model_id: str) -> None:
            excluded.setdefault(reason, []).append(model_id)

        for model in models:
            model_id = model.get("id", "")
            pricing = model.get("pricing") or {}

            try:
                input_rate = float(pricing["prompt"]) * 1_000_000
                output_rate = float(pricing["completion"]) * 1_000_000
            except (KeyError, ValueError, TypeError):
                exclude("unpriced", model_id)
                continue

            if model_id.startswith("~"):
                exclude("alias", model_id)
                continue
            if input_rate < 0 or output_rate < 0:
                exclude("router", model_id)
                continue
            base_id, _, variant = model_id.partition(":")
            if variant == "free" or (input_rate == 0 and output_rate == 0):
                exclude("free", model_id)
                continue
            if variant == "batch":
                batch_rates[base_id] = (input_rate, output_rate)
                exclude("batch", model_id)
                continue

            provider = model_id.split("/")[0] if "/" in model_id else "unknown"

            obs = {
                "observation_id": f"obs-{target_date.isoformat()}-{model_id.replace('/', '-')}",
                "schema_version": "1.0.0",
                "provider": provider,
                "model_id": model_id,
                "model_display_name": model.get("name", model_id),
                "input_rate_usd_per_1m": round(input_rate, 6),
                "output_rate_usd_per_1m": round(output_rate, 6),
                "effective_date": target_date.isoformat(),
                "collected_at": collected_at,
                "source_url": self.api_url,
                "source_tier": self.source_tier,
                "currency": "USD",
                "collection_method": "aggregator_api",
                "confidence_level": "high",
            }

            # Add optional fields if available
            if context_length := model.get("context_length"):
                obs["context_window"] = context_length
            cache_read = _per_million(pricing.get("input_cache_read"))
            if cache_read is not None and cache_read > 0:
                obs["cached_rate_input"] = round(cache_read, 6)
            if model.get("hugging_face_id"):
                obs["open_weights"] = True
                obs["hugging_face_id"] = model["hugging_face_id"]

            observations[model_id] = obs

        for base_id, (batch_in, batch_out) in batch_rates.items():
            if base_id in observations:
                observations[base_id]["batch_rate_input"] = round(batch_in, 6)
                observations[base_id]["batch_rate_output"] = round(batch_out, 6)

        self.last_exclusions = {reason: sorted(ids) for reason, ids in sorted(excluded.items())}
        return list(observations.values())


def _per_million(value) -> Optional[float]:
    """Convert an OpenRouter $/token string to $/1M tokens, or None."""
    try:
        return float(value) * 1_000_000
    except (TypeError, ValueError):
        return None


class FixtureSource(BaseSource):
    """
    Fixture data source for testing and fallback.

    Loads observations from local JSON fixtures.
    """

    def __init__(self, fixture_path: Optional[Path] = None):
        if fixture_path is None:
            # Default to project fixtures directory
            self.fixture_path = (
                Path(__file__).parent.parent.parent
                / "data"
                / "fixtures"
                / "observations.sample.json"
            )
        else:
            self.fixture_path = Path(fixture_path)

    @property
    def source_id(self) -> str:
        return "fixture"

    @property
    def source_tier(self) -> str:
        return "T4"  # Lowest tier - fixture data

    def fetch(self, target_date: date) -> List[dict]:
        """
        Load observations from fixture file.

        Args:
            target_date: Date for the observations (updates effective_date)

        Returns:
            List of observation dictionaries with updated dates
        """
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {self.fixture_path}")

        with open(self.fixture_path) as f:
            observations = json.load(f)

        # Update dates in fixtures
        collected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for obs in observations:
            obs["effective_date"] = target_date.isoformat()
            obs["collected_at"] = collected_at
            # Update observation_id to reflect date
            model_id = obs.get("model_id", "unknown").replace("/", "-")
            obs["observation_id"] = f"obs-{target_date.isoformat()}-{obs['provider']}-{model_id}"

        return observations
