"""
Methodology 2.0.0: listing eligibility, the neocloud spread, rule baskets,
constituent staleness and the spread-aware verification hash.
"""

import json
from datetime import date

import pytest
import yaml

from services.collector import spread
from services.collector.sources import OpenRouterSource
from services.indexer.indexer import Indexer

DAY = date(2026, 11, 19)


def listing(model_id, prompt, completion, **extra):
    entry = {
        "id": model_id,
        "name": model_id,
        "pricing": {"prompt": str(prompt), "completion": str(completion)},
        "context_length": 1_000_000,
    }
    entry.update(extra)
    return entry


CATALOG = [
    listing("lab/big", "0.000008", "0.00004", pricing_extra=None),
    listing("lab/big:batch", "0.000004", "0.00002"),
    listing("lab/big:free", "0", "0"),
    listing("~lab/big-latest", "0.000008", "0.00004"),
    listing("router/auto", "-1", "-1"),
    listing("open/model", "0.0000001", "0.0000006", hugging_face_id="open/model"),
    listing("lab/zero", "0", "0"),
    listing("lab/unpriced", "n/a", "0.00001"),
    listing("orphan/only:batch", "0.000001", "0.000002"),
]
CATALOG[0]["pricing"]["input_cache_read"] = "0.0000008"
del CATALOG[0]["pricing_extra"]


class TestNormalize:
    def test_excludes_each_class_with_a_reason(self):
        source = OpenRouterSource()
        observations = source.normalize(CATALOG, DAY, "2026-11-19T00:00:00Z")

        assert sorted(o["model_id"] for o in observations) == ["lab/big", "open/model"]
        assert source.last_exclusions == {
            "alias": ["~lab/big-latest"],
            "batch": ["lab/big:batch", "orphan/only:batch"],
            "free": ["lab/big:free", "lab/zero"],
            "router": ["router/auto"],
            "unpriced": ["lab/unpriced"],
        }

    def test_batch_cache_and_open_weight_fields(self):
        observations = OpenRouterSource().normalize(CATALOG, DAY, "2026-11-19T00:00:00Z")
        by_id = {o["model_id"]: o for o in observations}

        big = by_id["lab/big"]
        assert big["input_rate_usd_per_1m"] == 8.0
        assert big["output_rate_usd_per_1m"] == 40.0
        assert big["batch_rate_input"] == 4.0
        assert big["batch_rate_output"] == 20.0
        assert big["cached_rate_input"] == 0.8
        assert "open_weights" not in big

        open_model = by_id["open/model"]
        assert open_model["open_weights"] is True
        assert open_model["hugging_face_id"] == "open/model"
        assert "batch_rate_input" not in open_model

    def test_observations_validate_against_schema(self, project_root=None):
        import jsonschema
        from pathlib import Path

        schema = json.loads((Path(__file__).parent.parent / "schemas" / "observation.schema.json").read_text())
        for obs in OpenRouterSource().normalize(CATALOG, DAY, "2026-11-19T00:00:00Z"):
            jsonschema.validate(obs, schema)


def endpoint(provider, prompt, completion, quantization="fp8"):
    return {
        "provider_name": provider,
        "quantization": quantization,
        "pricing": {"prompt": str(prompt), "completion": str(completion)},
    }


ENDPOINTS = [
    endpoint("Dear", "0.000002", "0.000002"),            # blended 2.00
    endpoint("Cheap", "0.0000001", "0.0000001", "fp4"),  # blended 0.10
    endpoint("Mid", "0.0000005", "0.0000005"),           # blended 0.50
    endpoint("Mid2", "0.000001", "0.000001", "bf16"),    # blended 1.00
    endpoint("Free", "0", "0"),                          # ignored
    endpoint("Router", "-1", "-1"),                      # ignored
    {"provider_name": "Broken", "pricing": {}},          # ignored
]


class TestSpread:
    def test_percentile_is_linear_and_deterministic(self):
        values = [0.1, 0.5, 1.0, 2.0]
        assert spread.percentile(values, 0.0) == 0.1
        assert spread.percentile(values, 1.0) == 2.0
        assert spread.percentile(values, 0.5) == pytest.approx(0.75)
        with pytest.raises(ValueError):
            spread.percentile([], 0.5)

    def test_summarize_endpoints_ignores_unpriced_and_ranks_cheapest(self):
        summary = spread.summarize_endpoints("open/model", ENDPOINTS)

        assert summary["endpoints"] == 4
        assert summary["providers"] == 4
        assert summary["min_blended"] == 0.1
        assert summary["max_blended"] == 2.0
        assert summary["median_blended"] == 0.75
        assert summary["max_min_ratio"] == 20.0
        assert summary["quantization_mix"] == {"bf16": 1, "fp4": 1, "fp8": 2}
        assert summary["cheapest"] == {"provider": "Cheap", "quantization": "fp4", "blended": 0.1}

    def test_summarize_endpoints_needs_enough_priced_endpoints(self):
        assert spread.summarize_endpoints("open/model", ENDPOINTS[:2]) is None
        assert spread.summarize_endpoints("open/model", ENDPOINTS[:2], min_endpoints=2) is not None

    def test_compute_spread_summary_names_widest_and_most_sold(self):
        wide = spread.summarize_endpoints("open/wide", ENDPOINTS)
        narrow = spread.summarize_endpoints(
            "open/narrow",
            [endpoint(f"P{i}", "0.000001", "0.000001") for i in range(6)],
        )
        doc = spread.compute_spread(DAY, [narrow, wide], errors=["open/lost: Timeout"])

        assert doc["methodology_version"] == "2.1.0"
        assert doc["models"][0]["model_id"] == "open/narrow"  # most endpoints first
        assert doc["summary"]["models_measured"] == 2
        assert doc["summary"]["fetch_errors"] == 1
        assert doc["summary"]["widest"]["model_id"] == "open/wide"
        assert doc["summary"]["most_endpoints"]["model_id"] == "open/narrow"
        assert doc["summary"]["median_max_min_ratio"] == pytest.approx(10.5)

    def test_fetch_spread_only_queries_open_weight_models_and_survives_errors(self):
        calls = []

        class Response:
            def __init__(self, endpoints):
                self.endpoints = endpoints

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": {"endpoints": self.endpoints}}

        def fake_get(url, timeout):
            calls.append(url)
            if url.endswith("open/lost/endpoints"):
                raise TimeoutError("slow")
            return Response(ENDPOINTS)

        observations = [
            {"model_id": "open/model", "open_weights": True},
            {"model_id": "open/lost", "open_weights": True},
            {"model_id": "lab/closed"},
        ]
        doc = spread.fetch_spread(observations, DAY, get=fake_get, pause_seconds=0)

        assert len(calls) == 2
        assert all("lab/closed" not in url for url in calls)
        assert [m["model_id"] for m in doc["models"]] == ["open/model"]
        assert doc["summary"]["fetch_errors"] == 1


METHODOLOGY = {
    "methodology_version": "2.0.0",
    "output_ratio": 3.0,
    "min_basket_coverage": 0.5,
    "decimal_places": {"rates": 6, "weights": 8, "output": 2},
    "eligibility": {
        "exclude_alias_prefix": "~",
        "exclude_variant_separator": ":",
        "exclude_negative_prices": True,
    },
    "indices": {
        "STCI-ALL": {"weighting": "equal", "filter": None},
        "STCI-FRONTIER": {"weighting": "equal", "models": ["lab/big", "lab/gone"]},
        "STCI-OPEN": {"weighting": "equal", "filter": {"open_weights": True, "min_endpoints": 10}},
    },
}


def observation(model_id, input_rate, output_rate, **extra):
    obs = {
        "observation_id": f"obs-2026-11-19-{model_id.replace('/', '-')}",
        "model_id": model_id,
        "provider": model_id.split("/")[0],
        "input_rate_usd_per_1m": input_rate,
        "output_rate_usd_per_1m": output_rate,
        "effective_date": "2026-11-19",
    }
    obs.update(extra)
    return obs


OBSERVATIONS = [
    observation("lab/big", 8.0, 40.0),
    observation("open/liquid", 0.2, 0.8, open_weights=True),
    observation("open/thin", 0.2, 0.8, open_weights=True),
    observation("lab/big:batch", 4.0, 20.0),      # old file: variant leaks in
    observation("~lab/big-latest", 8.0, 40.0),    # old file: alias leaks in
    observation("router/auto", -1e6, -1e6),       # old file: router leaks in
]
SPREAD = {"models": [{"model_id": "open/liquid", "endpoints": 12}, {"model_id": "open/thin", "endpoints": 3}]}


@pytest.fixture
def indexer(tmp_path):
    path = tmp_path / "methodology.yaml"
    path.write_text(yaml.safe_dump(METHODOLOGY))
    return Indexer(path)


class TestIndexerV2:
    def test_eligibility_drops_variants_aliases_and_routers(self, indexer):
        result = indexer.compute(OBSERVATIONS, DAY, SPREAD)
        assert result["observation_count"] == 3
        assert sorted(result["indices"]["STCI-ALL"]["models_included"]) == [
            "lab/big", "open/liquid", "open/thin",
        ]

    def test_constituents_missing_is_reported(self, indexer):
        result = indexer.compute(OBSERVATIONS, DAY, SPREAD)
        frontier = result["indices"]["STCI-FRONTIER"]
        assert frontier["model_count"] == 1
        assert frontier["constituents_missing"] == ["lab/gone"]
        assert "constituents_missing" not in result["indices"]["STCI-ALL"]

    def test_open_basket_needs_the_spread_and_screens_for_liquidity(self, indexer):
        without = indexer.compute(OBSERVATIONS, DAY)
        assert "STCI-OPEN" not in without["indices"]

        with_spread = indexer.compute(OBSERVATIONS, DAY, SPREAD)
        assert with_spread["indices"]["STCI-OPEN"]["models_included"] == ["open/liquid"]
        assert with_spread["indices"]["STCI-OPEN"]["blended_rate"] == pytest.approx(0.65)

    def test_hash_is_stable_and_binds_the_liquidity_screen(self, indexer):
        first = indexer.compute(OBSERVATIONS, DAY, SPREAD)["verification_hash"]
        again = indexer.compute(list(reversed(OBSERVATIONS)), DAY, SPREAD)["verification_hash"]
        assert first == again

        thinner = {"models": [{"model_id": "open/liquid", "endpoints": 11}]}
        assert indexer.compute(OBSERVATIONS, DAY, thinner)["verification_hash"] != first
        assert indexer.compute(OBSERVATIONS, DAY)["verification_hash"] != first
