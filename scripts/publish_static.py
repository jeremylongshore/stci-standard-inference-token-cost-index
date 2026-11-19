#!/usr/bin/env python3
"""Build the STCI static site and its static JSON API.

Reads committed data only:
  data/indices/<date>.json        daily index files
  data/spread/<date>.json         neocloud spread files (methodology 2.0.0+)
  data/fixtures/methodology.yaml  the current rulebook
  public/                         static assets (CSS, favicon)

Writes to --out (default dist/):
  index.html, thesis.html, methodology.html, privacy.html, 404.html,
  sitemap.xml, robots.txt, plus every file in public/
  v1/index/latest.json, v1/index/<date>.json, v1/indices.json,
  v1/spread/latest.json, v1/spread/<date>.json, v1/methodology.json

Licensing (ADR 014): only indices and derived metrics are published. Every
published JSON object is rebuilt from an explicit allow-list of keys, so a raw
observation or raw API field that appears in a data file is dropped, never
passed through. Nothing is read from data/observations or data/raw.

Dependencies: Python 3.11+ standard library and PyYAML.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://inferencepriceindex.com"
API_ALT = "https://stci.intentsolutions.io"
REPO = "https://github.com/jeremylongshore/stci-standard-inference-token-cost-index"
CONTACT = "jeremy@intentsolutions.io"
INDEX_ORDER = ["STCI-FRONTIER", "STCI-EFFICIENT", "STCI-OPEN", "STCI-ALL"]
INDEX_BLURB = {
    "STCI-FRONTIER": "Flagship models, one per lab",
    "STCI-EFFICIENT": "Cost-optimized models, one per lab",
    "STCI-OPEN": "Open-weight models sold by many providers",
    "STCI-ALL": "Every eligible listed model",
}

# Allow-lists. Anything not named here is not published.
INDEX_TOP_KEYS = ["date", "methodology_version", "computed_at", "verification_hash", "observation_count"]
INDEX_KEYS = ["input_rate", "output_rate", "blended_rate", "model_count", "dispersion",
              "models_included", "constituents_missing"]
SPREAD_TOP_KEYS = ["date", "methodology_version", "blend", "source"]
SPREAD_SUMMARY_KEYS = ["models_measured", "fetch_errors", "median_max_min_ratio",
                       "median_p75_p25_ratio", "widest", "most_endpoints"]
SPREAD_MODEL_KEYS = ["model_id", "endpoints", "providers", "min_blended", "p25_blended",
                     "median_blended", "p75_blended", "max_blended", "max_min_ratio",
                     "p75_p25_ratio", "quantization_mix", "cheapest"]
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
        models.append(c)
    out["models"] = models
    return out


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

NAV = [("/", "Index"), ("/thesis", "Thesis"), ("/methodology", "Methodology & API")]


def page(*, path: str, title: str, description: str, body: str, jsonld: dict | None = None) -> str:
    canonical = SITE + path
    bar = (ROOT / "vendor" / "estate-bar" / "fragments" / "estate-bar.stci.html").read_text().strip()
    nav = "".join(
        f'<li><a href="{href}"{" aria-current=\"page\"" if href == path else ""}>{label}</a></li>'
        for href, label in NAV
    )
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
<meta property="og:site_name" content="STCI: Standard Token Cost Index">
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
    <a class="logo" href="/">STCI<span class="logo-sub">Standard Token Cost Index</span></a>
    <nav aria-label="Primary"><ul class="nav">{nav}</ul></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p>STCI, the Standard Token Cost Index. Created by <a href="https://intentsolutions.io">intentsolutions.io</a>.
    Code MIT on <a href="{REPO}">GitHub</a>. Contact <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
    <p class="muted">Listed prices are informational, not an offer or financial advice. <a href="/privacy">Privacy</a>.</p>
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
        missing = body.get("constituents_missing")
        miss = ""
        if missing:
            miss = f'<p class="card-note">{len(missing)} constituent(s) missing today</p>'
        cards.append(f"""<div class="card card-{name.split('-')[1].lower()}">
  <h3>{e(name)}</h3>
  <p class="value num">{usd(body['blended_rate'])}<span class="unit"> per 1M tokens</span></p>
  <p class="card-sub">{e(INDEX_BLURB.get(name, ''))}. {body.get('model_count', '?')} models.</p>
  <p class="card-detail">input {usd(body['input_rate'])}, output {usd(body['output_rate'])}</p>
  {miss}
</div>""")
    return '<div class="cards">' + "".join(cards) + "</div>"


def spread_lead(spread: dict | None) -> str:
    if not spread:
        return ('<p>The spread measurement publishes with methodology 2.0.0. '
                'No spread file is in the published data yet.</p>')
    s = spread["summary"]
    most = s.get("most_endpoints") or {}
    row = next((m for m in spread["models"] if m.get("model_id") == most.get("model_id")), None)
    if not row:
        return ""
    ch = row.get("cheapest") or {}
    return f"""<p class="lead-stat">One open-weight model, <code>{e(row['model_id'])}</code>, is sold through
<strong>{row['endpoints']} endpoints</strong> by <strong>{row['providers']} providers</strong>, from
<strong>{usd(row['min_blended'])}</strong> to <strong>{usd(row['max_blended'])}</strong> per million blended tokens:
a {ratio(row['max_min_ratio'])} spread. The cheapest endpoint serves it at <strong>{e(ch.get('quantization', 'unknown'))}</strong>.</p>"""


def spread_table(spread: dict | None, limit: int = 12) -> str:
    if not spread:
        return ""
    rows = sorted(spread["models"], key=lambda m: m.get("max_min_ratio", 0), reverse=True)[:limit]
    trs = []
    for m in rows:
        ch = m.get("cheapest") or {}
        trs.append(
            f"<tr><th scope=\"row\"><code>{e(m['model_id'])}</code></th>"
            f"<td>{m['endpoints']}</td><td>{m['providers']}</td>"
            f"<td>{usd(m['min_blended'])}</td><td>{usd(m['median_blended'])}</td><td>{usd(m['max_blended'])}</td>"
            f"<td>{ratio(m['max_min_ratio'])}</td><td>{e(ch.get('quantization', 'unknown'))}</td></tr>"
        )
    s = spread["summary"]
    cap = (f"Widest {len(rows)} of {s.get('models_measured', len(spread['models']))} open-weight models measured on "
           f"{e(long_date(spread['date']))}. Blended $ per 1M tokens at {spread.get('blend', {}).get('output_ratio', 3):g}:1 "
           f"output:input. Median spread across all models: {ratio(s['median_max_min_ratio'])} (max/min), "
           f"{ratio(s['median_p75_p25_ratio'])} (p75/p25)." if "median_p75_p25_ratio" in s else "")
    return f"""<div class="table-scroll" role="region" aria-label="Neocloud spread table" tabindex="0">
<table>
<caption>{cap}</caption>
<thead><tr><th scope="col">Model</th><th scope="col">Endpoints</th><th scope="col">Providers</th>
<th scope="col">Cheapest</th><th scope="col">Median</th><th scope="col">Dearest</th>
<th scope="col">Max / min</th><th scope="col">Cheapest precision</th></tr></thead>
<tbody>{''.join(trs)}</tbody>
</table></div>"""


def coverage(dates: list[str]) -> str:
    runs = series_runs(dates)
    parts = []
    for i, (a, b) in enumerate(runs):
        n = (date.fromisoformat(b) - date.fromisoformat(a)).days + 1
        parts.append(f"<li><strong>{e(a)} to {e(b)}</strong>: published, {n} day{'s' if n != 1 else ''}.</li>"
                     if a != b else f"<li><strong>{e(a)}</strong>: published.</li>")
        if i + 1 < len(runs):
            gap_a = date.fromordinal(date.fromisoformat(b).toordinal() + 1).isoformat()
            gap_b = date.fromordinal(date.fromisoformat(runs[i + 1][0]).toordinal() - 1).isoformat()
            parts.append(f"<li class=\"gap\"><strong>{gap_a} to {gap_b}</strong>: not collected. "
                         "The pipeline was switched off; nothing in this range is published or back-filled.</li>")
    return "<ul class=\"coverage\">" + "".join(parts) + "</ul>"


LADDER = """<ol class="ladder">
<li><span class="rung now">Now</span> <strong>Listed prices.</strong> Every separately priced model on one aggregator
(OpenRouter), normalized to $ per million tokens, combined into four indices under a public rulebook. Each day’s value
carries a verification hash that anyone holding the inputs can reproduce.</li>
<li><span class="rung now">Now</span> <strong>Grades and spread.</strong> For open-weight models, the price of every
provider endpoint selling the same model, and the precision each one serves.</li>
<li><span class="rung next">Next</span> <strong>A reported-price panel.</strong> Gateways and large buyers report what
they actually paid, anonymized and volume-weighted. Listed prices cannot show discounts, credits or subsidies; a panel can.</li>
<li><span class="rung later">Later</span> <strong>Contracts that settle against the index.</strong> Forwards that let a
buyer fix next year's token cost. This needs the panel and independent administration first.</li>
</ol>"""


def landing(latest: dict, spread: dict | None, dates: list[str], methodology: dict) -> str:
    d = latest["date"]
    return f"""<section class="hero wrap">
  <h1>The benchmark price for AI tokens.</h1>
  <p class="lead">Oil has Brent. Shipping has the Baltic Dry Index. Tokens have no price the sellers don’t set.</p>
  <p class="hero-links"><a class="btn" href="/thesis">Read the thesis</a> <a class="btn btn-ghost" href="#today">See today’s numbers</a></p>
</section>

<section class="wrap section" aria-labelledby="why">
  <h2 id="why">1. Tokens need a benchmark price</h2>
  <p>Every commodity market that works has a reference price that no single seller sets. Brent and WTI price crude.
  The Baltic Dry Index prices bulk shipping capacity. Contracts, budgets and hedges are written against those numbers.</p>
  <p>Tokens have none. Each provider sets its own price, changes it without notice, and more and more tokens are
  subsidized or resold by intermediaries. A buyer cannot tell a fair price from a subsidy, budget a year ahead, or hedge.</p>
</section>

<section class="wrap section" aria-labelledby="pillars">
  <h2 id="pillars">2. What a benchmark needs</h2>
  <div class="pillars">
    <div class="pillar"><h3>Routes</h3><p>Standard units everyone prices the same way. Model tiers today; the cost of a
    defined task later.</p></div>
    <div class="pillar"><h3>A panel</h3><p>Gateways and large buyers reporting what they actually paid, anonymized and
    weighted by volume.</p></div>
    <div class="pillar"><h3>A public rulebook</h3><p>How every value is computed, written down before it is used.</p></div>
    <div class="pillar"><h3>An audit trail</h3><p>Values anyone can reproduce, and administration independent of the sellers.</p></div>
  </div>
</section>

<section class="wrap section" aria-labelledby="grades">
  <h2 id="grades">3. Not every token is the same token</h2>
  <p>Crude has grades: light, heavy, sweet, sour. Tokens have grades too: serving precision, context length, uptime.
  The neocloud spread is the first measurement of that.</p>
  {spread_lead(spread)}
</section>

<section class="wrap section" aria-labelledby="ladder">
  <h2 id="ladder">4. Where STCI is today</h2>
  {LADDER}
</section>

<section class="wrap section" id="today" aria-labelledby="today-h">
  <h2 id="today-h">5. Today’s numbers</h2>
  <p>Blended $ per million tokens at {methodology.get('output_ratio', 3):g} output tokens per input token, for
  <strong>{e(long_date(d))}</strong> (methodology {e(latest.get('methodology_version', '?'))}).</p>
  {index_cards(latest)}
  <h3 class="sub">The neocloud spread</h3>
  {spread_table(spread)}
  <p class="muted small">Source: listed prices on OpenRouter, the model catalog and each model’s provider endpoint list.
  Listed prices, not prices paid. JSON: <a href="/v1/index/latest.json">/v1/index/latest.json</a>,
  <a href="/v1/spread/latest.json">/v1/spread/latest.json</a>.</p>
</section>

<section class="wrap section" aria-labelledby="ask">
  <h2 id="ask">6. Report what you pay</h2>
  <p>The next rung needs prices paid, not prices listed. If you run an LLM gateway, or your company buys tokens at
  volume, you can make the index real by reporting what you pay, anonymized and aggregated before anything is published.</p>
  <p><a class="btn" href="mailto:{CONTACT}?subject=STCI%20panel">Report a price</a>
  <a class="btn btn-ghost" href="{REPO}">The code and data on GitHub</a></p>
</section>

<section class="wrap section" aria-labelledby="repro">
  <h2 id="repro">7. Methodology and reproducibility</h2>
  <p>The rulebook is public. Today’s value carries verification hash <code>{e(latest.get('verification_hash', ''))}</code>:
  SHA-256 over the sorted eligible observations, the methodology version and the date. Anyone holding the inputs can
  recompute it; the observations are available on request.</p>
  <p>Series coverage, labeled as it is:</p>
  {coverage(dates)}
  <p>Values across the break are not comparable: the baskets changed with methodology 2.0.0.
  <a href="/methodology">Methodology and API</a>.</p>
</section>"""


def thesis_page(latest: dict, spread: dict | None) -> str:
    return f"""<article class="wrap prose">
<h1>Tokens need a benchmark price</h1>
<p class="lead">AI tokens are turning into a commodity. Commodities that trade well share one piece of infrastructure:
a reference price that the sellers do not control. Tokens do not have one yet. This is the case for building it, and
an honest account of how far STCI has got.</p>

<h2>1. A commodity without a price</h2>
<p>A million tokens from a capable model is becoming a unit of input that businesses buy the way they buy fuel or
freight: in volume, from several suppliers, with a budget behind it. Guillermo Rauch put the moment as "more like an
oil rush than a gold rush." Oil is a useful comparison because oil has something tokens lack.</p>
<p>Crude trades against Brent and WTI. Dry bulk shipping trades against the Baltic Dry Index, which the Baltic Exchange
compiles each day from a panel of shipbrokers reporting what routes actually cost. No refiner and no shipowner sets
those numbers. Supply contracts, budgets, loans and hedges are written against them.</p>
<p>Token prices work differently. Each provider sets its own price and changes it when it likes. A growing share of
tokens reach buyers through intermediaries, gateways and resellers, some of whom subsidize the price to win volume.
From the outside, nobody can tell a fair price from a subsidy. Nobody can budget a year ahead with confidence, and
nobody can hedge, because there is nothing neutral to settle against.</p>

<h2>2. What a benchmark needs</h2>
<p>The working examples share four parts.</p>
<ul>
<li><strong>Routes.</strong> The Baltic index is built from named routes and vessel sizes, so everyone prices the
same thing. For tokens the first routes are model tiers: frontier, efficient, open-weight. Later routes are tasks:
the cost to complete a defined unit of work, which is what a buyer actually cares about.</li>
<li><strong>A panel.</strong> Credibility comes from the people who pay. Gateways and large consumers report the
effective price they paid per million tokens, anonymized, and the index weights them by volume so a few odd trades
cannot move it.</li>
<li><strong>A public rulebook.</strong> How each value is calculated, which data is eligible, how baskets change and
when, all written down before it is applied.</li>
<li><strong>An audit trail and independent administration.</strong> Values that can be recomputed by someone else,
regular checks that the rulebook was followed, and an administrator that is not one of the sellers.</li>
</ul>

<h2>3. Grades: not every token is the same token</h2>
<p>Brent is a grade of crude, not crude in general. A barrel of heavy sour is worth less than a barrel of light sweet,
and the market prices the difference. Tokens have grades as well: the numerical precision the model is served at,
the context it can use, the uptime and latency behind it. Two tokens from "the same model" are not necessarily the
same product.</p>
<p>The neocloud spread is STCI's first measurement of grade. For each open-weight model it collects the price of every
provider endpoint selling it and the precision each serves.</p>
{spread_lead(spread)}
<p>A benchmark that ignored this would average fp4 tokens with full-precision tokens and call the result one price.</p>

<h2>4. Where STCI is on that ladder</h2>
{LADDER}
<h3>Where it came from</h3>
<p>I started STCI on January 1, 2026 and built the first version in a week: v0.1.0 on January 3 through v0.5.0 on
January 8, with the collector, the indexer, the API and the site. It ran every day until March 6. Then I got pulled
onto other work and switched the pipeline off, which is why the series has a gap. It came back on November 19, 2026
under methodology 2.0.0. The gap stays a gap: nothing in it is back-filled. <em>Jeremy Longshore</em></p>
<p>What STCI is not, yet: it does not see prices paid, it uses a single source for listed prices, it weights models
equally, and its 3:1 output-to-input blend is a stated assumption, not a measurement. Those limits are in the
<a href="/methodology">methodology</a>, and the panel is the planned remedy for most of them.</p>

<h2>5. The evidence</h2>
<p>Today’s four index values and the full spread table are on the <a href="/#today">front page</a>, and every number is
in the <a href="/methodology#api">JSON API</a>.</p>

<h2>6. Who it is for</h2>
<p>Gateways and brokers, who see prices paid every day and would benefit most from a neutral reference to quote
against. Enterprises that buy tokens at volume and want to know whether their price is fair. Finance teams that need
to budget a year of inference. If that is you, <a href="mailto:{CONTACT}?subject=STCI%20panel">report what you pay</a>.</p>
</article>"""


def methodology_page(methodology: dict, latest: dict) -> str:
    rows = []
    for name, spec in (methodology.get("indices") or {}).items():
        members = spec.get("models") or []
        if members and isinstance(members[0], dict):
            members = [m.get("id") or m.get("model_id") or "" for m in members]
        basket = (", ".join(f"<code>{e(m)}</code>" for m in members) if members
                  else e(spec.get("rule") or spec.get("description") or "rule-based"))
        rows.append(f"<tr><th scope=\"row\">{e(name)}</th><td>{e(spec.get('description', ''))}</td>"
                    f"<td>{e(spec.get('weighting', methodology.get('weighting', {}).get('type', 'equal')))}</td>"
                    f"<td>{basket}</td></tr>")
    v = e(methodology.get("methodology_version", "?"))
    return f"""<article class="wrap prose">
<h1>The rulebook</h1>
<p>Current methodology: <strong>{v}</strong>. The full text and the machine-readable rules are in the
<a href="{REPO}/tree/main/000-docs">repository</a>; the rules as published here are at
<a href="/v1/methodology.json">/v1/methodology.json</a>.</p>
<ul>
<li><strong>Unit.</strong> US dollars per million tokens. The blended rate assumes
{methodology.get('output_ratio', 3):g} output tokens per input token: (input + {methodology.get('output_ratio', 3):g} &times; output) / {methodology.get('output_ratio', 3) + 1:g}.</li>
<li><strong>Source.</strong> Listed prices from OpenRouter: the model catalog, and each open-weight model's provider endpoint list.</li>
<li><strong>Eligibility.</strong> Only separately priced models count. Aliases, free listings, batch variants and routers are excluded by rule.</li>
<li><strong>Weighting.</strong> Equal. Volume weighting needs reported volumes, which needs the panel.</li>
<li><strong>Publication.</strong> Indices and derived spread metrics only. Raw source responses and individual observations are not published.</li>
<li><strong>Verification.</strong> Each day’s value carries a hash over the sorted eligible observations, the methodology
version and the date. Today: <code>{e(latest.get('verification_hash', ''))}</code>.</li>
</ul>
<h2>Baskets</h2>
<div class="table-scroll" role="region" aria-label="Index baskets" tabindex="0">
<table><thead><tr><th scope="col">Index</th><th scope="col">What</th><th scope="col">Weighting</th><th scope="col">Constituents</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>

<h2 id="api">JSON API</h2>
<p>Static JSON files, no key, readable cross-origin (<code>Access-Control-Allow-Origin: *</code>). The same paths answer on
<code>{SITE}</code> and <code>{API_ALT}</code>, with or without the <code>.json</code> extension.</p>
<div class="table-scroll" role="region" aria-label="API endpoints" tabindex="0">
<table><thead><tr><th scope="col">Path</th><th scope="col">Returns</th></tr></thead><tbody>
<tr><th scope="row"><a href="/v1/index/latest.json"><code>/v1/index/latest.json</code></a></th><td>The latest daily index</td></tr>
<tr><th scope="row"><code>/v1/index/&lt;YYYY-MM-DD&gt;.json</code></th><td>The index for one date</td></tr>
<tr><th scope="row"><a href="/v1/indices.json"><code>/v1/indices.json</code></a></th><td>Every published date and the coverage gaps</td></tr>
<tr><th scope="row"><a href="/v1/spread/latest.json"><code>/v1/spread/latest.json</code></a></th><td>The latest neocloud spread</td></tr>
<tr><th scope="row"><code>/v1/spread/&lt;YYYY-MM-DD&gt;.json</code></th><td>The spread for one date</td></tr>
<tr><th scope="row"><a href="/v1/methodology.json"><code>/v1/methodology.json</code></a></th><td>The current rulebook</td></tr>
</tbody></table></div>
<pre><code>curl -s {SITE}/v1/index/latest.json</code></pre>
</article>"""


PRIVACY = """<article class="wrap prose">
<h1>Privacy</h1>
<p>This site sets no cookies, runs no analytics or tracking scripts, loads nothing from third-party servers, and has
no forms. The web server may keep standard request logs (address, time, path) for operations and security.</p>
<p>If you email us, we use your message only to reply. Questions: <a href="mailto:jeremy@intentsolutions.io">jeremy@intentsolutions.io</a>.</p>
</article>"""

NOT_FOUND = """<section class="wrap prose"><h1>Not found</h1>
<p>That page does not exist. Try the <a href="/">index</a>, the <a href="/thesis">thesis</a> or the
<a href="/methodology">methodology and API</a>.</p></section>"""


# ---------------------------------------------------------------- build

def build(root: Path, out: Path, data_dir: Path | None = None, spread_dir: Path | None = None) -> dict:
    data_dir = data_dir or root / "data"
    indices = load_dated(data_dir / "indices")
    if not indices:
        raise PublishError(f"no index files in {data_dir / 'indices'}")
    spreads = load_dated(spread_dir or data_dir / "spread")
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

    runs = series_runs(dates)
    gaps = []
    for (_, b), (a2, _) in zip(runs, runs[1:]):
        gaps.append({"from": date.fromordinal(date.fromisoformat(b).toordinal() + 1).isoformat(),
                     "to": date.fromordinal(date.fromisoformat(a2).toordinal() - 1).isoformat(),
                     "status": "not collected"})
    write_json(out / "v1" / "indices.json", {
        "dates": list(reversed(dates)), "count": len(dates), "latest": dates[-1], "first": dates[0],
        "runs": [{"from": a, "to": b} for a, b in runs], "gaps": gaps,
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

    desc = ("STCI is a public benchmark price for AI tokens, like Brent for oil or the Baltic Dry Index for "
            "shipping: daily index values, the neocloud spread, an open rulebook and a JSON API.")
    dataset_ld = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "STCI: Standard Token Cost Index",
        "description": desc, "url": SITE + "/", "license": "https://opensource.org/licenses/MIT",
        "creator": {"@type": "Organization", "name": "intentsolutions.io", "url": "https://intentsolutions.io"},
        "temporalCoverage": f"{dates[0]}/{dates[-1]}", "isAccessibleForFree": True,
        "variableMeasured": "US dollars per million blended tokens",
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/v1/index/latest.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/v1/spread/latest.json"},
        ],
    }
    pages = {
        "index.html": page(path="/", title="STCI: the benchmark price for AI tokens", description=desc,
                           body=landing(latest, spread_latest, dates, methodology), jsonld=dataset_ld),
        "thesis.html": page(path="/thesis", title="Tokens need a benchmark price | STCI",
                            description="Why AI tokens need a benchmark price that the sellers do not control, what one "
                                        "needs, and how far STCI has got.",
                            body=thesis_page(latest, spread_latest),
                            jsonld={"@context": "https://schema.org", "@type": "Article",
                                    "headline": "Tokens need a benchmark price", "url": SITE + "/thesis",
                                    "author": {"@type": "Person", "name": "Jeremy Longshore"},
                                    "publisher": {"@type": "Organization", "name": "intentsolutions.io"}}),
        "methodology.html": page(path="/methodology", title="Methodology and API | STCI",
                                 description="How STCI is computed, what is published, and the static JSON API.",
                                 body=methodology_page(methodology, latest)),
        "privacy.html": page(path="/privacy", title="Privacy | STCI", description="STCI privacy note.", body=PRIVACY),
        "404.html": page(path="/404", title="Not found | STCI", description="Page not found.", body=NOT_FOUND),
    }
    for name, text in pages.items():
        (out / name).write_text(text)
    # The old API docs page name keeps working.
    (out / "docs.html").write_text(pages["methodology.html"])

    urls = ["/", "/thesis", "/methodology"]
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
