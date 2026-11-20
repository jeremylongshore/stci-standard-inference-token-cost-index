# STCI Governance and Rulebook Statement

**Document ID:** 024
**Category:** DR (Design)
**Type:** STND (Standard)
**Status:** DRAFT, written 2026-11-20
**Companion to:** `020-DR-STND-stci-methodology-2-0-0.md` (the methodology), `014-AT-ADEC-data-licensing-private.md` (data licensing, amended 2026-11-19)

This document says who runs STCI, what rules the administrator holds itself to, how
the rulebook has changed, and how STCI measures up against the IOSCO Principles for
Financial Benchmarks. It states gaps as gaps. Where a claim is a requirement or a
plan, it says so.

Note on sources: the runbook for the nightly refresh was named as an input (document
021). It does not exist in this checkout, so nothing here relies on it.

## 1. Methodology change log

Versions and dates are taken from `README.md`, `CHANGELOG.md` and the methodology
documents. Nothing is added beyond them.

| Date | Version | Change | Source |
|---|---|---|---|
| 2026-01-01 | Methodology 1.0.0 drafted | Hand-written baskets, equal weighting, 3:1 blend. Document 004 records its creation date as 2026-01-01. | `000-docs/004` |
| 2026-01-02 | Software release 0.1.0 | Collector, indexer, read-only API, schemas, tests. | `CHANGELOG.md` |
| 2026-01-02 to 2026-03-06 | Methodology 1.0.0 in force | The published series under 1.0.0. Archived at `data/fixtures/methodology-1.0.0.yaml`. | `000-docs/004`, `020` |
| 2026-01-04 | Software release 0.2.0 | Pricing Intelligence Center page, tests, CI, legal pages. | `CHANGELOG.md` |
| 2026-03-07 to 2026-11-18 | none | Not collected. The pipeline was switched off. | `000-docs/020` section 5 |
| 2026-11-19 | Methodology 2.0.0 | Eligibility is a rule. Constituents are cited to the provider's own description. STCI-OPEN is rule-based. The neocloud spread is added. `constituents_missing` is reported daily. | `000-docs/020`, `CHANGELOG.md` |
| 2026-11-19 | ADR 014 amended | New observation files are no longer committed. | `000-docs/014` |

Known inconsistency: `README.md` says v0.1.0 was built on January 3 and `CHANGELOG.md`
dates 0.1.0 as 2026-01-02. This document uses the changelog. The README should be
reconciled.

Rules for future changes (a requirement, not yet exercised under 2.0.0):

- A change to the methodology gets a new version number and an entry in this table.
- Constituent changes are announced 7 days ahead and reviewed on the first day of each month (`000-docs/020` section 7).
- Values across a version boundary are not comparable. Reconstructions are labelled reconstructed and published separately.

## 2. Administrator and conflict-of-interest statement

STCI is operated by intentsolutions.io LLC (the administrator).

**Independence is a requirement the administrator holds itself to. It is not an
established fact.** No third party has reviewed or certified the administrator's
independence. No audit has been done.

Disclosures:

- intentsolutions.io LLC does applied AI engineering work for clients.
- intentsolutions.io LLC may buy inference from model providers and gateways whose prices STCI records. Its purchases do not enter any index. The index uses listed prices only.
- The administrator has no stake in any index constituent that it is aware of. This is a self-statement and has not been verified by anyone else.
- Intent Solutions is a Claude Partner Network Select Services Partner. Anthropic models are index constituents. The partnership gives the administrator no say over constituent selection, and it does not alter the rules in document 020.

What the administrator commits to:

- Constituents are chosen by published rules and cited evidence, not by discretion.
- Any exercise of judgment is logged with a reason.
- A new conflict is added to this section when it is identified.

Not yet in place: a written conflicts register, a recusal procedure, and an independent
oversight body.

## 3. Blend convention

STCI blends input and output prices at **3 parts output to 1 part input** (3:1
output:input). The 3:1 figure is an assumption, stated and not measured
(`000-docs/020` section 9).

Other products use different conventions. This comes from the competitor research
dated 2026-11-19. Most rows were snippet-level and should be re-checked before anyone
relies on them.

| Product | Convention | Source |
|---|---|---|
| STCI | 3 output : 1 input | `000-docs/020` |
| Artificial Analysis | 7:2:1 mix of cache, input and output, per the research | https://artificialanalysis.ai/methodology (fetched) |
| BenchLM Token Price Index | 3:1 input:output, per the research | https://benchlm.ai/token-price-index/methodology (snippet only) |

STCI's weighting runs the opposite way to the BenchLM convention as the research
describes it. The research found no shared convention. Do not compare blended values
across indices.

## 4. Data retention and release

- Raw source responses, normalized observations and the per-endpoint snapshot are private. See ADR 014 as amended on 2026-11-19.
- Published: daily indices, the neocloud spread (aggregated per-model statistics, not the endpoint list) and the methodology.
- Each daily output carries a SHA-256 verification hash, truncated to 16 hex characters, over the sorted eligible observations, the methodology version and the date. When the liquidity screen ran, the hash also covers the per-model endpoint counts.
- Observations are available on request to support recomputation: support@intentsolutions.io.
- Private data stays on the collecting host and in its backups. No retention period has been set. That is a gap.
- 64 days of observations from 2026-01-02 to 2026-03-06 were committed to the public repository before ADR 014 was applied. They remain, because removing them would rewrite public history.
- OpenRouter's terms have not been reviewed for redistribution. That is why release stays conservative.
- Raw data is not published, so a reader cannot recompute a value without asking. The hash proves consistency with the observations the administrator holds. It does not prove those observations are correct.

## 5. IOSCO Principles for Financial Benchmarks

IOSCO published the Principles in July 2013 (FR07/13). Application is meant to scale
to the size and risk of the benchmark. STCI is not a regulated financial benchmark and
nothing references it. It is assessed here as a self-check only.

Caveat: the research could not fetch the IOSCO text. The principle names below are
from memory and have not been checked against the published report. Verify them before
this table is cited elsewhere.

Status: **Met**, **Partly**, **Not yet**. No principle is marked Met on the basis of
an independent review, because none has happened.

| No. | Principle | Status | Evidence |
|---|---|---|---|
| 1 | Overall Responsibility of the Administrator | Partly | intentsolutions.io LLC is named as administrator in this document; no formal accountability framework exists. |
| 2 | Oversight of Third Parties | Not yet | The single data source is OpenRouter; there is no agreement, and no oversight arrangement. |
| 3 | Conflicts of Interest for Administrators | Partly | Conflicts are disclosed in section 2; there is no register, recusal procedure or independent check. |
| 4 | Control Framework for Administrators | Partly | Deterministic code, tests, and a verification hash exist; no written control framework. |
| 5 | Internal Oversight | Not yet | One small team runs and reviews the index; no oversight committee. |
| 6 | Benchmark Design | Partly | Baskets, weighting and the 3:1 blend are documented in 020; the blend is an assumption and the source is a single aggregator. |
| 7 | Data Sufficiency | Partly | A 50% basket coverage floor and a 10-endpoint screen for STCI-OPEN exist; inputs are listed prices, not transactions. |
| 8 | Hierarchy of Data Inputs | Partly | Source tiers T1 to T3 are defined; only T1 is in use. |
| 9 | Transparency of Benchmark Determination | Partly | Methodology and daily hash are public; raw inputs are available only on request. |
| 10 | Periodic Review | Partly | Monthly constituent review is specified in 020; no completed review cycle exists under 2.0.0. |
| 11 | Content of the Methodology | Partly | Document 020 covers eligibility, constituents, hash, continuity and limitations; no expert-judgment policy or stress-condition procedure. |
| 12 | Changes to the Methodology | Partly | Versioned documents and a change log (section 1); a 7-day notice is specified but untested, and no stakeholder consultation process exists. |
| 13 | Transition Policy | Not yet | The 2026-03-07 to 2026-11-18 gap is disclosed, with no continuity or cessation policy. |
| 14 | Submitter Code of Conduct | Not yet | There are no submitters; the reported-price panel is planned. |
| 15 | Internal Controls over Data Collection | Partly | The collector logs exclusion reasons and the indexer re-applies the rules; no control over the source's own errors. |
| 16 | Complaints Procedures | Partly | Contact is support@intentsolutions.io (section 6); no response time, escalation path or record. |
| 17 | Audits | Not yet | No internal or external audit has been done. |
| 18 | Audit Trail | Partly | Observations and hashes are retained on the host; no retention period is set and the trail is not independently held. |
| 19 | Cooperation with Regulatory Authorities | Not yet | No procedure, and no regulator is involved. |

Count: Met 0, Partly 13, Not yet 6.

## 6. Complaints and corrections

Send complaints, correction requests and requests for observations to
**support@intentsolutions.io**.

Include the date, the index or model, the value in question and the reason it looks
wrong. The administrator will:

- Acknowledge the report.
- Recompute the value from the held observations.
- Publish a correction with a dated note if the value was wrong.

No response time is promised yet. No complaints log exists yet. Both are listed as
gaps in section 5.

## 7. What a grade is and is not

A grade describes how a provider serves a model: for example serving precision, as
published in the neocloud spread. It is a view over published facets.

- A grade is computed by a rule identified by a content-hashed `rule_id`. The same rule over the same facets gives the same grade. A changed rule gets a new `rule_id`.
- Grades are views, not independent measurements. They do not test output quality.
- Precision labels are reported by the source. Matching labels do not guarantee identical behavior. The research notes that evidence on quantization quality is mixed.
- **No audited grade exists.** No one outside the administrator has checked a grade.
- A grade is not an offer, quote, rating or financial advice.

## 8. Limits of this document

- It is a self-assessment. It is not a certification or a compliance claim.
- IOSCO principle names need verification against the primary text.
- Competitor details are snippet-level except where marked fetched.
- Statuses change as controls are built. Update the table and the change log together.
