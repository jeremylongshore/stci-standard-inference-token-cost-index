---
name: stci-dataops
description: |
  Evaluate and onboard LLM pricing sources into STCI with evidence-backed
  source profiles, schema-valid observations, collector changes, and review
  receipts. Use when researching a provider or aggregator, assessing a pricing
  feed, or implementing an STCI collector; trigger with "evaluate this pricing
  source", "add a provider to STCI", or "review this collector".
allowed-tools: "Read,Write,Edit,Glob,WebFetch,WebSearch,Bash(python:*),Bash(git status:*),Bash(git diff:*)"
argument-hint: "[research|profile|implement|review] [provider-or-URL]"
version: "1.1.0"
author: "Jeremy Longshore <jeremy@intentsolutions.io>"
license: "MIT"
compatibility: "Requires an STCI repository checkout and Python 3.11+; live source evaluation requires network access. Implementation mode may require dependencies already declared by the repository."
tags: [llm-pricing, data-operations, provenance, collectors, validation]
model: inherit
effort: high
---

# STCI Data Operations

## Overview

Turn a proposed pricing source into a reproducible evidence packet and, when
requested, a tested STCI collector change. Treat published prices as
time-sensitive evidence and legal conclusions as a human-review boundary; see
the [source evaluation rubric](references/source-evaluation.md).

## Prerequisites

- Work from the STCI repository root with Python 3.11 or later.
- Read the current observation schema, collector base class, methodology, source
  profile template, and legal-risk register before proposing changes.
- Use existing dependencies and test fixtures. Ask before installing packages,
  changing authentication, enabling schedules, deploying, or publishing data.
- Confirm whether the request is research-only, profile, implementation, or
  review. Research-only mode must not modify repository files.

## Workflow

1. Establish repository truth with `Glob` and `Read`: locate the current schema,
   collector modules, tests, methodology, source-profile convention, provider
   IDs, and mappings.
2. Define the requested source and collection boundary: official provider,
   aggregator, manual submission, or fixture; public page or API; authentication;
   expected units; intended refresh cadence.
3. Research with `WebSearch` and `WebFetch`, preferring the provider's official
   pricing, API, terms, robots.txt, rate-limit, and changelog pages. Record the exact
   URL and retrieval time for every claim.
4. Separate observations from judgments. A reachable endpoint or permissive
   robots.txt file is not proof that automated collection or redistribution is
   legally authorized. Mark ambiguous terms `LEGAL REVIEW REQUIRED`.
5. Reconcile the proposed source tier against the repository's current written
   methodology and implementation. Report contradictions instead of silently
   choosing one; in particular, aggregator classification must be consistent
   across docs, schema usage, and collector code.
6. Produce the evidence and acceptance matrix in the evaluation reference.
   Stop in profile mode after presenting it.
7. In implementation mode, obtain approval for the proposed file set, then use
   `Write` or `Edit` to add the smallest collector, fixture, profile, and test
   changes that satisfy the [collector contract](references/collector-contract.md).
8. Run the narrow test first, then the repository suite. Use fixture or dry-run
   modes before any live collection. Inspect `git diff` and report all generated
   or data-bearing files; do not commit, push, enable CI schedules, deploy, or
   publish unless explicitly requested.

## Approval boundaries

- **Proceed:** read public documentation; inspect local code and fixtures; draft
  an evidence packet; run existing local tests.
- **Ask first:** install dependencies, use credentials, call a metered/private
  API, write repository files, run a live collection that stores data, or alter
  source-tier policy.
- **Explicit separate authorization:** deploy, publish observations, enable a
  schedule, change cloud/IAM configuration, commit, push, or open a PR.
- **Never:** scrape around access controls, expose tokens, invent permission from
  silence, copy restricted content, or label uncertain evidence as verified.

## Validation

```bash
python -m pytest tests/test_collector.py -v
python -m pytest tests/ -v --tb=short
python -m services.collector.pipeline --fixtures --dry-run
git status --short
git diff --check
```

Validate every candidate observation against `schemas/observation.schema.json`
and confirm normalization with fixed input/output unit tests. A live endpoint
response is evidence, not a golden fixture; redact secrets and minimize retained
payloads according to approved policy.

## Output

Return:

- mode, source identity, retrieval timestamp, and official evidence URLs;
- auth, rate-limit, automation, and redistribution status, with unknowns clear;
- unit mapping and required observation fields;
- source-tier recommendation plus any policy contradiction;
- proposed or changed files and approval received;
- tests run, exit results, observation counts, and validation failures;
- unresolved legal, operational, provenance, or data-quality risks;
- next human decision, without claiming deployment or publication occurred.

## Error Handling

- **Terms or permissions unclear:** stop before automation and request legal or
  owner review.
- **Authentication required:** document the mechanism; never request secrets in
  chat or place them in code, fixtures, URLs, or logs.
- **Rate units ambiguous:** retain the raw field and stop normalization until an
  official definition resolves the unit.
- **Schema drift:** preserve a minimal redacted sample, report changed fields,
  and fail closed rather than dropping records silently.
- **Rate limit or outage:** honor retry guidance; do not retry indefinitely or
  substitute stale data without the methodology's explicit carry-forward rule.
- **Cross-source disagreement:** report both values and provenance; do not average
  or choose a source outside the approved methodology.
- **Partial write or failed test:** show the diff and failure, preserve evidence,
  and do not publish.

## Examples

Research-only request:

```text
Evaluate Provider X's official pricing API for STCI. Produce evidence and a
source-tier recommendation, but do not edit files or call authenticated APIs.
```

Implementation request:

```text
Using the approved source profile, add the provider collector and fixed fixtures.
Run collector tests and the fixture dry-run; do not deploy or enable schedules.
```

## Resources

- [Source evidence and acceptance rubric](references/source-evaluation.md)
- [Repository-grounded collector contract](references/collector-contract.md)
