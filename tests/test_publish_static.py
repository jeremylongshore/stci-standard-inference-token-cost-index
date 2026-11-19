"""Tests for scripts/publish_static.py: the static site and /v1 JSON build."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SPREAD = ROOT / "tests" / "fixtures" / "spread"
spec = importlib.util.spec_from_file_location("publish_static", ROOT / "scripts" / "publish_static.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)


@pytest.fixture()
def built(tmp_path):
    out = tmp_path / "dist"
    ps.build(ROOT, out, spread_dir=FIXTURE_SPREAD)
    return out


def test_writes_every_api_file(built):
    for rel in ["v1/index/latest.json", "v1/indices.json", "v1/spread/latest.json",
                "v1/spread/2026-11-19.json", "v1/methodology.json"]:
        json.loads((built / rel).read_text())
    dates = json.loads((built / "v1/indices.json").read_text())
    latest = json.loads((built / "v1/index/latest.json").read_text())
    assert latest["date"] == dates["latest"] == max(dates["dates"])
    for d in dates["dates"]:
        assert (built / "v1" / "index" / f"{d}.json").is_file()


def test_gap_in_series_is_reported(built):
    dates = json.loads((built / "v1/indices.json").read_text())
    if len(dates["runs"]) > 1:
        assert dates["gaps"] and all(g["status"] == "not collected" for g in dates["gaps"])
    assert len(dates["gaps"]) == len(dates["runs"]) - 1


def test_never_publishes_observations_or_raw_fields(built):
    assert not (built / "v1" / "observations").exists()
    spread = (built / "v1/spread/latest.json").read_text()
    assert "endpoints_raw" not in spread and "raw_response" not in spread
    for f in (built / "v1").rglob("*.json"):
        text = f.read_text()
        assert "observation_id" not in text and "source_url" not in text


def test_spread_keeps_contract_fields(built):
    s = json.loads((built / "v1/spread/latest.json").read_text())
    m = s["models"][0]
    assert set(m) <= set(ps.SPREAD_MODEL_KEYS)
    assert m["cheapest"] == {"provider": "FixtureCloud", "quantization": "fp4", "blended": 0.25}


def test_pages_render_values_and_canonical(built):
    html = (built / "index.html").read_text()
    latest = json.loads((built / "v1/index/latest.json").read_text())
    assert f'${latest["indices"]["STCI-FRONTIER"]["blended_rate"]:,.2f}' in html
    assert '<link rel="canonical" href="https://inferencepriceindex.com/">' in html
    assert "fixture/open-a" in html and "8.0" in html
    for page in ["thesis.html", "methodology.html", "404.html", "privacy.html", "sitemap.xml", "robots.txt"]:
        assert (built / page).is_file()
    assert "style=" not in html and "<script src" not in html


def test_missing_spread_still_builds(tmp_path):
    ps.build(ROOT, tmp_path / "d", spread_dir=tmp_path / "none")
    assert not (tmp_path / "d/v1/spread/latest.json").exists()
    assert "No spread file" in (tmp_path / "d/index.html").read_text()


def test_mismatched_date_is_refused(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "fixtures", data / "fixtures")
    (data / "indices").mkdir()
    (data / "indices" / "2026-01-02.json").write_text(json.dumps(
        {"date": "2026-01-03", "indices": {"STCI-ALL": {"blended_rate": 1}}}))
    with pytest.raises(ps.PublishError):
        ps.build(ROOT, tmp_path / "out", data_dir=data)
