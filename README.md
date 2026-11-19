# STCI — Standardized Token Cost Index

[![Release](https://img.shields.io/github/v/release/jeremylongshore/stci-standard-inference-token-cost-index)](https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/releases)
[![Tests](https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/actions/workflows/tests.yml/badge.svg)](https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/U5S225PTME)

<!-- intent-select-partner:start -->
<p><a href="https://intentsolutions.io/"><img src="https://raw.githubusercontent.com/intent-solutions-io/.github/b82af5d3e7951d85e39ea9e65cc24ee8278722a7/assets/brand/claude-select-partner.svg" alt="Intent Solutions: Claude Partner Network Select Services Partner" width="300" height="95" /></a></p>

Intent Solutions is a Claude Partner Network Select Services Partner.
<!-- intent-select-partner:end -->

**The benchmark price for AI tokens.** Open, reproducible, run by nobody who sells them.

Site: [inferencepriceindex.com](https://inferencepriceindex.com)

> **Project status:** Revived 2026-11-19 under methodology 2.0.0
> ([000-docs/020](000-docs/020-DR-STND-stci-methodology-2-0-0.md)). The published
> series covers 2026-01-02 to 2026-03-06 (methodology 1.0.0), stops while the
> pipeline was switched off, and resumes 2026-11-19. Values across that boundary
> are not comparable: the baskets changed.

---

## The idea

Tokens are becoming a commodity. Every commodity market that works has a benchmark
price that nobody selling the commodity controls: Brent and WTI for crude, the
Baltic Dry Index for shipping. Tokens have none. Prices are set unilaterally, change
without notice, and are increasingly subsidized or resold by intermediaries, so nobody
can tell a fair price from a subsidy, budget a year ahead, or hedge a contract.

STCI is built on the Baltic Exchange model. A benchmark needs four things:

1. **Routes**: standard units to price. Model tiers today; cost per standard task later.
2. **A panel**: gateways and large consumers reporting what they actually paid,
   anonymized and volume-weighted.
3. **A public rulebook**: the methodology, every constituent, every exclusion, in writing.
4. **An audit trail**: a verification hash on every value, so a third party can
   recompute it, and administration independent of any seller.

### Not every token is the same token

Crude has grades. Tokens have serving precision, context length and uptime. The same
open-weight model is sold by dozens of providers at once, and the price is not the
only thing that differs. On 2026-11-19 DeepSeek V4.1 Flash was sold by 41 providers
through 50 endpoints at $0.12 to $1.95 per million blended tokens, a 16× spread; the
cheapest served it at fp4. Across 57 open-weight models the median spread was 2.5×.
STCI publishes this as the **neocloud spread**, alongside the index.

### Where STCI is on that ladder

| Rung | What | Status |
|---|---|---|
| 1 | Listed prices from one aggregator, reproducible, hash-verified | **live** |
| 2 | Grade and spread across providers | **live** |
| 3 | Reported-price panel (gateways, enterprises) | next; [say hello](mailto:jeremy@intentsolutions.io) if you run one |
| 4 | Forwards and contracts that settle against the index | later |

### How it started

Started 2026-01-01 and built in one week (v0.1.0 on January 3 through v0.5.0 on
January 8: collector, indexer, API, site). It ran daily until 2026-03-06, then the
author got pulled onto other work and switched the pipeline off. Revived 2026-11-19.

## The indices

Four equal-weighted daily reference rates in USD per 1M tokens, blended at 3:1
output:input:

- **STCI-FRONTIER**: each lab's most capable generally available model, cited to the provider's own description
- **STCI-EFFICIENT**: each lab's small, fast, cost-efficient tier
- **STCI-OPEN**: open-weight models with published weights, sold by at least 10 provider endpoints that day
- **STCI-ALL**: every eligible model
- **Neocloud spread** (not an index): per open-weight model, min, median and max across the providers selling it, the max/min ratio, and the serving precision of the cheapest endpoint

First reading, 2026-11-19: FRONTIER $12.04, EFFICIENT $1.05, OPEN $2.05 (23 models),
ALL $6.00 (344 models). Verification hash `3b422aefd8c603c8`.

Every value is deterministic: given the date and the observation set, STCI produces
identical output. Published: indices, the spread, the methodology. Not published: raw
observations (ADR [014](000-docs/014-AT-ADEC-data-licensing-private.md)); available on request.

## Data sources

| Tier | Source type | Today |
|---|---|---|
| T1 | Aggregator public API (OpenRouter models + per-provider endpoints) | in use |
| T2 | Provider-published pricing APIs | scaffolded |
| T3 | Reported prices from a panel | planned (rung 3) |

---

## Repository Structure

```
stci/
├── 000-docs/                 # All documentation (flat, 6767 naming)
│   ├── 001-PP-PROD-stci-prd.md            # Product Requirements
│   ├── 002-AT-ADEC-index-first-strategy.md # Architecture Decision
│   ├── 003-AT-SPEC-observation-schema.md   # Observation Schema Spec
│   ├── 004-AT-SPEC-stci-methodology.md     # Index Methodology Spec
│   ├── 005-OD-SOPS-recompute-runbook.md    # Deterministic Recompute
│   └── ...                                 # Additional docs
├── schemas/                  # Canonical JSON schemas
│   ├── observation.schema.json
│   └── stci_daily.schema.json
├── data/                     # Sample data and fixtures
│   └── fixtures/
│       ├── observations.sample.json
│       └── methodology.sample.yaml
├── services/                 # Application services
│   ├── collector/            # Price data collection
│   ├── indexer/              # Index computation
│   └── api/                  # Read-only API
├── scripts/                  # Utilities and verification
│   └── verify_repo.sh
├── skills/                   # Claude Code skills
│   └── stci-dataops/
│       └── SKILL.md
├── infra/                    # Infrastructure placeholders
├── .beads/                   # Beads issue tracking
├── LICENSE                   # MIT License
└── README.md                 # This file
```

---

## Core Concepts

### Observation
A single pricing data point for a specific model at a specific time:

```json
{
  "observation_id": "obs-2026-01-01-openai-gpt4o",
  "provider": "openai",
  "model_id": "gpt-4o",
  "model_display_name": "GPT-4o",
  "input_rate_usd_per_1m": 2.50,
  "output_rate_usd_per_1m": 10.00,
  "effective_date": "2026-01-01",
  "collected_at": "2026-01-01T12:00:00Z",
  "source_url": "https://openai.com/pricing",
  "source_tier": "T1",
  "currency": "USD",
  "schema_version": "1.0.0"
}
```

### Daily Index Output
Aggregated reference rate for a given date:

```json
{
  "date": "2026-01-01",
  "indices": {
    "STCI-ALL": {
      "input_rate": 3.42,
      "output_rate": 12.87,
      "blended_rate": 6.27,
      "model_count": 24,
      "dispersion": 0.42
    },
    "STCI-FRONTIER": {
      "input_rate": 4.85,
      "output_rate": 15.20,
      "blended_rate": 8.22,
      "model_count": 8
    }
  },
  "methodology_version": "1.0.0",
  "computed_at": "2026-01-01T23:59:00Z"
}
```

---

## Methodology (2.0.0)

Full rulebook: [000-docs/020](000-docs/020-DR-STND-stci-methodology-2-0-0.md).
Config: `data/fixtures/methodology.yaml`.

- **Eligibility is a rule.** Alias (`~lab/x-latest`), `:free`, `:batch`, router
  (negative sentinel) and unpriced listings are excluded with the reason logged;
  batch rates attach to the base model. The indexer re-applies the rules, so an old
  observation file cannot leak them in.
- **Constituents are cited.** FRONTIER and EFFICIENT hold one model per lab and
  tier, each quoting the provider's own description. STCI-OPEN is rule-based.
- **Weighting:** equal. Usage weighting waits on the reported-price panel.
- **Aggregation:** mean input and output rate per basket; blended at 3:1; dispersion
  as standard deviation.
- **Staleness:** every daily output lists `constituents_missing`; constituents are
  reviewed on the first of each month.
- **Hash:** SHA-256 over the sorted eligible observations, methodology version and
  date, plus the per-model endpoint counts when the liquidity screen ran.
- **Edge cases:** missing data carries forward at most 7 days; a basket below 50%
  coverage is not published.

---

## Agent Skill

The public `stci-dataops` skill evaluates and onboards pricing sources with
evidence, legal-review boundaries, schema validation, and deterministic tests:

```bash
npx skills add jeremylongshore/stci-standard-inference-token-cost-index \
  --skill stci-dataops
```

Research-only mode does not modify the repository. Collector implementation,
live collection, deployment, publication, and schedule changes have separate
approval boundaries.

## Quickstart

```bash
# Clone the repository
git clone https://github.com/jeremylongshore/stci-standard-inference-token-cost-index.git
cd stci-standard-inference-token-cost-index

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run verification
./scripts/verify_repo.sh

# Run tests
pytest

# Run collection pipeline (from fixtures)
python -m services.collector.pipeline --fixtures

# Run indexing pipeline
python -m services.indexer.pipeline --date 2026-01-02

# Start API (development)
python -m services.api.main
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/index/latest` | GET | Latest STCI values |
| `/v1/index/{date}` | GET | Index for specific date |
| `/v1/indices` | GET | List all available dates |
| `/v1/observations/{date}` | GET | Raw observations (local development server only; not published) |
| `/v1/methodology` | GET | Current methodology config |

---

## Trust Model

STCI is designed as a **reference rate product**. Trust is the moat:

1. **Transparency**: All methodology is documented and public
2. **Reproducibility**: Anyone can verify index values
3. **Provenance**: Every observation has source metadata
4. **Auditability**: Full history of changes and computations
5. **Neutrality**: No financial stake in any provider

---

## Status and roadmap

Live: collector, neocloud spread, deterministic indexer, read-only API, tests, and the
site at [inferencepriceindex.com](https://inferencepriceindex.com) (self-hosted).
Next: nightly runs on our own host with automatic publication, then the reported-price
panel (methodology 3.x). Tracked in Beads and
[issue #8](https://github.com/jeremylongshore/stci-standard-inference-token-cost-index/issues/8).

---

## Contributing

See documentation in `000-docs/` for:
- Contribution guidelines
- Source acceptance criteria
- Data quality requirements

---

## License

MIT License. See [LICENSE](./LICENSE).

---

## Contact

- Repository: [github.com/jeremylongshore/stci-standard-inference-token-cost-index](https://github.com/jeremylongshore/stci-standard-inference-token-cost-index)
- Issues: Use GitHub Issues or Beads (`bd create`)

---

*STCI — Making LLM pricing transparent, reproducible, and trustworthy.*
