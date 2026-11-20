"""
Grade rules (methodology 2.1.0): an append-only list of rule values, each with
an effective date. ``rule_id`` is the SHA-256 of the rule's canonical JSON, so a
changed rule is a different rule and the verification hash notices.
"""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import List, Optional

import yaml

RULES_PATH = Path(__file__).parent.parent.parent / "rules" / "grade-rules.yaml"


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def rule_id(rule: dict) -> str:
    """SHA-256 over the canonical content of a rule (any rule_id key ignored)."""
    content = {k: v for k, v in rule.items() if k != "rule_id"}
    return hashlib.sha256(canonical_json(content).encode()).hexdigest()


def load_rules(path: Optional[Path] = None) -> List[dict]:
    """Load rules sorted by effective_from, each with its computed rule_id."""
    raw = yaml.safe_load((path or RULES_PATH).read_text()) or {}
    rules = []
    for entry in raw.get("rules") or []:
        entry = dict(entry)
        entry["effective_from"] = str(entry["effective_from"])
        entry["rule_id"] = rule_id(entry)
        rules.append(entry)
    rules.sort(key=lambda r: r["effective_from"])
    return rules


def active_rule(target_date: date, path: Optional[Path] = None) -> Optional[dict]:
    """The latest rule whose effective_from is on or before target_date."""
    chosen = None
    for rule in load_rules(path):
        if rule["effective_from"] <= target_date.isoformat():
            chosen = rule
    return chosen


# Date ranges each archived rulebook governs. Anything later uses methodology.yaml.
ARCHIVED_RULEBOOKS = [
    ("1.0.0", "2026-03-06"),   # dates up to and including
    ("2.0.0", "2026-11-20"),
]
FIRST_FACET_VERSION = (2, 1, 0)


def resolve_methodology_path(target_date: date, data_dir: Path) -> Path:
    """
    The rulebook that governs target_date: an archived methodology-X.Y.Z.yaml
    when one covers the date, else the current methodology.yaml. Reruns of
    published dates therefore reproduce the published hash.
    """
    fixtures = Path(data_dir) / "fixtures"
    iso = target_date.isoformat()
    for version, last_day in ARCHIVED_RULEBOOKS:
        archived = fixtures / f"methodology-{version}.yaml"
        if iso <= last_day and archived.exists():
            if version == "2.0.0" and iso < "2026-11-19":
                continue  # the gap before 2.0.0 started is not 2.0.0's
            return archived
    return fixtures / "methodology.yaml"


def version_tuple(version) -> tuple:
    return tuple(int(x) for x in str(version or "0.0.0").split("."))


def uses_facets(version) -> bool:
    return version_tuple(version) >= FIRST_FACET_VERSION


def read_methodology_version(path: Path) -> str:
    return str((yaml.safe_load(Path(path).read_text()) or {}).get("methodology_version"))
