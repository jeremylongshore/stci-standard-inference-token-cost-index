#!/usr/bin/env python3
"""Build the STCI static site and its static JSON API.

Reads committed data only:
  data/indices/<date>.json        daily index files
  data/spread/<date>.json         neocloud spread files (methodology 2.0.0+; 2.1.0 adds facet cells)
  data/fixtures/methodology.yaml  the current rulebook
  public/                         static assets (CSS, favicon)

Writes to --out (default dist/):
  index.html, thesis.html, methodology.html, the four legal pages, 404.html,
  sitemap.xml, robots.txt, plus every file in public/
  v1/index/latest.json, v1/index/<date>.json, v1/indices.json,
  v1/spread/latest.json, v1/spread/<date>.json, v1/methodology.json

Licensing (ADR 014): only indices and derived metrics are published. Every
published JSON object is rebuilt from an explicit allow-list of keys, so a raw
observation or raw API field that appears in a data file is dropped, never
passed through. Nothing is read from data/observations or data/raw.

Only dates on or after PUBLIC_START are published, in the pages and in /v1.

Dependencies: Python 3.11+ standard library and PyYAML.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://inferencepriceindex.com"
API_ALT = "https://stci.intentsolutions.io"
REPO = "https://github.com/jeremylongshore/stci-standard-inference-token-cost-index"
CONTACT = "support@intentsolutions.io"
NAME = "Standardized Token Cost Index"
# The public series starts here. Earlier internal runs are not published.
PUBLIC_START = "2026-11-19"
INDEX_ORDER = ["STCI-FRONTIER", "STCI-EFFICIENT", "STCI-OPEN", "STCI-ALL"]
INDEX_BLURB = {
    "STCI-FRONTIER": "Flagship models, one per lab",
    "STCI-EFFICIENT": "Cost-optimized models, one per lab",
    "STCI-OPEN": "Open-weight models sold by many providers",
    "STCI-ALL": "Every eligible listed model",
}

# Allow-lists. Anything not named here is not published.
INDEX_TOP_KEYS = ["date", "methodology_version", "computed_at", "verification_hash", "observation_count",
                  "rule_id", "endpoint_snapshot_sha256"]
INDEX_KEYS = ["input_rate", "output_rate", "blended_rate", "model_count", "dispersion",
              "models_included", "constituents_missing"]
SPREAD_TOP_KEYS = ["date", "methodology_version", "blend", "source", "rule_id",
                   "endpoint_snapshot_sha256"]
SPREAD_SUMMARY_KEYS = ["models_measured", "fetch_errors", "median_max_min_ratio",
                       "median_p75_p25_ratio", "widest", "most_endpoints"]
SPREAD_MODEL_KEYS = ["model_id", "endpoints", "providers", "min_blended", "p25_blended",
                     "median_blended", "p75_blended", "max_blended", "max_min_ratio",
                     "p75_p25_ratio", "quantization_mix", "cheapest", "snapshot",
                     "precision_disclosure", "cells"]
CELL_KEYS = ["precision", "context_bucket", "tools", "n", "min", "p25", "median", "p75", "max",
             "p75_p25_ratio"]
DISCLOSURE_KEYS = ["disclosed", "undisclosed"]
# Keys that only ever appear on a per-endpoint row of the private snapshot.
ENDPOINT_ROW_KEYS = {"tag", "price_in", "price_out", "cache_read", "supported_parameters",
                     "max_completion_tokens", "context_length", "provider_name"}
CHEAPEST_KEYS = ["provider", "quantization", "blended"]
REF_KEYS = ["model_id", "max_min_ratio", "endpoints", "providers"]


class PublishError(Exception):
    pass


def pick(src: dict, keys: list[str]) -> dict:
    return {k: src[k] for k in keys if k in src}


def is_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return len(s) == 10
    except ValueError:
        return False


def load_dated(directory: Path) -> dict[str, dict]:
    out = {}
    if not directory.is_dir():
        return out
    for f in sorted(directory.glob("*.json")):
        if not is_date(f.stem):
            continue
        data = json.loads(f.read_text())
        if data.get("date") != f.stem:
            raise PublishError(f"{f}: date field {data.get('date')!r} does not match file name")
        out[f.stem] = data
    return out


def clean_index(raw: dict) -> dict:
    out = pick(raw, INDEX_TOP_KEYS)
    indices = raw.get("indices") or {}
    out["indices"] = {}
    for name, body in indices.items():
        clean = pick(body, INDEX_KEYS)
        if not isinstance(clean.get("blended_rate"), (int, float)):
            raise PublishError(f"{raw.get('date')} {name}: blended_rate missing or not numeric")
        out["indices"][name] = clean
    if not out["indices"]:
        raise PublishError(f"{raw.get('date')}: no indices")
    return out


def clean_spread(raw: dict) -> dict:
    out = pick(raw, SPREAD_TOP_KEYS)
    summary = pick(raw.get("summary") or {}, SPREAD_SUMMARY_KEYS)
    for k in ("widest", "most_endpoints"):
        if isinstance(summary.get(k), dict):
            summary[k] = pick(summary[k], REF_KEYS)
    out["summary"] = summary
    models = []
    for m in raw.get("models") or []:
        c = pick(m, SPREAD_MODEL_KEYS)
        if isinstance(c.get("cheapest"), dict):
            c["cheapest"] = pick(c["cheapest"], CHEAPEST_KEYS)
        if isinstance(c.get("quantization_mix"), dict):
            c["quantization_mix"] = {str(k): int(v) for k, v in c["quantization_mix"].items()}
        if isinstance(c.get("cells"), list):
            c["cells"] = [pick(cell, CELL_KEYS) for cell in c["cells"]]
        if isinstance(c.get("precision_disclosure"), dict):
            c["precision_disclosure"] = pick(c["precision_disclosure"], DISCLOSURE_KEYS)
        models.append(c)
    out["models"] = models
    assert_no_endpoint_rows(out)
    return out


def assert_no_endpoint_rows(doc) -> None:
    """Facets publish; per-endpoint rows never do. Walk the whole document."""
    if isinstance(doc, dict):
        leaked = ENDPOINT_ROW_KEYS & set(doc)
        if leaked:
            raise PublishError(f"per-endpoint fields in published spread: {sorted(leaked)}")
        if isinstance(doc.get("endpoints"), (list, dict)):
            raise PublishError("per-endpoint rows in published spread")
        for v in doc.values():
            assert_no_endpoint_rows(v)
    elif isinstance(doc, list):
        for v in doc:
            assert_no_endpoint_rows(v)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


# ---------------------------------------------------------------- formatting

def e(x) -> str:
    return html.escape(str(x), quote=True)


def usd(x) -> str:
    return f"${x:,.2f}"


def ratio(x) -> str:
    return f"{x:.2f}×" if x < 10 else f"{x:.1f}×"


def long_date(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def series_runs(dates: list[str]) -> list[tuple[str, str]]:
    """Group sorted ISO dates into consecutive-day runs."""
    runs: list[tuple[str, str]] = []
    for s in dates:
        d = date.fromisoformat(s)
        if runs and (d - date.fromisoformat(runs[-1][1])).days == 1:
            runs[-1] = (runs[-1][0], s)
        else:
            runs.append((s, s))
    return runs


# ---------------------------------------------------------------- page shell

NAV = [("/", "Index"), ("/thesis", "Thesis"), ("/methodology", "Methodology and API"), ("/governance", "Governance")]
LEGAL = [("/privacy", "Privacy"), ("/terms", "Terms"), ("/acceptable-use", "Acceptable use"),
         ("/data-retention", "Data retention")]


def page(*, path: str, title: str, description: str, body: str, jsonld: dict | None = None) -> str:
    canonical = SITE + path
    bar = (ROOT / "vendor" / "estate-bar" / "fragments" / "estate-bar.stci.html").read_text().strip()
    nav = "".join(
        '<li><a href="{}"{}>{}</a></li>'.format(href, ' aria-current="page"' if href == path else "", label)
        for href, label in NAV
    )
    legal = "".join(f'<li><a href="{h}">{label}</a></li>' for h, label in LEGAL)
    ld = ""
    if jsonld:
        ld = ('<script type="application/ld+json">'
              + json.dumps(jsonld, separators=(",", ":")).replace("</", "<\\/")
              + "</script>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="STCI, the {NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#f6f6f4">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/fonts/ibm-plex-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/estate-bar/estate-bar.css">
<link rel="stylesheet" href="/styles.css">
{ld}
</head>
<body>
{bar}
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="wordmark" href="/"><span class="wordmark-mark">STCI</span><span class="wordmark-name">{NAME}</span></a>
    <nav aria-label="Primary"><ul class="nav">{nav}</ul></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <div class="footer-id">
      <p class="footer-mark">STCI</p>
      <p>The {NAME}. Built and run by <a href="https://intentsolutions.io">intentsolutions.io LLC</a>.
      Code MIT on <a href="{REPO}">GitHub</a>.</p>
      <p>Contact <a href="mailto:{CONTACT}">{CONTACT}</a></p>
      <p class="badge"><a href="https://intentsolutions.io/"><img src="/claude-select-partner.svg" alt="Intent Solutions: Claude Partner Network Select Services Partner" width="240" height="76"></a></p>
    </div>
    <nav aria-label="Legal"><ul class="footer-links">{legal}</ul></nav>
    <p class="footer-note">Listed prices are informational. They are not an offer, a quote or financial advice.</p>
  </div>
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------- sections

def index_cards(latest: dict) -> str:
    cards = []
    for name in INDEX_ORDER:
        body = latest["indices"].get(name)
        if not body:
            continue
        tier = name.split("-")[1].lower()
        missing = body.get("constituents_missing")
        miss = f'<p class="tape-note">{len(missing)} constituent(s) missing today</p>' if missing else ""
        cards.append(f"""<li class="tape-item tape-{tier}">
  <h3 class="tape-name">{e(name)}</h3>
  <p class="tape-value num">{usd(body['blended_rate'])}</p>
  <p class="tape-unit">per million tokens, blended</p>
  <p class="tape-sub">{e(INDEX_BLURB.get(name, ''))}. {body.get('model_count', '?')} models.</p>
  <p class="tape-detail num">in {usd(body['input_rate'])}, out {usd(body['output_rate'])}</p>
  {miss}
</li>""")
    return '<ul class="tape">' + "".join(cards) + "</ul>"


def spread_row(spread: dict | None) -> dict | None:
    if not spread:
        return None
    most = (spread["summary"].get("most_endpoints") or {}).get("model_id")
    return next((m for m in spread["models"] if m.get("model_id") == most), None)


def spread_lead(spread: dict | None) -> str:
    row = spread_row(spread)
    if not row:
        return '<p>The spread table publishes with the daily index.</p>'
    ch = row.get("cheapest") or {}
    return f"""<figure class="grade">
  <p class="grade-model"><code>{e(row['model_id'])}</code></p>
  <dl class="grade-facts">
    <div><dt>Providers</dt><dd class="num">{row['providers']}</dd></div>
    <div><dt>Endpoints</dt><dd class="num">{row['endpoints']}</dd></div>
    <div><dt>Cheapest</dt><dd class="num">{usd(row['min_blended'])}</dd></div>
    <div><dt>Dearest</dt><dd class="num">{usd(row['max_blended'])}</dd></div>
    <div><dt>Spread</dt><dd class="num">{ratio(row['max_min_ratio'])}</dd></div>
    <div><dt>Cheapest serves at</dt><dd class="num">{e(ch.get('quantization', 'unknown'))}</dd></div>
  </dl>
  <figcaption>One open-weight model, sold by {row['providers']} providers through {row['endpoints']} endpoints.
  Blended $ per million tokens on {e(long_date(spread['date']))}.</figcaption>
</figure>"""


PRECISION_ORDER = ("bf16", "fp16", "fp8", "mxfp8", "fp6", "int8", "fp4", "mxfp4", "nvfp4", "int4", "undisclosed")


def precision_floors(m: dict) -> list[tuple[str, float | None, int]]:
    """Cheapest blended price per reported precision, from the 2.1 facet cells.

    Returns (precision, min or None, endpoints). min is None when every cell for that precision is
    below the n >= 3 publication floor. Older spread files carry no cells; they fall back to the
    cheapest endpoint's precision alone.
    """
    cells = m.get("cells")
    if not cells:
        ch = m.get("cheapest") or {}
        q = (ch.get("quantization") or "").strip().lower()
        return [(q if q not in ("", "unknown", "none", "null") else "undisclosed", m.get("min_blended"), 1)]
    agg: dict[str, list] = {}
    for c in cells:
        a = agg.setdefault(c["precision"], [None, 0])
        a[1] += c.get("n", 0)
        if c.get("min") is not None:
            a[0] = c["min"] if a[0] is None else min(a[0], c["min"])
    rank = {p: i for i, p in enumerate(PRECISION_ORDER)}
    return sorted(((p, v[0], v[1]) for p, v in agg.items()), key=lambda t: rank.get(t[0], 50))


def precision_label(p: str) -> str:
    return "precision undisclosed" if p == "undisclosed" else p


def precision_lines(m: dict) -> str:
    parts = []
    for p, lo, n in precision_floors(m):
        price = f"from {usd(lo)}" if lo is not None else f"{n} endpoint{'s' if n != 1 else ''}, too few to price"
        parts.append(f"<li><span class=\"prec\">{e(precision_label(p))}</span> {price}</li>")
    return f'<ul class="prec-lines">{"".join(parts)}</ul>'


def _widest(spread: dict, limit: int) -> list[dict]:
    return sorted(spread["models"], key=lambda m: m.get("max_min_ratio", 0), reverse=True)[:limit]


def _spread_caption(spread: dict, shown: int) -> str:
    s = spread["summary"]
    measured = s.get("models_measured", len(spread["models"]))
    cap = (f"The {shown} widest spreads of {measured} open-weight models measured on {e(long_date(spread['date']))}. "
           f"Blended $ per million tokens, {spread.get('blend', {}).get('output_ratio', 3):g} output tokens per input token.")
    if "median_max_min_ratio" in s:
        cap += f" Median spread across all {measured}: {ratio(s['median_max_min_ratio'])}."
    return cap


def spread_cards(spread: dict | None, limit: int = 12) -> str:
    """Phone layout: one card per model instead of an eight-column table."""
    if not spread:
        return ""
    rows = _widest(spread, limit)
    cards = "".join(
        f"""<li class="spread-card"><h4><code>{e(m['model_id'])}</code></h4>
<p class="spread-meta">{m['endpoints']} endpoints &middot; {m['providers']} providers &middot;
<span class="hi">{ratio(m['max_min_ratio'])}</span> max/min</p>
{precision_lines(m)}
<p class="spread-meta">Median {usd(m['median_blended'])} &middot; dearest {usd(m['max_blended'])}</p></li>"""
        for m in rows
    )
    return f"""<div class="spread-cards"><p class="caption">{_spread_caption(spread, len(rows))}</p>
<ol class="cards-list" aria-label="Neocloud spread, widest models">{cards}</ol></div>"""


def spread_table(spread: dict | None, limit: int = 12) -> str:
    if not spread:
        return ""
    rows = _widest(spread, limit)
    trs = []
    for m in rows:
        trs.append(
            f"<tr><th scope=\"row\"><code>{e(m['model_id'])}</code></th>"
            f"<td>{m['endpoints']}</td><td>{m['providers']}</td>"
            f"<td>{usd(m['min_blended'])}</td><td>{usd(m['median_blended'])}</td><td>{usd(m['max_blended'])}</td>"
            f"<td class=\"hi\">{ratio(m['max_min_ratio'])}</td><td class=\"prec-cell\">{precision_lines(m)}</td></tr>"
        )
    return f"""<div class="table-scroll spread-table" role="region" aria-label="Neocloud spread, widest models" tabindex="0">
<table>
<caption>{_spread_caption(spread, len(rows))}</caption>
<thead><tr><th scope="col">Model</th><th scope="col">Endpoints</th><th scope="col">Providers</th>
<th scope="col">Cheapest</th><th scope="col">Median</th><th scope="col">Dearest</th>
<th scope="col">Max / min</th><th scope="col">Cheapest by precision</th></tr></thead>
<tbody>{''.join(trs)}</tbody>
</table></div>"""


LADDER = """<ol class="ladder">
<li><span class="rung now">Now</span><div><strong>Listed prices.</strong> Every separately priced model on one
aggregator (OpenRouter), normalized to dollars per million tokens and combined into four indices under a public
rulebook. Each day carries a verification hash that anyone holding the inputs can reproduce.</div></li>
<li><span class="rung now">Now</span><div><strong>Grades and spread.</strong> For open-weight models, the price of
every provider endpoint selling the same model, and the precision each one serves.</div></li>
<li><span class="rung next">Next</span><div><strong>A reported-price panel.</strong> Gateways and large buyers report
what they actually paid, anonymized and weighted by volume. Listed prices cannot show discounts, credits or
subsidies; a panel can.</div></li>
<li><span class="rung later">Later</span><div><strong>Contracts that settle against the index.</strong> Forwards that
let a buyer fix next year&rsquo;s token cost. This needs the panel and independent administration first.</div></li>
</ol>"""

ORIGIN = """<p>I started STCI on New Year&rsquo;s Day 2026 and built the first version in a week: the collector, the
indexer, the API and the site. It ran every day for two months. Then I got pulled onto other work and switched it off.</p>
<p>Then Guillermo Rauch argued that tokens are becoming the new unit of energy. Energy has benchmark prices;
tokens still did not. So I turned STCI back on, and relaunched it on November 19, 2026, with a rulebook written for
today&rsquo;s models and a measurement of grade the first version did not have.</p>
<p class="sig">Jeremy Longshore</p>"""


def landing(latest: dict, spread: dict | None, methodology: dict) -> str:
    d = latest["date"]
    row = spread_row(spread)
    grade_line = ""
    if row:
        grade_line = (f"<p>One open-weight model is sold by {row['providers']} providers at prices "
                      f"{ratio(row['max_min_ratio'])} apart, and the cheapest serves it at "
                      f"{e((row.get('cheapest') or {}).get('quantization', 'unknown'))}.</p>")
    return f"""<section class="hero">
  <div class="wrap hero-inner">
    <h1>The benchmark price for AI tokens.</h1>
    <p class="lead">Oil has Brent. Shipping has the Baltic Dry. Tokens have no price their sellers don&rsquo;t set.</p>
    <p class="actions"><a class="btn" href="/thesis">Read the thesis</a><a class="btn btn-ghost" href="#today">Today&rsquo;s index</a></p>
  </div>
</section>

<section class="section" aria-labelledby="why">
  <div class="wrap split">
    <h2 id="why">Tokens need a benchmark</h2>
    <div class="split-body">
      <p>Every commodity market that works has a reference price no single seller sets. Brent and WTI price crude.
      The Baltic Dry Index prices bulk shipping. Contracts, budgets and hedges are written against those numbers.</p>
      <p>Tokens have none. Each provider sets its own price and changes it without notice, and more tokens reach
      buyers subsidized or resold. Nobody can tell a fair price from a subsidy, budget a year ahead, or hedge.</p>
    </div>
  </div>
</section>

<section class="section" aria-labelledby="pillars">
  <div class="wrap">
    <h2 id="pillars">What a benchmark needs</h2>
    <ol class="pillars">
      <li><h3>Routes</h3><p>Standard units everyone prices the same way. Model tiers today, the cost of a defined task later.</p></li>
      <li><h3>A panel</h3><p>Gateways and large buyers reporting what they actually paid, anonymized and weighted by volume.</p></li>
      <li><h3>A public rulebook</h3><p>How every value is computed, written down before it is used.</p></li>
      <li><h3>An audit trail</h3><p>Values anyone can reproduce, administered independently of the sellers.</p></li>
    </ol>
  </div>
</section>

<section class="section section-band" aria-labelledby="grades">
  <div class="wrap split">
    <div>
      <h2 id="grades">Not every token is the same token</h2>
      <p>Crude has grades: light, heavy, sweet, sour. Tokens have grades too: serving precision, context length,
      uptime. The neocloud spread is the first measurement of that.</p>
      {grade_line}
    </div>
    {spread_lead(spread)}
  </div>
</section>

<section class="section wide" aria-labelledby="ladder">
  <div class="wrap split">
    <h2 id="ladder">Where STCI is today</h2>
    <div class="split-body">{LADDER}</div>
  </div>
</section>

<section class="section" id="today" aria-labelledby="today-h">
  <div class="wrap">
    <h2 id="today-h">Today&rsquo;s index</h2>
    <p class="section-lead">{e(long_date(d))}. Dollars per million tokens, blended at
    {methodology.get('output_ratio', 3):g} output tokens per input token.</p>
    {index_cards(latest)}
    <h3 class="table-head">The neocloud spread</h3>
    {spread_table(spread)}
    {spread_cards(spread)}
    <p class="source">Precision is what each provider reports. It is a fact about the endpoint, not a verdict on the
    tokens: OpenRouter&rsquo;s own test (November 11, 2026) found no clear accuracy gap between fp16, fp8 and fp4 on one
    model, and could not rule out a point or two. The provider can matter as much as the precision.</p>
    <p class="source">Source: listed prices on OpenRouter, from its model catalog and each model&rsquo;s provider
    endpoints. Listed prices, not prices paid. As JSON: <a href="/v1/index/latest.json">/v1/index/latest.json</a>
    and <a href="/v1/spread/latest.json">/v1/spread/latest.json</a>.</p>
  </div>
</section>

<section class="section" aria-labelledby="origin">
  <div class="wrap split">
    <h2 id="origin">Where it came from</h2>
    <div class="split-body origin">{ORIGIN}</div>
  </div>
</section>

<section class="section section-ink" aria-labelledby="ask">
  <div class="wrap split">
    <h2 id="ask">Report what you pay</h2>
    <div class="split-body">
      <p>The next rung needs prices paid, not prices listed. If you run an LLM gateway, or your company buys tokens
      at volume, report what you pay. Reports are anonymized and aggregated before anything is published.</p>
      <p class="actions"><a class="btn btn-light" href="mailto:{CONTACT}?subject=STCI%20panel">Email {CONTACT}</a><a class="btn btn-ghost-light" href="{REPO}">Code and data on GitHub</a></p>
    </div>
  </div>
</section>

<section class="section" aria-labelledby="repro">
  <div class="wrap split">
    <h2 id="repro">Reproduce it</h2>
    <div class="split-body">
      <p>The rulebook is public. Today&rsquo;s values carry verification hash
      <code>{e(latest.get('verification_hash', ''))}</code>: SHA-256 over the sorted eligible listings, the rulebook
      and the date. Anyone holding the inputs can recompute it, and the inputs are available on request.</p>
      <p><a href="/methodology">Methodology and API</a></p>
    </div>
  </div>
</section>"""


def thesis_page(spread: dict | None) -> str:
    return f"""<article class="wrap prose">
<h1>Tokens need a benchmark price</h1>
<p class="lead">AI tokens are turning into a commodity. Commodities that trade well share one piece of
infrastructure: a reference price the sellers do not control. Tokens do not have one yet. This is the case for
building it, and an honest account of how far STCI has got.</p>

<h2>A commodity without a price</h2>
<p>A million tokens from a capable model is becoming an input that businesses buy the way they buy fuel or
freight: in volume, from several suppliers, against a budget. Guillermo Rauch put the moment as &ldquo;more like an
oil rush than a gold rush.&rdquo; Oil is the right comparison, because oil has something tokens lack.</p>
<p>Crude trades against Brent and WTI. Dry bulk shipping trades against the Baltic Dry Index, which the Baltic
Exchange compiles each day from a panel of shipbrokers reporting what routes actually cost. No refiner and no
shipowner sets those numbers. Supply contracts, budgets, loans and hedges are written against them.</p>
<p>Token prices work differently. Each provider sets its own price and changes it when it likes. A growing share
of tokens reach buyers through intermediaries, gateways and resellers, some of whom subsidize the price to win
volume. From the outside nobody can tell a fair price from a subsidy, nobody can budget a year ahead with
confidence, and nobody can hedge, because there is nothing neutral to settle against.</p>

<h2>What a benchmark needs</h2>
<p>The working examples share four parts.</p>
<ul>
<li><strong>Routes.</strong> The Baltic index is built from named routes and vessel sizes, so everyone prices the
same thing. For tokens the first routes are model tiers: frontier, efficient, open-weight. Later routes are tasks:
the cost to complete a defined unit of work, which is what a buyer actually cares about.</li>
<li><strong>A panel.</strong> Credibility comes from the people who pay. Gateways and large consumers report the
effective price they paid per million tokens, anonymized, and the index weights them by volume so a few odd
trades cannot move it.</li>
<li><strong>A public rulebook.</strong> How each value is calculated, which listings are eligible, how baskets
change and when, all written down before it is applied.</li>
<li><strong>An audit trail and independent administration.</strong> Values that someone else can recompute,
regular checks that the rulebook was followed, and an administrator that is not one of the sellers.</li>
</ul>

<h2>Grades: not every token is the same token</h2>
<p>Brent is a grade of crude, not crude in general. A barrel of heavy sour is worth less than a barrel of light
sweet, and the market prices the difference. Tokens have grades as well: the numerical precision the model is
served at, the context it can use, the uptime and latency behind it. Two tokens from &ldquo;the same model&rdquo;
are not necessarily the same product.</p>
<p>The neocloud spread is STCI&rsquo;s first measurement of grade. For each open-weight model it collects the
price of every provider endpoint selling it and the precision each one serves.</p>
{spread_lead(spread)}
<p>A benchmark that ignored this would average fp4 tokens with full-precision tokens and call the result one price.</p>

<h2>Where STCI is on that ladder</h2>
{LADDER}
<p>What STCI is not, yet: it does not see prices paid, it uses one source for listed prices, it weights models
equally, and its 3:1 output-to-input blend is a stated assumption, not a measurement. Those limits are in the
<a href="/methodology">methodology</a>. The panel is the planned remedy for most of them.</p>

<h2>Who it is for</h2>
<p>Gateways and brokers, who see prices paid every day and would gain most from a neutral reference to quote
against. Enterprises that buy tokens at volume and want to know whether their price is fair. Finance teams that
need to budget a year of inference. If that is you, <a href="mailto:{CONTACT}?subject=STCI%20panel">report what
you pay</a>. Today&rsquo;s values and the full spread table are on the <a href="/#today">index page</a>.</p>
</article>"""


def methodology_page(methodology: dict, latest: dict) -> str:
    rows = []
    for name, spec in (methodology.get("indices") or {}).items():
        members = spec.get("models") or spec.get("constituents") or []
        ids = []
        for m in members:
            ids.append(m if isinstance(m, str) else (m.get("id") or m.get("model_id") or ""))
        basket = (", ".join(f"<code>{e(m)}</code>" for m in ids if m) if ids
                  else e(spec.get("rule") or "Rule-based"))
        rows.append(f"<tr><th scope=\"row\">{e(name)}</th><td>{e(spec.get('description', ''))}</td>"
                    f"<td>{basket}</td></tr>")
    r = methodology.get("output_ratio", 3)
    return f"""<article class="wrap prose">
<h1>Methodology and API</h1>
<p class="lead">How the index is computed, what is published, and how to read it as JSON.</p>
<h2>The rulebook</h2>
<ul>
<li><strong>Unit.</strong> US dollars per million tokens. The blended rate assumes {r:g} output tokens per input
token: (input + {r:g} &times; output) / {r + 1:g}.</li>
<li><strong>Source.</strong> Listed prices from OpenRouter: the model catalog, and each open-weight model&rsquo;s
list of provider endpoints.</li>
<li><strong>Eligibility.</strong> Only separately priced models count. Aliases, free listings, batch variants and
routers are excluded by rule.</li>
<li><strong>Baskets.</strong> FRONTIER and EFFICIENT hold one model per lab, each cited to the provider&rsquo;s own
description. OPEN admits open-weight models sold through at least ten priced endpoints. ALL is every eligible
listing. Each day lists any basket constituent that is missing.</li>
<li><strong>Weighting.</strong> Equal. Volume weighting needs reported volumes, which needs the panel.</li>
<li><strong>The neocloud spread.</strong> For each open-weight model with at least four priced endpoints: endpoint
and provider counts, minimum, quartiles, median and maximum blended price, the max/min and p75/p25 ratios, the
serving-precision mix, and the cheapest endpoint with its precision. From methodology 2.1.0 each model also
carries facet cells (reported precision, context bucket, tool support) with the count and quartiles of each
cell; a missing precision is its own &ldquo;undisclosed&rdquo; cell, and cells under three endpoints publish
their count only. There are no grades, only facets and a disclosed-versus-undisclosed precision count.</li>
<li><strong>Publication.</strong> Indices and derived spread metrics only. Raw source responses and individual
listings are not published; they are available on request. Each day publishes the SHA-256 of its private
endpoint snapshot.</li>
<li><strong>Verification.</strong> Each day carries a SHA-256 hash over the sorted eligible listings, the rulebook
and the date, truncated to 16 hex characters. From methodology 2.1.0 the hash also covers the endpoint
snapshot digest, the grade-rule id and the spread output. Today: <code>{e(latest.get('verification_hash', ''))}</code>.</li>
<li><strong>Rebalancing.</strong> Constituents are reviewed on the first day of each month, with changes announced
seven days ahead.</li>
</ul>
<h2>Limits</h2>
<ul>
<li>One source for both prices and endpoint lists.</li>
<li>Equal weighting.</li>
<li>The {r:g}:1 blend is an assumption, stated, not measured.</li>
<li>Listed prices only: subsidized or negotiated prices are invisible until there is a reported-price panel.</li>
</ul>
<h2>Baskets</h2>
<div class="table-scroll" role="region" aria-label="Index baskets" tabindex="0">
<table class="table-text"><thead><tr><th scope="col">Index</th><th scope="col">What</th><th scope="col">Constituents</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>

<h2 id="api">JSON API</h2>
<p>Static JSON files. No key, readable cross-origin (<code>Access-Control-Allow-Origin: *</code>). The same paths
answer on <code>{SITE}</code> and <code>{API_ALT}</code>, with or without the <code>.json</code> extension.</p>
<div class="table-scroll" role="region" aria-label="API endpoints" tabindex="0">
<table class="table-text"><thead><tr><th scope="col">Path</th><th scope="col">Returns</th></tr></thead><tbody>
<tr><th scope="row"><a href="/v1/index/latest.json"><code>/v1/index/latest.json</code></a></th><td>The latest daily index</td></tr>
<tr><th scope="row"><code>/v1/index/&lt;YYYY-MM-DD&gt;.json</code></th><td>The index for one date</td></tr>
<tr><th scope="row"><a href="/v1/indices.json"><code>/v1/indices.json</code></a></th><td>Every published date</td></tr>
<tr><th scope="row"><a href="/v1/spread/latest.json"><code>/v1/spread/latest.json</code></a></th><td>The latest neocloud spread</td></tr>
<tr><th scope="row"><code>/v1/spread/&lt;YYYY-MM-DD&gt;.json</code></th><td>The spread for one date</td></tr>
<tr><th scope="row"><a href="/v1/methodology.json"><code>/v1/methodology.json</code></a></th><td>The rulebook as published</td></tr>
</tbody></table></div>
<pre><code>curl -s {SITE}/v1/index/latest.json</code></pre>

<h2 id="grades">What a grade is and is not</h2>
<p>STCI publishes facts about each endpoint, never a verdict on its tokens. For every open-weight model the spread
groups endpoints by the precision the provider reports, the context they offer and whether they accept tools, and
publishes the cheapest, quartiles and dearest price of each group with at least three endpoints. Individual
endpoint prices are not published.</p>
<p>A grade, if STCI ever publishes one, is a named rule over those groups. Each rule is stored as data and
identified by the hash of its content, the <code>rule_id</code> printed in every daily file, so a rule cannot change
without the identifier changing. The only rule in force sorts endpoints into precision disclosed and precision
undisclosed.</p>
<p>No grade has been audited. A grade will be published only after the same prompts have been run through
reference-precision and lower-precision endpoints of the same model and the results show a difference worth
naming. A missing precision is shown as undisclosed; it is not treated as low quality.</p>
</article>"""


LEGAL_SCOPE = """<aside class="scope">
<p><strong>For STCI.</strong> This policy is the Intent Solutions estate policy, published unchanged and
applying to inferencepriceindex.com and stci.intentsolutions.io, operated by intentsolutions.io LLC,
26050 Equity Dr, Ste E - 1062, Daphne, AL 36526, United States. On this site specifically: there are no accounts, no
forms, no cookies and no analytics or tracking scripts; nothing is loaded from third parties; the web server may keep
standard request logs for operations and security; the JSON API serves published index values and derived metrics
only, never raw source data. Where the policy below describes services this site does not offer, that part does not
apply here. Questions: <a href="mailto:support@intentsolutions.io">support@intentsolutions.io</a>.</p>
</aside>"""

NOT_FOUND = """<section class="wrap prose"><h1>Not found</h1>
<p>That page does not exist. Try the <a href="/">index</a>, the <a href="/thesis">thesis</a> or the
<a href="/methodology">methodology and API</a>.</p></section>"""


def legal_page(root: Path, slug: str) -> tuple[str, str]:
    raw = (root / "content" / "legal" / f"{slug}.html").read_text()
    title = re.search(r"<h1>(.*?)</h1>", raw).group(1)
    raw = raw.replace(f"<h1>{title}</h1>", "", 1)
    return title, f'<article class="wrap prose legal"><h1>{title}</h1>{LEGAL_SCOPE}{raw}</article>'


# ---------------------------------------------------------------- build

def build(root: Path, out: Path, data_dir: Path | None = None, spread_dir: Path | None = None,
          public_start: str = PUBLIC_START) -> dict:
    data_dir = data_dir or root / "data"
    indices = {d: v for d, v in load_dated(data_dir / "indices").items() if d >= public_start}
    if not indices:
        raise PublishError(f"no index files on or after {public_start} in {data_dir / 'indices'}")
    spreads = {d: v for d, v in load_dated(spread_dir or data_dir / "spread").items() if d >= public_start}
    methodology = yaml.safe_load((data_dir / "fixtures" / "methodology.yaml").read_text())
    if not isinstance(methodology, dict):
        raise PublishError("methodology.yaml is not a mapping")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pub = root / "public"
    if pub.is_dir():
        shutil.copytree(pub, out, dirs_exist_ok=True)
    bar_src = root / "vendor" / "estate-bar"
    (out / "estate-bar").mkdir()
    shutil.copy2(bar_src / "estate-bar.css", out / "estate-bar" / "estate-bar.css")
    shutil.copytree(bar_src / "fonts", out / "estate-bar" / "fonts")

    clean = {d: clean_index(raw) for d, raw in indices.items()}
    dates = sorted(clean)
    latest = clean[dates[-1]]
    for d, body in clean.items():
        write_json(out / "v1" / "index" / f"{d}.json", body)
    write_json(out / "v1" / "index" / "latest.json", latest)
    write_json(out / "v1" / "indices.json", {
        "dates": list(reversed(dates)), "count": len(dates), "latest": dates[-1], "first": dates[0],
    })

    spread_latest = None
    if spreads:
        cs = {d: clean_spread(raw) for d, raw in spreads.items()}
        for d, body in cs.items():
            write_json(out / "v1" / "spread" / f"{d}.json", body)
        spread_latest = cs[max(cs)]
        write_json(out / "v1" / "spread" / "latest.json", spread_latest)
        write_json(out / "v1" / "spreads.json", {"dates": sorted(cs, reverse=True), "latest": max(cs)})

    write_json(out / "v1" / "methodology.json", methodology)

    desc = ("STCI, the Standardized Token Cost Index: a public benchmark price for AI tokens, like Brent for oil "
            "or the Baltic Dry Index for shipping. Daily index values, the neocloud spread, an open rulebook and a JSON API.")
    org = {"@type": "Organization", "name": "intentsolutions.io LLC", "url": "https://intentsolutions.io",
           "email": CONTACT}
    dataset_ld = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"STCI, the {NAME}", "alternateName": "STCI",
        "description": desc, "url": SITE + "/", "license": "https://opensource.org/licenses/MIT",
        "creator": org, "temporalCoverage": f"{dates[0]}/..", "isAccessibleForFree": True,
        "variableMeasured": "US dollars per million blended tokens",
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/v1/index/latest.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/v1/spread/latest.json"},
        ],
    }
    pages = {
        "index.html": page(path="/", title=f"STCI, the {NAME}: the benchmark price for AI tokens", description=desc,
                           body=landing(latest, spread_latest, methodology), jsonld=dataset_ld),
        "thesis.html": page(path="/thesis", title=f"Tokens need a benchmark price | STCI, the {NAME}",
                            description="Why AI tokens need a benchmark price that the sellers do not control, what one "
                                        "needs, and how far STCI has got.",
                            body=thesis_page(spread_latest),
                            jsonld={"@context": "https://schema.org", "@type": "Article",
                                    "headline": "Tokens need a benchmark price", "url": SITE + "/thesis",
                                    "author": {"@type": "Person", "name": "Jeremy Longshore"}, "publisher": org}),
        "methodology.html": page(path="/methodology", title=f"Methodology and API | STCI, the {NAME}",
                                 description="How STCI is computed, what is published, and the static JSON API.",
                                 body=methodology_page(methodology, latest)),
        "governance.html": page(path="/governance", title=f"Rulebook and governance | STCI, the {NAME}",
                                description="Who administers STCI, how the rulebook changes, and which IOSCO "
                                            "benchmark principles it meets and does not yet meet.",
                                body='<article class="wrap prose">'
                                     + (root / "content" / "governance" / "governance.html").read_text()
                                     + "</article>"),
        "404.html": page(path="/404", title=f"Not found | STCI, the {NAME}", description="Page not found.", body=NOT_FOUND),
    }
    for href, _ in LEGAL:
        slug = href.strip("/")
        title, body = legal_page(root, slug)
        pages[f"{slug}.html"] = page(path=href, title=f"{title} | STCI, the {NAME}",
                                     description=f"{title} for STCI, the {NAME}.", body=body)
    for name, text in pages.items():
        (out / name).write_text(text)
    (out / "docs.html").write_text(pages["methodology.html"])

    urls = ["/", "/thesis", "/methodology", "/governance"] + [h for h, _ in LEGAL]
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{dates[-1]}</lastmod></url>\n" for u in urls)
        + "</urlset>\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")

    if (out / "v1" / "observations").exists():
        raise PublishError("refusing: v1/observations must never be published")
    return {"latest": dates[-1], "dates": len(dates), "spread": spread_latest["date"] if spread_latest else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    ap.add_argument("--data-dir", type=Path, default=None, help="default: <repo>/data")
    ap.add_argument("--spread-dir", type=Path, default=None, help="default: <data-dir>/spread")
    a = ap.parse_args(argv)
    try:
        r = build(ROOT, a.out.resolve(), a.data_dir, a.spread_dir)
    except PublishError as exc:
        print(f"publish_static: {exc}", file=sys.stderr)
        return 1
    print(f"publish_static: {r['dates']} index dates, latest {r['latest']}, spread {r['spread']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
