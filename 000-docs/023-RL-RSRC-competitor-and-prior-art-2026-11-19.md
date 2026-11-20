---
title: "STCI competitor and prior-art brief"
doc_id: stci-competitor-brief
---

- **Date:** 2026-11-19 (research), verification addendum 2026-11-20
- **Status:** Dated snapshot. Rows marked "snippet" were seen in search results only; "unverified" were not checked.
- **Scope:** who else prices AI tokens, how commodity benchmarks are administered, what is known about quantization and subsidy, and which gaps STCI can own.

## 0. Method and limits

- Queries covered competitors, indices, quantization, subsidy, and benchmark-administration sources. I fetched about 10 primary or near-primary pages and ran about 12 searches.
- The Baltic Exchange white paper and the IOSCO PDF returned HTTP 403 or binary data. I relied on secondary summaries for those and say so below.
- I did not research LBMA, LME, ICE Brent, or Argus methodology. Those are unverified.
- `inferencepriceindex.com` is STCI itself, so I treat it as the subject, not a competitor. Its claims are self-reported.

## 1. Competitors and adjacent products

### Artificial Analysis

- **URL:** [methodology](https://artificialanalysis.ai/methodology) (fetched)
- **Publishes:** Per-model price, blended price, cost per task, speed, error rate
- **Data source:** Provider API rates and its own benchmark runs
- **Cadence:** Not stated; uses a "past 5 days" window
- **Pricing / model:** Site and data API; paid tier unverified
- **Reproducible / open:** Method public, raw data via API
- **Quantization or grade:** Not addressed; says results are "not intended to represent the maximum possible performance on any particular hardware platform"
- **Index concept:** Quality "Intelligence Index"; price is not an index
- **Last visible update:** Footer "© 2026"; no date shown

### OpenRouter (pricing, rankings, routing)

- **URL:** [quantization blog](https://openrouter.ai/blog/insights/llm-quantization) (fetched); [provider routing docs](https://openrouter.ai/docs/guides/providers) (snippet)
- **Publishes:** Per-endpoint listed prices; usage rankings
- **Data source:** Its own marketplace listings
- **Cadence:** Live
- **Pricing / model:** Marketplace; fee structure unverified
- **Reproducible / open:** Listed prices visible; rankings are usage-based
- **Quantization or grade:** Provider filter `quantizations` (int4, int8, fp4, mxfp4, nvfp4, fp6, fp8, mxfp8, fp16, bf16, fp32)
- **Index concept:** None
- **Last visible update:** Blog dated 11/11/2026

### LLM Stats, PricePerToken, LLMPriceCheck

- **URL:** not fetched
- **Publishes:** Unverified
- **Data source:** Unverified
- **Cadence:** Unverified
- **Pricing / model:** Unverified
- **Reproducible / open:** Unverified
- **Quantization or grade:** Unverified
- **Index concept:** Unverified
- **Last visible update:** Unverified

### Helicone LLM cost

- **URL:** [helicone.ai/llm-cost](https://www.helicone.ai/llm-cost) (snippet)
- **Publishes:** Pricing calculator over an open pricing dataset of 300+ models
- **Data source:** Open-source dataset
- **Cadence:** Unverified
- **Pricing / model:** Free
- **Reproducible / open:** Open source (per snippet)
- **Quantization or grade:** None seen
- **Index concept:** None
- **Last visible update:** Unverified

### LiteLLM model cost map

- **URL:** [GitHub JSON](https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json) (URL cited in snippet; not fetched) and [docs](https://docs.litellm.ai/docs/proxy/model_cost_map.md) (snippet)
- **Publishes:** Price and context-window JSON
- **Data source:** Community PRs and maintainers
- **Cadence:** Proxy fetches at startup; file cadence unverified
- **Pricing / model:** Free, open
- **Reproducible / open:** Git history is reproducible
- **Quantization or grade:** None
- **Index concept:** None
- **Last visible update:** Incident report dated 2026-01-27 (snippet)

### Portkey Models

- **URL:** [docs](https://portkey.ai/docs/product/model-catalog/portkey-models) (snippet)
- **Publishes:** Open pricing DB, JSON endpoint, no key
- **Data source:** Unverified
- **Cadence:** Unverified
- **Pricing / model:** Free
- **Reproducible / open:** Open
- **Quantization or grade:** None seen
- **Index concept:** None
- **Last visible update:** Coverage conflicts: 2,000+ models (announcement) vs 3,500+ (later post)

### Model Price Watch; apicostcalc.com

- **URL:** [apicostcalc.com](https://apicostcalc.com/api-pricing-data.html) (snippet)
- **Publishes:** Static JSON price lists (387 models claimed)
- **Data source:** Unverified
- **Cadence:** "Monthly" per snippet
- **Pricing / model:** Free
- **Reproducible / open:** Downloadable
- **Quantization or grade:** None
- **Index concept:** None
- **Last visible update:** Unverified

### BenchLM Token Price Index

- **URL:** [index](https://www.benchlm.ai/token-price-index) (snippet); [methodology v1.3](https://benchlm.ai/token-price-index/methodology) (snippet)
- **Publishes:** Median blended flagship price, base March 2023 = 100
- **Data source:** Flagship list prices
- **Cadence:** Monthly per snippet
- **Pricing / model:** Non-commercial series under CC BY-NC 4.0; commercial needs license (snippet)
- **Reproducible / open:** Partly; excludes caching, batch, flex, volume, off-peak discounts
- **Quantization or grade:** None
- **Index concept:** Yes, closest existing index
- **Last visible update:** Methodology "Updated November 12, 2026"; index reading 15 reported (snippet, unverified)

### Gradually LLM Price Index

- **URL:** [gradually.ai](https://www.gradually.ai/en/llm-price-index/) (snippet)
- **Publishes:** Market median over a curated basket
- **Data source:** Curated provider list
- **Cadence:** Unverified
- **Pricing / model:** Unverified
- **Reproducible / open:** Method described; basket is curated
- **Quantization or grade:** None
- **Index concept:** Yes; median of provider medians
- **Last visible update:** Methodology v2.2; $1.30 current median (snippet)

### Silicon Data LLM Token Expenditure Index (SDLLMTK)

- **URL:** [product page](https://www.silicondata.com/products/silicon-index/llm-token-expenditure-index) (snippet)
- **Publishes:** Daily effective price per million tokens; frontier vs open segments
- **Data source:** Usage-weighted; not fully public
- **Cadence:** Daily (snippet)
- **Pricing / model:** Commercial; Bloomberg listed
- **Reproducible / open:** Partly; "does not publicly disclose every parameter and proprietary weight" (snippet)
- **Quantization or grade:** Normalizes for input/output mix and context (snippet)
- **Index concept:** Yes
- **Last visible update:** April 2026 reading: frontier $4.20, open $0.85 (snippet, unverified)

### Inference Price Index (STCI)

- **URL:** [inferencepriceindex.com](https://inferencepriceindex.com/) (fetched)
- **Publishes:** FRONTIER, EFFICIENT, OPEN, ALL indices plus neocloud spread
- **Data source:** OpenRouter listed prices
- **Cadence:** Daily, SHA-256 verification hash
- **Pricing / model:** Free; "not an offer, quote, or financial advice"
- **Reproducible / open:** MIT code; inputs "available on request"
- **Quantization or grade:** Tracks precision served and provider spread
- **Index concept:** Yes
- **Last visible update:** 2026-11-19 values; launched 2026-01-01, switched off, relaunched 2026-11-19 (self-reported)

### Epoch AI inference price trends

- **URL:** [data insight](https://epoch.ai/data-insights/ai-inference-price-trends) (fetched)
- **Publishes:** Cost-to-reach-benchmark-level research
- **Data source:** Benchmark scores and per-token prices for named models
- **Cadence:** Page dated Mar 12, 2025
- **Pricing / model:** Free
- **Reproducible / open:** Partly
- **Quantization or grade:** None
- **Index concept:** Trend analysis, not an index
- **Last visible update:** Mar 12, 2025 (stale)

### "The Price of Progress" (arXiv 2511.23455)

- **URL:** [arXiv](https://arxiv.org/abs/2511.23455) (snippet)
- **Publishes:** Frontier cost decline 5–10x/yr; algorithmic efficiency ~3x/yr (snippet)
- **Data source:** Academic analysis
- **Cadence:** One-off
- **Pricing / model:** Free
- **Reproducible / open:** Partly
- **Quantization or grade:** None
- **Index concept:** No
- **Last visible update:** Nov 2025

### Vercel AI Gateway

- **URL:** [pricing docs](https://vercel.com/docs/ai-gateway/pricing) (snippet)
- **Publishes:** Pass-through list prices; per-response `providerMetadata.gateway.cost` (snippet)
- **Data source:** Provider list prices
- **Cadence:** Live
- **Pricing / model:** "No markup and no platform fee on tokens" per docs; add-ons and payment fees apply
- **Reproducible / open:** Not a price index
- **Quantization or grade:** No quantization disclosure seen
- **Index concept:** No
- **Last visible update:** Unverified

### Silicon Data H100 rental index (SDH100RT)

- **URL:** [Silicon Index](https://www.silicondata.com/products/silicon-index?gpu=h100) (snippet)
- **Publishes:** Daily H100 rental price; Bloomberg listed
- **Data source:** 10,000+ rental records/day (snippet)
- **Cadence:** Daily
- **Pricing / model:** Commercial
- **Reproducible / open:** Partly
- **Quantization or grade:** Not per precision
- **Index concept:** Yes
- **Last visible update:** Conflicting latest prints: $2.53 (one page) vs $2.88 (24 Oct 2026, FourWeekMBA)

### SemiAnalysis GPU Spot-Contract Composite

- **URL:** [index](https://gpu-index.semianalysis.com/) (snippet)
- **Publishes:** H100/A100/B200 hourly composite; Bloomberg SAH100SC
- **Data source:** Provider prices, weighted
- **Cadence:** Hourly
- **Pricing / model:** Underlying data via sales
- **Reproducible / open:** Partly; weights not public
- **Quantization or grade:** Not per precision
- **Index concept:** Yes
- **Last visible update:** Cached H100 $2.82 for Apr 2026 (snippet, possibly stale)

### Flopper; Uvik GPU trackers

- **URL:** [Flopper](https://flopper.io/docs/gpu-cloud-pricing-tracker) (snippet); [Uvik](https://uvik.net/blog/gpu-price-index/) (snippet)
- **Publishes:** Per-GPU hourly rates (337 rates, 24 clouds); list prices (13 GPUs, 19 providers)
- **Data source:** Provider pricing pages
- **Cadence:** Flopper every 6 hours (snippet)
- **Pricing / model:** Unverified
- **Reproducible / open:** Unverified
- **Quantization or grade:** None
- **Index concept:** Partly
- **Last visible update:** Unverified


Note: the search also turned up an "Inference Price Index" proxy-hosted page ([proxy-ga.blitzz.co](https://proxy-ga.blitzz.co/proxy/123456/inferencepriceindex.com/)). Its content was not checked, so I cannot confirm it is a separate attempt.

## 2. How commodity benchmarks are administered

- **Baltic Dry Index.** The BEISL white paper returned 403. Secondary sources (not authoritative) say: an approved panel of shipbrokers submits assessments on designated routes each working day; valid submissions are averaged per route; route assessments roll into BCI, BPI and BSI sub-indices. One source says route contributions are weighted equally unless defined otherwise, and that panellist identities per route are not disclosed. Handysize was removed in March 2018 (one source). Source list: [bmti-report](https://www.bmti-report.com/?p=275), [Wikipedia mirror](https://Www.Wikipedia.org/wiki/Baltic_Dry_Index), and the BEISL PDF (blocked; URL in search results). Status: partly unverified.
- **S&amp;P Global Platts Market-on-Close.** Platts publishes timing guidelines and increment rules; firm bids and offers are executable unless flagged otherwise; priority goes to "fully verifiable and transparent market information from entities that have been reviewed for participation"; trades outside the observed range may be excluded; editorial review applies ([MOC page](https://www.spglobal.com/platts/en/our-methodologies/market-on-close), snippet). No IOSCO compliance statement was found.
- **Argus, LBMA gold, LME, ICE Brent.** Not researched. Unverified.
- **IOSCO Principles for Financial Benchmarks.** The final report FR07/13 was published July 2013; the principles cover governance, quality of benchmark design and methodology, accountability and transparency, with application scaled to each benchmark's size and risk ([FSA Japan copy](https://www.fsa.go.jp/inter/ios/20130718-1/03.pdf) was a binary PDF and did not parse; press summary via [Mondo Visione](https://mondovisione.com/news/iosco-publishes-principles-for-financial-benchmarks-2013717), snippet; [etfstrategy](https://etfstrategy.com/iosco-unveils-benchmark-principles-in-response-to-libor-manipulation-45145), snippet). Follow-up reviews: [PD429](https://www.iosco.org/library/pubdocs/pdf/IOSCOPD429.pdf), [PD451](https://www.iosco.org/library/pubdocs/pdf/IOSCOPD451.pdf) and [PD553 (corrected 2026-11-20; PD549 was a mis-citation)](https://www.iosco.org/library/pubdocs/pdf/IOSCOPD553 (corrected 2026-11-20; PD549 was a mis-citation).pdf) (URLs seen in search results; not fetched). The principle-by-principle wording is not verified in this session.

## 3. Quantization and grade evidence

- **OpenRouter's controlled test (fetched 2026-11-19; blog dated 11/11/2026).** One model (Qwen3.8 27B), six endpoints, 280 tasks (240 scored, 40 multiplication), one day (20 Oct 2026). Quote: "didn't detect an accuracy difference between fp8, fp4 and fp16." All six endpoints scored 98.3%–99.2% on the 240 scored tasks. Cost per full run ranged from $0.58 (fp4, Darkbloom) to $1.24 (fp16, Cerebras). Authors: the test "doesn't show that 4-bit is safe for every model or workload," and it "can't rule out a gap of a point or two." Provider choice moved cost more than precision did.
- **Counter-evidence.** A Substack analysis reports that on GLM 5.2, both FP4 endpoints cost more per solved problem than the un-quantized endpoint, with occasional runaway generations ([collectgarbage substack](https://collectgarbage.substack.com/p/quantized-endpoints-charge-less-per), snippet). Treat it as single-model, non-peer-reviewed.
- **Disclosure as policy.** OpenRouter's `quantizations` routing filter is documented ([docs](https://openrouter.ai/docs/client-sdks/go/models/components/quantization.md), snippet). The docs also state that undeclared precision is represented as null. Together, Fireworks, DeepInfra and Groq were not checked for precision-disclosure policy; DeepInfra has a [precision guide](https://deepinfra.com/blog/precision-to-quantization-faster-cheaper-llms) (URL only).
- **Label caveat.** A routing guide notes that matching labels do not rule out differences in which tensors were quantized, calibration, or kernels ([simeononsecurity](https://simeononsecurity.com/articles/openrouter-provider-routing-quality-cost/), snippet).
- **Prior proposals to grade inference like commodities.** None found in this search. STCI's own site claims it measures precision served (self-reported).

## 4. Subsidy and below-cost evidence

- No audited per-token cost figures from OpenAI, Anthropic or Google were found.
- A "subsidy near 90%" estimate (H200 cluster cost divided by throughput) exists, but a critic says the author sells a token-optimization workshop and that neoclouds serve 70B models at $0.90–2.00/M ([mimetiq substack](https://mimetiq.substack.com/p/the-tokenmaxxing-hangover), snippet). Treat as contested.
- NVIDIA's "up to 10x lower cost per token on Blackwell" is vendor marketing ([NVIDIA blog](https://blogs.nvidia.com/blog/inference-open-source-models-blackwell-reduce-cost-per-token), snippet).
- One May 2026 comparison puts gpt-oss-120B at roughly $0.08 per million blended tokens (snippet, unverified).
- Rauch and Vercel AI Gateway: I found no sourced growth figures. The gateway's zero-markup claim is in Vercel's docs (snippet). Rauch's post could not be checked.
- SemiAnalysis, Epoch and academic work give GPU rental trends but no verified cost-per-token estimates for named providers in this session.

## 5. Gaps STCI can own

- No existing index publishes a verifiable, daily, open-data, rulebook-plus-hash price series for LLM tokens. BenchLM and Gradually are monthly or curated, and Silicon Data is proprietary.
- No index prices the same model across providers at a stated precision, so the "grade" dimension has no benchmark.
- Blend conventions differ across products: Artificial Analysis uses a 7:2:1 cache/input/output mix, BenchLM uses 3:1 input:output, and STCI uses 3 output per input. Nothing documents a shared convention, so cross-index comparisons are unsafe.
- Listed prices are not transaction prices. Silicon Data's expenditure index is closest to paid prices but is proprietary, so an open reported-price panel is an unfilled niche.
- No published administrator conflict-of-interest policy exists for token indices. STCI is operated by intentsolutions.io LLC and says independence is a requirement, not a current fact.
- Quantization disclosure is inconsistent: OpenRouter has a filter, but no index tracks it. A precision-tagged index would be new.
- Provider-level spread for the same open-weight model (STCI reports a 2.53x neocloud median and 34.8x widest case, self-reported) has no independent comparison.
- Epoch's cost-decline rates (9x–900x per year, March 2025) and the 2025 arXiv estimate (5–10x/yr) disagree and are stale. No maintained series tracks them.
- No index publishes a rulebook change log. STCI's own launch-off-relaunch history (Jan–Nov 2026) is a credibility gap it must disclose.
- Public GPU rental indices disagree widely (one H100 print $2.53 vs $2.88 on the same day; Implicator reports up to 8x disagreement between trackers). That supports building a reconciliation note.
- Commodity-style governance (panel, sealed inputs, independent administrator, appeal path) has no token-market equivalent in the sources reviewed.

## Recommendations for further research

- Fetch Helicone, PricePerToken, LLM Stats and LLMPriceCheck directly and fill the unverified rows.
- Retry the BEISL white paper and IOSCO FR07/13 through a different route, and verify principle numbers.
- Pull the Silicon Data SDLLMTK methodology PDF to compare its normalization with STCI's.
- Check the Vercel AI Gateway pricing page and the Rauch post for dated, sourced figures before any claim is made.

## Sources

- [Artificial Analysis methodology](https://artificialanalysis.ai/methodology)
- [STCI site](https://inferencepriceindex.com/)
- [OpenRouter quantization blog](https://openrouter.ai/blog/insights/llm-quantization)
- [Epoch AI inference price trends](https://epoch.ai/data-insights/ai-inference-price-trends)
- [IOSCO FR07/13 mirror, FSA Japan](https://www.fsa.go.jp/inter/ios/20130718-1/03.pdf) (binary; not parsed)
- [BenchLM methodology](https://benchlm.ai/token-price-index/methodology), [Gradually index](https://www.gradually.ai/en/llm-price-index/), [Silicon Data SDLLMTK](https://www.silicondata.com/products/silicon-index/llm-token-expenditure-index), [SemiAnalysis index](https://gpu-index.semianalysis.com/), [Vercel pricing](https://vercel.com/docs/ai-gateway/pricing), [LiteLLM docs](https://docs.litellm.ai/docs/proxy/model_cost_map.md), [Portkey models](https://portkey.ai/docs/product/model-catalog/portkey-models) (all snippet-level)

## Verification addendum (2026-11-20)

Retrieved 2026-11-20 by WebFetch/WebSearch; page extracts were summarized by a model and are not verbatim.

### [Helicone](https://www.helicone.ai/llm-cost) ([cost package](https://github.com/Helicone/helicone/tree/main/packages/cost))

- **Publishes:** Calculator + pricing registry, 300+ models
- **Cadence:** Not stated
- **License:** Repo is Apache 2.0 (data terms not separately confirmed)
- **Methodology:** Calculator arithmetic only, no index
- **Precision tag / same-model spread:** No precision field ("FP8" only inside some model IDs); incidental cross-provider rows

### [PricePerToken](https://www.pricepertoken.com)

- **Publishes:** Price table with context, cached-input price, some benchmark scores
- **Cadence:** "Last updated" 2026-11-19; no schedule
- **License:** None stated
- **Methodology:** None visible
- **Precision tag / same-model spread:** No precision; one provider per row

### [LLM Stats](https://llm-stats.com)

- **Publishes:** Composite rankings, 300+ models, Data API
- **Cadence:** "Updated continuously"
- **License:** None stated
- **Methodology:** Partial (TrueSkill-based score)
- **Precision tag / same-model spread:** Precision not mentioned; spread page not fetched

### [LLMPriceCheck](https://llmpricecheck.com)

- **Publishes:** Price table + calculator
- **Cadence:** Not stated; table looks stale (Llama-3 era)
- **License:** None stated
- **Methodology:** None; quality scores from Artificial Analysis
- **Precision tag / same-model spread:** Incidental cross-provider rows (e.g. Llama-3-70b: $0.59/$0.79 vs $0.65/$2.75); fp16/int8 only in two Cloudflare names

### [Silicon Data SDLLMTK](https://www.silicondata.com/products/silicon-index/llm-token-expenditure-index)

- **Publishes:** Daily usage-weighted price per 1M tokens; Bloomberg SDLLMTK; open/proprietary sub-series
- **Cadence:** Daily, confirmed (readings Nov 11-18 2026)
- **License:** Commercial
- **Methodology:** Partial: weighting formula, caps and basket size not disclosed; methodology PDF not retrieved
- **Precision tag / same-model spread:** Neither precision nor provider spread mentioned

### BEISL white paper (Baltic Exchange)

- **Publishes:** —
- **Cadence:** —
- **License:** —
- **Methodology:** **Still unverified** (HTTP 403). Related: [Baltic methodology hub](https://www.balticexchange.com/en/data-services/Methodology.html). Sources disagree on EU vs UK Benchmarks Regulation; resolve before citing.
- **Precision tag / same-model spread:** n/a

### IOSCO Principles for Financial Benchmarks (FR07/13)

- **Publishes:** 19 principles in four areas: governance, benchmark quality, methodology, accountability
- **Cadence:** —
- **License:** —
- **Methodology:** **Principle wording still unverified** (PD415 403; FSA mirror unparseable). Next try: [PD474](https://www.iosco.org/library/pubdocs/pdf/ioscopd474.pdf) or the [FSB page](https://www.fsb.org/2013/07/cos_130717/).
- **Precision tag / same-model spread:** n/a


**Net changes:** Helicone's open-source claim is confirmed; PricePerToken, LLM Stats and LLMPriceCheck now have rows and none publishes a rulebook, index, data license or precision tag; SDLLMTK's daily cadence and Bloomberg listing are confirmed while its April 2026 figures are stale; IOSCO follow-up review is PD553, not PD549; PD429 is a communique, not a review. STCI's precision-tagging and same-model spread gap versus every listed competitor holds.
