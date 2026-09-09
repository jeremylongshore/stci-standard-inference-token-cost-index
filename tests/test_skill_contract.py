"""Regression checks for the public stci-dataops Agent Skill."""

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "stci-dataops" / "SKILL.md"


def load_skill():
    text = SKILL_PATH.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def test_marketplace_metadata_contract():
    metadata, _ = load_skill()
    required = {
        "name",
        "description",
        "allowed-tools",
        "version",
        "author",
        "license",
        "compatibility",
        "tags",
    }
    assert required <= metadata.keys()
    assert metadata["name"] == "stci-dataops"
    assert re.fullmatch(r"\d+\.\d+\.\d+", metadata["version"])
    assert "Use when" in metadata["description"]
    assert "trigger with" in metadata["description"]


def test_operational_and_safety_contract():
    _, body = load_skill()
    for heading in (
        "## Prerequisites",
        "## Workflow",
        "## Approval boundaries",
        "## Validation",
        "## Output",
        "## Error Handling",
        "## Examples",
        "## Resources",
    ):
        assert heading in body

    assert "robots.txt" in body
    assert "is not proof" in body
    assert "LEGAL REVIEW REQUIRED" in body
    assert "do not commit, push, enable CI schedules, deploy, or" in body
    assert not re.search(r"\{(?:source|provider|model)[^}]*\}", body, re.I)


def test_bundled_references_resolve():
    _, body = load_skill()
    references = re.findall(r"\]\((references/[^)]+)\)", body)
    assert references
    for reference in references:
        target = SKILL_PATH.parent / reference
        assert target.is_file(), f"missing skill reference: {reference}"
        assert len(target.read_text(encoding="utf-8").splitlines()) >= 40


def test_public_readme_uses_current_repository_and_status():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "jeremylongshore/stci-standard-inference-token-cost-index" in readme
    assert "intent-solutions-io/stci-standard-llm-token-cost-index" not in readme
    assert "scheduled daily pipeline is intentionally disabled" in readme
    assert "npx skills add" in readme
