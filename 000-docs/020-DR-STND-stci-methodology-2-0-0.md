# STCI Methodology 2.0.0

**Document ID:** 020
**Category:** DR (Design)
**Type:** STND (Standard)
**Status:** ACTIVE from 2026-11-19
**Supersedes:** `004-DR-STND-stci-methodology.md` (1.0.0) for dates from 2026-11-19. Version 1.0.0 remains the rulebook for the published series 2026-01-02 to 2026-03-06, archived as `data/fixtures/methodology-1.0.0.yaml`.

## Why a new version

The 1.0.0 baskets were written in January 2026 by hand. By November two of nine FRONTIER constituents and three of seven OPEN constituents had been delisted, and the models that define the frontier today (GPT-6.2, Gemini 4, Claude Fable 5.2) were not in the index. The source catalog had also changed shape: on 2026-11-19 OpenRouter listed 92 `:batch` variants at half price, 17 free listings, 19 alias IDs and 8 routers priced at a negative sentinel. Under 1.0.0 the batch and free listings would have entered STCI-ALL as if they were separate models, and the aliases and routers were logged as schema failures.

2.0.0 fixes both: listing eligibility is a rule, constituents are cited to the provider's own description, the open-weight basket is rule-based, and a new measurement, the neocloud spread, records what the same open-weight model costs across the providers that sell it.

## 1. Listing eligibility

A catalog entry is an observation only if it is a separately priced model:

| Rule | Excluded | Reason recorded as |
|---|---|---|
| ID starts with `~` | `~anthropic/claude-opus-latest` | `alias` (points at another listing) |
| ID has a `:free` variant, or both prices are 0 | `openai/gpt-oss-20b:free` | `free` |
| ID has a `:batch` variant | `openai/gpt-6.2-astra:batch` | `batch`; its rates are attached to the base model as `batch_rate_input` / `batch_rate_output` |
| Either price is negative | `openrouter/auto` | `router` |
| Price missing or non-numeric | | `unpriced` |

The collector applies these rules and logs the counts per reason. The indexer re-applies the same rules from `methodology.yaml` (`eligibility:`), so an older observation file cannot leak an excluded listing into an index.

New optional observation fields: `cached_rate_input` (prompt-cache read price), `open_weights` and `hugging_face_id` (set when the source lists a Hugging Face repository for the weights).

## 2. Constituents

STCI-FRONTIER and STCI-EFFICIENT hold one model per lab and tier. Each entry in `methodology.yaml` carries a quotation from the provider's own model description on the source, so membership is evidence, not opinion. A `-pro` listing that is the same model served in a higher reasoning mode is not a separate constituent.

**STCI-FRONTIER (9):** openai/gpt-6.2-astra, anthropic/claude-fable-5.2, google/gemini-4-argon, x-ai/grok-4.7, meta/muse-wonder, mistralai/mistral-large-4-0, qwen/qwen4-max, moonshotai/kimi-k3.1-pro, deepseek/deepseek-v4-pro-0813.

**STCI-EFFICIENT (9):** openai/gpt-6-luna, anthropic/claude-haiku-5.5, google/gemini-4-hydrogen, meta/muse-ember, mistralai/mistral-small-2603, qwen/qwen3.8-flash, deepseek/deepseek-v4.1-flash-1017, z-ai/glm-5.3-flash, minimax/minimax-m3.1-flash.

**STCI-OPEN** is rule-based: an observation qualifies when the source lists published weights **and** that day's spread file shows at least 10 priced provider endpoints for it. Without a spread file the index is not published for that day. On 2026-11-19 the rule admits 23 models.

**STCI-ALL** is every eligible observation (344 on 2026-11-19).

Every daily output lists `constituents_missing` per explicit basket. A non-empty list is the signal to review; the `min_basket_coverage` floor (0.5) still decides whether the index publishes.

## 3. Neocloud spread

For every open-weight observation the collector fetches the source's per-provider endpoint list and computes, from endpoints with a positive price, the blended rate at the methodology's 3:1 output:input assumption. Per model it records endpoint and provider counts, min / p25 / median / p75 / max, the max/min and p75/p25 ratios, the serving-precision mix (fp4, fp8, mxfp4, ...), and the cheapest endpoint with its precision. Models with fewer than 4 priced endpoints are not reported. Output: `data/spread/{date}.json`.

The spread is a measurement of listed prices, not of prices paid. It answers one question the headline index cannot: how far apart are the prices of the same token, and is the cheapest one the same grade of token.

## 4. Verification hash

Unchanged in construction: SHA-256 over the sorted eligible observations, the methodology version and the date, truncated to 16 hex characters. When a basket used the liquidity screen, the per-model endpoint counts are included in the hashed input, so the hash binds the spread file that was used.

## 5. Series continuity

| Range | Methodology | Note |
|---|---|---|
| 2026-01-02 to 2026-03-06 | 1.0.0 | published; equal-weighted, hand-picked baskets |
| 2026-03-07 to 2026-11-18 | none | not collected (pipeline disabled for cost) |
| 2026-11-19 onward | 2.0.0 | this document |

Values across the boundary are not comparable; the baskets changed. Any reconstruction of the gap from archived snapshots will be labelled reconstructed and published separately.

## 6. Publication

Published: daily indices (`data/indices`), the spread (`data/spread`), the methodology. Not published from 2026-11-19: raw source responses and normalized observations (ADR 014, amended 2026-11-19). The verification hash lets anyone holding the observations reproduce the value; the observations are available on request.

## 7. Rebalancing

Constituents are reviewed on the first day of each month against the provider descriptions, with changes announced 7 days ahead, as in 1.0.0. A delisting mid-month leaves the basket short until the next review; the output's `constituents_missing` says so each day.

## 8. First run, 2026-11-19

| Index | $/1M blended | Models |
|---|---|---|
| STCI-FRONTIER | 12.04 | 9 |
| STCI-EFFICIENT | 1.05 | 9 |
| STCI-OPEN | 2.05 | 23 |
| STCI-ALL | 6.00 | 344 |

Spread: 57 models measured, 0 fetch errors; median max/min 2.53×, median p75/p25 1.31×. Most endpoints: deepseek/deepseek-v4.1-flash-1017, 50 endpoints from 41 providers, $0.12 to $1.95, 16.08×, cheapest at fp4. Verification hash `3b422aefd8c603c8`, reproduced on a second run.

Commands: `python -m services.collector.pipeline --date D`, `python -m services.collector.spread --date D`, `python -m services.indexer.pipeline --date D`.

## 9. Limitations

- Single source (OpenRouter) for both prices and the endpoint list.
- Equal weighting; usage weighting still needs reported volumes.
- The 3:1 blend is an assumption, stated, not measured.
- Spread uses listed prices; subsidized or negotiated prices are invisible to it. A reported-price panel is the planned remedy.
