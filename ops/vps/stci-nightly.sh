#!/usr/bin/env bash
# stci-nightly.sh — the nightly STCI data refresh on the intentsolutions VPS.
#
# DEPLOYED TO: /usr/local/sbin/stci-nightly.sh (root:root 0755) by ops/vps/install.sh.
# This file in the repository is the source of truth; the VPS copy is byte-identical.
#
# Runs as the `intentsolutions` user (never root) from a job-owned clone of
# origin/main, once a day at 06:30 UTC (stci-nightly.timer):
#
#   git fetch + reset --hard origin/main        (the job owns this clone; the
#                                               hard reset is sanctioned here only)
#   collector  -> data/observations/D.jsonl     (PRIVATE, git-ignored, never pushed)
#   spread     -> data/spread/D.json            (published)
#   indexer    -> data/indices/D.json           (published)
#   verify     -> 4 indices, rates > 0, constituents_missing checked
#   commit ONLY the two published files, push to main
#
# The push to main triggers the "Deploy site to VPS" workflow, which rebuilds
# the static JSON and ships it to /srv/stci. This script never touches /srv.
#
# Outcome contract (the estate's two-marker liveness rule):
#   .beat  written on every start
#   .ok    written only when the day's files are on origin/main (freshly pushed
#          or already there) — a run that exits 0 without that is NOT success
# Failure: one high-severity sys-automation event through notify.sh, exit 1.
# Success: an audit-only (low) notify.sh event carrying the four blended rates.
#
# Overrides (for re-runs and drills; see 000-docs/021-OD-RUNB-nightly-refresh.md):
#   STCI_NIGHTLY_DATE=YYYY-MM-DD   compute that date instead of today (UTC)
#   STCI_NIGHTLY_FORCE=1           recompute even if the date is already published
#   HTTPS_PROXY=http://127.0.0.1:9 planted-fault drill: OpenRouter unreachable

set -uo pipefail

# systemd and cron both start with a minimal PATH; make the script self-sufficient.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

JOB="stci-nightly"
STATE="${STCI_NIGHTLY_STATE:-/var/lib/intentsolutions/stci-nightly}"
REPO="$STATE/repo"
VENV="$STATE/venv"
LOGDIR="$STATE/logs"
LIVE="${STCI_NIGHTLY_LIVENESS_DIR:-/var/lib/intentsolutions/liveness}"
NOTIFY="${STCI_NIGHTLY_NOTIFY:-/usr/local/bin/notify.sh}"
REMOTE="${STCI_NIGHTLY_REMOTE:-git@github-stci-nightly:jeremylongshore/stci-standard-inference-token-cost-index.git}"
SSH_KEY="${STCI_NIGHTLY_SSH_KEY:-$HOME/.ssh/stci_nightly_ed25519}"
DATE="${STCI_NIGHTLY_DATE:-$(date -u +%F)}"
FORCE="${STCI_NIGHTLY_FORCE:-0}"
AUTHOR_NAME="STCI nightly"
AUTHOR_EMAIL="support@intentsolutions.io"

INDEX_REL="data/indices/$DATE.json"
SPREAD_REL="data/spread/$DATE.json"

mkdir -p "$LOGDIR" || { echo "cannot create $LOGDIR" >&2; exit 1; }
LOG="$LOGDIR/$DATE.log"
exec > >(tee -a "$LOG") 2>&1

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

notify() { # <title> <body> <priority>
  # The shim's default audit log and the alert floor's default state dir are
  # root-owned on the VPS; this job keeps both under its own state directory
  # so every event (audit-only ones included) leaves a record it can write.
  if [ -x "$NOTIFY" ]; then
    local rc=0
    NOTIFY_SHIM_LOG="$LOGDIR/notify-shim.log" AF_STATE_DIR="$STATE/af" \
      "$NOTIFY" "$1" "$2" "$JOB" "$3" || rc=$?
    log "notify.sh rc=$rc ($3): $1 — $(tail -1 "$LOGDIR/notify-shim.log" 2>/dev/null | sed 's/.*| //')"
  else
    log "notify.sh absent at $NOTIFY — event not dispatched: $1 — $2"
  fi
}

FAILURE_REASON="startup"
SUCCEEDED=0
on_exit() {
  local rc=$?
  if [ "$SUCCEEDED" -eq 1 ] && [ "$rc" -eq 0 ]; then
    date -u +%FT%TZ > "$LIVE/$JOB.ok" 2>/dev/null || log "warning: could not write $LIVE/$JOB.ok"
  else
    [ "$rc" -eq 0 ] && rc=1
    log "FAILED: $FAILURE_REASON"
    notify "STCI nightly FAILED for $DATE" "$FAILURE_REASON. Log: $LOG on the VPS. Re-run: STCI_NIGHTLY_DATE=$DATE /usr/local/sbin/stci-nightly.sh" high
  fi
  trap - EXIT
  exit "$rc"
}
trap on_exit EXIT
fail() { FAILURE_REASON="$*"; exit 1; }

date -u +%FT%TZ > "$LIVE/$JOB.beat" 2>/dev/null || log "warning: could not write $LIVE/$JOB.beat"

log "=== stci-nightly start · date=$DATE force=$FORCE user=$(id -un) ==="
[ "$(id -un)" != "root" ] || fail "refusing to run as root; this job runs as intentsolutions"
[ -r "$SSH_KEY" ] || fail "deploy key missing or unreadable: $SSH_KEY"

# One run at a time (Persistent=true can queue a catch-up behind a manual run).
exec 9>"$STATE/run.lock"
flock -n 9 || fail "another stci-nightly run holds $STATE/run.lock"

export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes"

# ── 1. The job-owned clone, pinned to origin/main ──────────────────────────────
if [ ! -d "$REPO/.git" ]; then
  log "cloning $REMOTE -> $REPO"
  git clone --quiet "$REMOTE" "$REPO" || fail "git clone failed"
fi
cd "$REPO" || fail "cannot cd $REPO"
git config user.name "$AUTHOR_NAME"
git config user.email "$AUTHOR_EMAIL"
git remote set-url origin "$REMOTE"
git fetch --quiet --prune origin || fail "git fetch origin failed"
git checkout --quiet -B main origin/main || fail "git checkout main failed"
git reset --hard --quiet origin/main || fail "git reset --hard origin/main failed"
git clean -fdq || fail "git clean failed"
HEAD_BEFORE="$(git rev-parse HEAD)"
log "clone at origin/main $HEAD_BEFORE"

# ── 2. Skip when the date is already published (no empty or duplicate commits) ─
if [ "$FORCE" != "1" ] && git cat-file -e "origin/main:$INDEX_REL" 2>/dev/null \
   && git cat-file -e "origin/main:$SPREAD_REL" 2>/dev/null; then
  log "$INDEX_REL and $SPREAD_REL already on origin/main — nothing to do (STCI_NIGHTLY_FORCE=1 recomputes)"
  notify "STCI nightly: $DATE already published" "both files present on origin/main at $HEAD_BEFORE; skipped" low
  SUCCEEDED=1
  exit 0
fi

# ── 3. Python environment (venv beside the clone; deps re-installed only on change)
PY="$VENV/bin/python"
if [ ! -x "$PY" ]; then
  log "creating venv $VENV"
  python3 -m venv "$VENV" || fail "python3 -m venv failed"
fi
REQ_HASH="$(sha256sum requirements.txt | cut -c1-64)"
if [ "$(cat "$STATE/requirements.sha256" 2>/dev/null || true)" != "$REQ_HASH" ]; then
  log "installing requirements (hash $REQ_HASH)"
  "$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt || fail "pip install -r requirements.txt failed"
  printf '%s\n' "$REQ_HASH" > "$STATE/requirements.sha256"
fi

# ── 4. The three pipeline steps ───────────────────────────────────────────────
log "step 1/3 collector"
"$PY" -m services.collector.pipeline --date "$DATE" || fail "collector failed for $DATE (OpenRouter unreachable or no valid observations)"
log "step 2/3 spread"
"$PY" -m services.collector.spread --date "$DATE" || fail "spread failed for $DATE"
log "step 3/3 indexer"
"$PY" -m services.indexer.pipeline --date "$DATE" || fail "indexer failed for $DATE"

# ── 5. Verify the output before anything is committed ─────────────────────────
[ -s "$INDEX_REL" ] || fail "$INDEX_REL missing or empty after the indexer ran"
[ -s "$SPREAD_REL" ] || fail "$SPREAD_REL missing or empty after the spread step ran"
VERIFY="$("$PY" - "$INDEX_REL" "$SPREAD_REL" "$DATE" <<'PY'
import json, sys
index_path, spread_path, day = sys.argv[1:4]
d = json.load(open(index_path))
s = json.load(open(spread_path))
problems = []
if d.get("date") != day:
    problems.append(f"index date {d.get('date')!r} != {day}")
if s.get("date") != day:
    problems.append(f"spread date {s.get('date')!r} != {day}")
idx = d.get("indices") or {}
expected = ["STCI-ALL", "STCI-FRONTIER", "STCI-EFFICIENT", "STCI-OPEN"]
missing = [n for n in expected if n not in idx]
if missing or len(idx) != 4:
    problems.append(f"expected exactly 4 indices {expected}, got {sorted(idx)}")
for name, v in idx.items():
    if not isinstance(v.get("blended_rate"), (int, float)) or v["blended_rate"] <= 0:
        problems.append(f"{name} blended_rate not > 0: {v.get('blended_rate')!r}")
    if not v.get("model_count"):
        problems.append(f"{name} model_count is 0")
if not d.get("verification_hash"):
    problems.append("verification_hash missing")
warnings = []
for name in ("STCI-FRONTIER", "STCI-EFFICIENT"):
    cm = (idx.get(name) or {}).get("constituents_missing") or []
    if cm:
        warnings.append(f"{name} constituents_missing={cm}")
rates = " ".join(f"{n}={idx[n]['blended_rate']:.2f}" for n in expected if n in idx)
counts = " ".join(f"{n}:{idx[n].get('model_count')}" for n in expected if n in idx)
print("PROBLEMS=" + json.dumps(problems))
print("WARNINGS=" + json.dumps(warnings))
print(f"RATES={rates}")
print(f"COUNTS={counts}")
print(f"HASH={d.get('verification_hash')}")
print(f"OBS={d.get('observation_count')}")
print(f"SPREAD_MODELS={len(s.get('models') or [])}")
PY
)" || fail "verification script crashed"
printf '%s\n' "$VERIFY"
PROBLEMS="$(sed -n 's/^PROBLEMS=//p' <<<"$VERIFY")"
WARNINGS="$(sed -n 's/^WARNINGS=//p' <<<"$VERIFY")"
RATES="$(sed -n 's/^RATES=//p' <<<"$VERIFY")"
COUNTS="$(sed -n 's/^COUNTS=//p' <<<"$VERIFY")"
HASH="$(sed -n 's/^HASH=//p' <<<"$VERIFY")"
OBS="$(sed -n 's/^OBS=//p' <<<"$VERIFY")"
SPREAD_MODELS="$(sed -n 's/^SPREAD_MODELS=//p' <<<"$VERIFY")"
[ "$PROBLEMS" = "[]" ] || fail "index verification failed: $PROBLEMS"
if [ "$WARNINGS" != "[]" ]; then
  log "WARNING: $WARNINGS"
  notify "STCI nightly: constituents missing on $DATE" "$WARNINGS — the index still published; review the basket (000-docs/020)" high
fi

# ── 6. Commit guard: nothing but the two published files may be dirty ─────────
STATUS="$(git status --porcelain --untracked-files=all)"
UNEXPECTED="$(/usr/bin/grep -vE "^(\?\?| M|M |A ) ?(data/indices/$DATE\.json|data/spread/$DATE\.json)$" <<<"$STATUS" | sed '/^$/d' || true)"
[ -z "$UNEXPECTED" ] || fail "refusing to commit: unexpected paths in git status: $(tr '\n' ';' <<<"$UNEXPECTED")"
git add -- "$INDEX_REL" "$SPREAD_REL" || fail "git add failed"
if git diff --cached --quiet; then
  log "recomputed $DATE: no diff against origin/main — nothing to commit"
  notify "STCI nightly: $DATE recomputed, no diff" "rates $RATES; hash $HASH; identical to origin/main $HEAD_BEFORE" low
  SUCCEEDED=1
  exit 0
fi

# ── 7. Commit only those two paths and push to main ───────────────────────────
MSG="data(index): publish $DATE

Nightly refresh on the intentsolutions VPS (stci-nightly.timer).
Indices (USD per 1M blended tokens): $RATES
Constituents: $COUNTS · observations: $OBS · spread models: $SPREAD_MODELS
Verification hash: $HASH
Published files: $INDEX_REL, $SPREAD_REL (observations stay private, ADR 014).

- Jeremy Longshore
intentsolutions.io"
GIT_AUTHOR_NAME="$AUTHOR_NAME" GIT_AUTHOR_EMAIL="$AUTHOR_EMAIL" \
GIT_COMMITTER_NAME="$AUTHOR_NAME" GIT_COMMITTER_EMAIL="$AUTHOR_EMAIL" \
  git commit --quiet -m "$MSG" || fail "git commit failed"
COMMITTED="$(git rev-parse HEAD)"
# The commit must contain exactly the two files; anything else is a bug above.
CHANGED="$(git diff-tree --no-commit-id --name-only -r "$COMMITTED" | sort | tr '\n' ' ')"
[ "$CHANGED" = "$INDEX_REL $SPREAD_REL " ] || fail "commit $COMMITTED touches unexpected paths: $CHANGED"
git push --quiet origin HEAD:main || fail "git push origin main rejected (commit $COMMITTED kept locally in $REPO)"
log "pushed $COMMITTED to main: $RATES hash=$HASH"
notify "STCI nightly: published $DATE" "$RATES · hash $HASH · commit ${COMMITTED:0:12} · site deploy follows on push" low
SUCCEEDED=1
exit 0
