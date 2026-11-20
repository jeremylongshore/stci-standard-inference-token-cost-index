"""
Methodology 2.1.0: facets, not verdicts. Cells, the private endpoint snapshot,
append-only rules, and the facet-aware verification hash, with planted-fault
tests for each way the facets could silently collapse into a verdict.
"""

import copy
import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

from scripts import publish_static as ps
from services.collector import spread
from services.indexer import rules
from services.indexer.indexer import Indexer
from services.indexer.pipeline import IndexingPipeline
from tests.test_methodology_v2 import METHODOLOGY, OBSERVATIONS, SPREAD

ROOT = Path(__file__).parent.parent
DAY = date(2026, 11, 21)
# 2.0.0 hashes computed by the pre-2.1 code on the fixtures in test_methodology_v2.
GOLDEN_V2_WITH_SPREAD = "0cd2f020db19660b"
GOLDEN_V2_NO_SPREAD = "0dc0ba328266446c"


def ep(provider, prompt, completion, quantization="fp8", context=131072, params=None, **extra):
    entry = {
        "provider_name": provider,
        "quantization": quantization,
        "context_length": context,
        "max_completion_tokens": 8192,
        "tag": provider.lower(),
        "supported_parameters": params if params is not None else ["tools", "max_tokens"],
        "pricing": {"prompt": str(prompt), "completion": str(completion), "input_cache_read": "0.0000001"},
    }
    entry.update(extra)
    return entry


FP8 = [ep(f"P{i}", f"0.00000{i + 1}", f"0.00000{i + 1}") for i in range(4)]
UNDISCLOSED = [
    ep("U1", "0.0000001", "0.0000001", quantization="unknown"),
    ep("U2", "0.0000002", "0.0000002", quantization=None),
]
MIXED = FP8 + UNDISCLOSED + [ep("F4", "0.0000003", "0.0000003", "fp4", context=1_048_576, params=["max_tokens"])]


def cell(summary, precision, bucket=None, tools=None):
    return [
        c for c in summary["cells"]
        if c["precision"] == precision
        and (bucket is None or c["context_bucket"] == bucket)
        and (tools is None or c["tools"] == tools)
    ]


class TestFacets:
    def test_context_buckets(self):
        assert [spread.context_bucket(n) for n in (8192, 32768, 32769, 131072, 131073, 999_999,
                                                  1_000_000, 1_048_576, None, "x")] == [
            "<=32k", "<=32k", "32-128k", "32-128k", "128k+", "128k+", "1M+", "1M+", "unknown", "unknown"]

    def test_precision_as_reported_and_undisclosed_is_its_own_bucket(self):
        summary = spread.summarize_endpoints("open/m", MIXED)
        precisions = {c["precision"] for c in summary["cells"]}
        assert precisions == {"fp8", "fp4", "undisclosed"}
        assert summary["quantization_mix"] == {"fp4": 1, "fp8": 4, "undisclosed": 2}
        assert summary["precision_disclosure"] == {"disclosed": 5, "undisclosed": 2}

    def test_planted_fault_unknown_never_folds_into_a_named_precision(self):
        summary = spread.summarize_endpoints("open/m", MIXED)
        fp8 = cell(summary, "fp8", "32-128k", True)[0]
        undisclosed = cell(summary, "undisclosed", "32-128k", True)[0]
        assert fp8["n"] == 4 and undisclosed["n"] == 2
        for value in ("unknown", None, "", "Unknown"):
            assert spread.precision_of(value) == "undisclosed"
        assert spread.precision_of("FP8") == "fp8"
        assert spread.precision_of("mxfp4") == "mxfp4"

    def test_cell_stats_null_below_three_but_n_reported(self):
        summary = spread.summarize_endpoints("open/m", MIXED)
        thin = cell(summary, "undisclosed")[0]
        assert thin["n"] == 2
        assert all(thin[k] is None for k in ("min", "p25", "median", "p75", "max", "p75_p25_ratio"))
        full = cell(summary, "fp8")[0]
        assert full["n"] == 4 and full["min"] == 1.0 and full["max"] == 4.0
        assert full["median"] == 2.5 and full["p75_p25_ratio"] == pytest.approx(3.25 / 1.75, abs=0.01)

    def test_tools_and_context_facets(self):
        summary = spread.summarize_endpoints("open/m", MIXED)
        fp4 = cell(summary, "fp4")[0]
        assert fp4["tools"] is False and fp4["context_bucket"] == "1M+"
        assert all(c["tools"] for c in cell(summary, "fp8"))

    def test_planted_fault_dated_and_undated_snapshots_are_never_pooled(self):
        assert spread.snapshot_kind("deepseek/deepseek-v4.1-flash-1017") == "dated"
        assert spread.snapshot_kind("lab/model-2026-10-17") == "dated"
        assert spread.snapshot_kind("deepseek/deepseek-v4.1-flash") == "undated"
        # An endpoint that names another model id must not enter this model's cells.
        stray = ep("Stray", "0.0000001", "0.0000001", model_id="lab/model-1017")
        summary = spread.summarize_endpoints("lab/model", FP8 + [stray])
        assert summary["endpoints"] == 4 and summary["snapshot"] == "undated"
        dated = spread.summarize_endpoints("lab/model-1017", [stray] * 4)
        assert dated["snapshot"] == "dated" and dated["endpoints"] == 4
        docs = spread.fetch_spread(
            [{"model_id": "lab/model", "open_weights": True},
             {"model_id": "lab/model-1017", "open_weights": True}],
            DAY, get=lambda url, timeout: _Response(FP8), pause_seconds=0)
        assert [m["model_id"] for m in docs["models"]] == ["lab/model", "lab/model-1017"]
        assert {m["snapshot"] for m in docs["models"]} == {"dated", "undated"}

    def test_observed_block_is_separate(self):
        live = [ep(f"P{i}", "0.000001", "0.000001", uptime_last_30m=99.5,
                   throughput_last_30m={"p50": 80.0}, latency_last_30m=0.4) for i in range(4)]
        summary = spread.summarize_endpoints("open/m", live)
        assert summary["observed"] == {"median_uptime": 99.5, "median_latency": 0.4, "median_throughput": 80.0}
        assert "uptime" not in json.dumps(summary["cells"])


class _Response:
    def __init__(self, endpoints):
        self.endpoints = endpoints

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"endpoints": self.endpoints}}


def build_day(endpoints=MIXED, day=DAY):
    return spread.fetch_spread_with_snapshot(
        [{"model_id": "open/m", "open_weights": True}], day,
        get=lambda url, timeout: _Response(endpoints), pause_seconds=0)


class TestSnapshot:
    def test_snapshot_rows_are_complete_sorted_and_canonical(self):
        doc, rows = build_day()
        assert set(rows[0]) == {"model_id", "provider", "tag", "quantization", "context_length",
                                "max_completion_tokens", "supported_parameters", "price_in",
                                "price_out", "cache_read"}
        raw = spread.canonical_snapshot(rows).decode().splitlines()
        parsed = [json.loads(line) for line in raw]
        assert raw == sorted(raw)
        assert all(line == json.dumps(json.loads(line), sort_keys=True, separators=(",", ":")) for line in raw)
        assert all(r["supported_parameters"] == sorted(r["supported_parameters"]) for r in parsed)
        assert doc["endpoint_snapshot_sha256"] == spread.snapshot_sha256(rows)

    def test_determinism_two_runs_same_snapshot_same_hash(self, tmp_path):
        (doc1, rows1), (doc2, rows2) = build_day(), build_day(list(reversed(MIXED)))
        assert spread.canonical_snapshot(rows1) == spread.canonical_snapshot(rows2)
        assert doc1 == doc2
        hashes = {_index_hash(tmp_path, doc, rows) for doc, rows in ((doc1, rows1), (doc2, rows2))}
        assert len(hashes) == 1

    def test_planted_fault_one_endpoint_price_changes_the_hash(self, tmp_path):
        doc, rows = build_day()
        changed = copy.deepcopy(MIXED)
        changed[0]["pricing"]["prompt"] = "0.0000011"
        doc2, rows2 = build_day(changed)
        assert doc2["endpoint_snapshot_sha256"] != doc["endpoint_snapshot_sha256"]
        assert _index_hash(tmp_path, doc, rows) != _index_hash(tmp_path, doc2, rows2)

    def test_pipeline_rejects_a_tampered_private_snapshot(self, tmp_path):
        doc, rows = build_day()
        _write_day(tmp_path, doc, rows)
        snap = tmp_path / "endpoints" / f"{DAY}.jsonl"
        snap.write_text(snap.read_text().replace("0.000001", "0.000009"))
        with pytest.raises(ValueError, match="does not match"):
            _run_pipeline(tmp_path)

    def test_pipeline_trusts_the_recorded_digest_without_the_private_file(self, tmp_path):
        doc, rows = build_day()
        _write_day(tmp_path, doc, rows)
        with_file = _run_pipeline(tmp_path)["verification_hash"]
        (tmp_path / "endpoints" / f"{DAY}.jsonl").unlink()
        assert _run_pipeline(tmp_path)["verification_hash"] == with_file

    def test_snapshot_is_git_ignored_like_observations(self):
        ignore = (ROOT / ".gitignore").read_text()
        assert "data/endpoints/*.jsonl" in ignore and "data/observations/*.jsonl" in ignore


def _write_day(data_dir, doc, rows):
    for sub in ("observations", "spread", "endpoints", "fixtures"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    (data_dir / "fixtures" / "methodology.yaml").write_text(yaml.safe_dump(_v21_methodology()))
    (data_dir / "observations" / f"{DAY}.jsonl").write_text(
        "\n".join(json.dumps(dict(o, effective_date=str(DAY))) for o in OBSERVATIONS) + "\n")
    (data_dir / "spread" / f"{DAY}.json").write_text(json.dumps(doc))
    (data_dir / "endpoints" / f"{DAY}.jsonl").write_bytes(spread.canonical_snapshot(rows))


def _run_pipeline(data_dir):
    return IndexingPipeline(data_dir=data_dir).run(DAY, dry_run=True)[0]


def _index_hash(tmp_path, doc, rows):
    sub = tmp_path / f"run{abs(hash(json.dumps(doc, sort_keys=True))) % 10**8}"
    _write_day(sub, doc, rows)
    return _run_pipeline(sub)["verification_hash"]


def _v21_methodology():
    return dict(METHODOLOGY, methodology_version="2.1.0")


@pytest.fixture
def indexer21(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text(yaml.safe_dump(_v21_methodology()))
    return Indexer(path)


class TestRules:
    def test_rule_id_is_sha256_of_canonical_content(self):
        import hashlib
        loaded = rules.load_rules()
        assert loaded
        for rule in loaded:
            content = {k: v for k, v in rule.items() if k != "rule_id"}
            expected = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert rule["rule_id"] == expected

    def test_editing_a_rule_changes_its_id(self):
        rule = rules.load_rules()[0]
        edited = dict(rule, undisclosed_values=["undisclosed", "fp8"])
        assert rules.rule_id(edited) != rule["rule_id"]

    def test_rules_are_append_only_ordered_and_unique(self):
        loaded = rules.load_rules()
        dates = [r["effective_from"] for r in loaded]
        assert dates == sorted(dates) and len(set(dates)) == len(dates)
        assert len({r["rule_id"] for r in loaded}) == len(loaded)
        # The first shipped rule is pinned: it may only ever be followed, never changed.
        assert loaded[0]["rule_id"] == PINNED_FIRST_RULE_ID

    def test_only_view_is_disclosure_and_no_grades(self):
        text = (ROOT / "rules" / "grade-rules.yaml").read_text()
        assert {r["view"] for r in rules.load_rules()} == {"disclosed_vs_undisclosed_precision"}
        for banned in ("grade: A", "grade: B", "grade: C"):
            assert banned not in text

    def test_active_rule_respects_effective_from(self):
        assert rules.active_rule(date(2026, 11, 19)) is None
        assert rules.active_rule(DAY)["rule_id"] == rules.load_rules()[0]["rule_id"]


PINNED_FIRST_RULE_ID = rules.load_rules()[0]["rule_id"]


class TestVerificationHash:
    def test_v2_hashes_are_unchanged(self, tmp_path):
        path = tmp_path / "m.yaml"
        path.write_text(yaml.safe_dump(METHODOLOGY))
        indexer = Indexer(path)
        day = date(2026, 11, 19)
        assert indexer.compute(OBSERVATIONS, day, SPREAD)["verification_hash"] == GOLDEN_V2_WITH_SPREAD
        assert indexer.compute(OBSERVATIONS, day)["verification_hash"] == GOLDEN_V2_NO_SPREAD
        out = indexer.compute(OBSERVATIONS, day, SPREAD)
        assert "rule_id" not in out and "endpoint_snapshot_sha256" not in out

    def test_hash_binds_snapshot_rule_and_spread(self, indexer21):
        doc, _ = build_day()
        base = indexer21.compute(OBSERVATIONS, DAY, doc)
        assert base["rule_id"] == rules.active_rule(DAY)["rule_id"]
        assert base["endpoint_snapshot_sha256"] == doc["endpoint_snapshot_sha256"]
        assert len(base["verification_hash"]) == 16

        other_snapshot = indexer21.compute(OBSERVATIONS, DAY, doc, "f" * 64)
        assert other_snapshot["verification_hash"] != base["verification_hash"]

        changed_cell = copy.deepcopy(doc)
        changed_cell["models"][0]["cells"][0]["n"] += 1
        assert indexer21.compute(OBSERVATIONS, DAY, changed_cell)["verification_hash"] != base["verification_hash"]

    def test_hash_ignores_the_observed_block(self, indexer21):
        doc, _ = build_day()
        base = indexer21.compute(OBSERVATIONS, DAY, doc)["verification_hash"]
        moved = copy.deepcopy(doc)
        moved["models"][0]["observed"] = {"median_uptime": 12.0}
        assert indexer21.compute(OBSERVATIONS, DAY, moved)["verification_hash"] == base

    def test_daily_output_validates_against_schema(self, indexer21):
        doc, _ = build_day()
        schema = json.loads((ROOT / "schemas" / "stci_daily.schema.json").read_text())
        jsonschema.validate(indexer21.compute(OBSERVATIONS, DAY, doc), schema)


class TestSpreadSchemaAndPublication:
    def test_spread_validates_against_schema(self):
        doc, _ = build_day()
        schema = json.loads((ROOT / "schemas" / "stci_spread.schema.json").read_text())
        jsonschema.validate(doc, schema)
        bad = copy.deepcopy(doc)
        bad["models"][0]["cells"][0]["context_bucket"] = "huge"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)

    def test_published_spread_has_cells_and_no_endpoint_rows_or_observed(self):
        doc, _ = build_day()
        doc["models"][0]["leak"] = [{"provider": "P0", "price_in": "1"}]
        clean = ps.clean_spread(doc)
        model = clean["models"][0]
        assert model["cells"] and model["precision_disclosure"]
        assert clean["endpoint_snapshot_sha256"] == doc["endpoint_snapshot_sha256"]
        text = json.dumps(clean)
        for banned in ("observed", "price_in", "price_out", "supported_parameters", "leak", '"tag"'):
            assert banned not in text

    def test_planted_fault_endpoint_rows_in_a_cell_fail_the_publish(self):
        with pytest.raises(ps.PublishError):
            ps.assert_no_endpoint_rows({"models": [{"cells": [{"price_in": "0.1"}]}]})
        with pytest.raises(ps.PublishError):
            ps.assert_no_endpoint_rows({"models": [{"endpoints": [{"provider": "x"}]}]})


class TestRulebookResolver:
    """A rerun of a published date must use the rulebook that published it."""

    DATA = ROOT / "data"

    @pytest.mark.parametrize("day,name", [
        ("2026-01-02", "methodology-1.0.0.yaml"),
        ("2026-03-06", "methodology-1.0.0.yaml"),
        ("2026-11-19", "methodology-2.0.0.yaml"),
        ("2026-11-20", "methodology-2.0.0.yaml"),
        ("2026-11-21", "methodology.yaml"),
        ("2027-01-01", "methodology.yaml"),
    ])
    def test_resolver_picks_the_governing_rulebook(self, day, name):
        assert rules.resolve_methodology_path(date.fromisoformat(day), self.DATA).name == name

    def test_missing_archive_falls_back_to_current(self, tmp_path):
        (tmp_path / "fixtures").mkdir()
        assert rules.resolve_methodology_path(date(2026, 11, 19), tmp_path).name == "methodology.yaml"

    def test_published_dates_resolve_to_their_published_version(self):
        for f in sorted((self.DATA / "indices").glob("2026-11-*.json")):
            published = json.loads(f.read_text())["methodology_version"]
            path = rules.resolve_methodology_path(date.fromisoformat(f.stem), self.DATA)
            if published != "2.1.0":
                assert rules.read_methodology_version(path) == published, f.name

    def _setup(self, tmp_path, day):
        import shutil
        shutil.copytree(self.DATA / "fixtures", tmp_path / "fixtures")
        for sub in ("observations", "spread", "indices"):
            (tmp_path / sub).mkdir()
        (tmp_path / "observations" / f"{day}.jsonl").write_text(
            "\n".join(json.dumps(dict(o, effective_date=str(day))) for o in OBSERVATIONS) + "\n")
        return tmp_path

    def test_2_0_0_date_reruns_through_the_pipeline_byte_for_byte(self, tmp_path):
        day = date(2026, 11, 19)
        data = self._setup(tmp_path, day)
        (data / "spread" / f"{day}.json").write_text(json.dumps(SPREAD))
        result = IndexingPipeline(data_dir=data).run(day, dry_run=True)[0]
        assert result["methodology_version"] == "2.0.0"
        assert "rule_id" not in result and "endpoint_snapshot_sha256" not in result
        # Golden built from the 2.0.0 path before facets existed (see TestVerificationHash).
        assert result["verification_hash"] == GOLDEN_V2_WITH_SPREAD
        (data / "spread" / f"{day}.json").unlink()
        assert IndexingPipeline(data_dir=data).run(day, dry_run=True)[0]["verification_hash"] == GOLDEN_V2_NO_SPREAD

    def test_pipeline_refuses_to_overwrite_a_different_methodology(self, tmp_path):
        day = date(2026, 11, 19)
        data = self._setup(tmp_path, day)
        (data / "indices" / f"{day}.json").write_text(json.dumps({"methodology_version": "2.0.0"}))
        forced = IndexingPipeline(data_dir=data, methodology_path=data / "fixtures" / "methodology.yaml")
        with pytest.raises(ValueError, match="refusing to overwrite"):
            forced.run(day)
        IndexingPipeline(data_dir=data).run(day, dry_run=True)  # resolved 2.0.0 is fine

    def test_pre_2_1_spread_has_no_facets_snapshot_or_rule(self):
        doc, rows = spread.fetch_spread_with_snapshot(
            [{"model_id": "open/m", "open_weights": True}], date(2026, 11, 19),
            get=lambda url, timeout: _Response(MIXED), pause_seconds=0, methodology_version="2.0.0")
        assert doc["methodology_version"] == "2.0.0"
        assert "rule_id" not in doc and "endpoint_snapshot_sha256" not in doc
        assert not set(spread.FACET_MODEL_KEYS) & set(doc["models"][0])

    def test_spread_cli_uses_the_resolved_rulebook_and_guards_overwrite(self, tmp_path, monkeypatch):
        day = date(2026, 11, 19)
        data = self._setup(tmp_path, day)
        (data / "observations" / f"{day}.jsonl").write_text(
            json.dumps({"model_id": "open/m", "open_weights": True}) + "\n")
        monkeypatch.setattr(
            spread, "fetch_spread_with_snapshot",
            lambda *a, **k: (spread.compute_spread(day, [], methodology_version=k["methodology_version"]), []))
        assert spread.main(["--date", str(day), "--data-dir", str(data)]) == 0
        written = json.loads((data / "spread" / f"{day}.json").read_text())
        assert written["methodology_version"] == "2.0.0" and "rule_id" not in written
        assert not (data / "endpoints").exists()
        (data / "spread" / f"{day}.json").write_text(json.dumps({"methodology_version": "9.9.9"}))
        assert spread.main(["--date", str(day), "--data-dir", str(data)]) == 1


class TestSnapshotHardening:
    def test_sort_is_total_over_every_field(self):
        base = {"model_id": "m", "provider": "p", "tag": "t", "quantization": "fp8",
                "price_in": "1", "price_out": "1"}
        a = dict(base, context_length=1000, max_completion_tokens=1, supported_parameters=["a"], cache_read="1")
        b = dict(base, context_length=2000, max_completion_tokens=1, supported_parameters=["a"], cache_read="1")
        c = dict(base, context_length=2000, max_completion_tokens=1, supported_parameters=["a"], cache_read="2")
        assert spread.canonical_snapshot([a, b, c]) == spread.canonical_snapshot([c, a, b])
        assert spread.canonical_snapshot([a, b, c]) == spread.canonical_snapshot([b, c, a])

    def test_mismatch_error_names_the_file_to_regenerate(self, tmp_path):
        doc, rows = build_day()
        _write_day(tmp_path, doc, rows)
        snap = tmp_path / "endpoints" / f"{DAY}.jsonl"
        snap.write_text(snap.read_text().replace("0.000001", "0.000009"))
        with pytest.raises(ValueError) as err:
            _run_pipeline(tmp_path)
        assert str(snap) in str(err.value) and "regenerate" in str(err.value)

    def test_committed_spread_never_carries_observed(self, tmp_path):
        live = [ep(f"P{i}", "0.000001", "0.000001", uptime_last_30m=99.0) for i in range(4)]
        doc, _ = build_day(live)
        assert doc["models"][0]["observed"]
        public, observed = spread.split_observed(doc)
        assert "observed" not in json.dumps(public) and observed == {"open/m": doc["models"][0]["observed"]}
        assert public["endpoint_snapshot_sha256"] == doc["endpoint_snapshot_sha256"]
