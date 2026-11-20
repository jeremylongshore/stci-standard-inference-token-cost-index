# Nightly refresh runbook

**Status:** live on the `intentsolutions` VPS since 2026-11-19. Source of truth for every
file named here is `ops/vps/` in this repository; the VPS copies are deployed copies and
must stay byte-identical (`/usr/local/sbin/stci-nightly.sh.provenance` records the hashes).

## What runs

| Piece | Where | Notes |
| --- | --- | --- |
| `stci-nightly.timer` | `/etc/systemd/system/` | `OnCalendar=*-*-* 06:30:00 UTC`, `RandomizedDelaySec=300`, `Persistent=true` |
| `stci-nightly.service` | `/etc/systemd/system/` | oneshot, `User=intentsolutions`, `OnFailure=notify-failure@%n.service` |
| `stci-nightly.sh` | `/usr/local/sbin/` | the job; root-owned 0755, runs as `intentsolutions` |
| job clone | `/var/lib/intentsolutions/stci-nightly/repo` | job-owned clone of `origin/main`; hard-reset every run |
| venv | `/var/lib/intentsolutions/stci-nightly/venv` | deps reinstalled only when `requirements.txt` changes |
| logs | `/var/lib/intentsolutions/stci-nightly/logs/<date>.log` | one file per computed date, appended on re-runs |
| liveness | `/var/lib/intentsolutions/liveness/stci-nightly.{beat,ok}` | `.beat` every start, `.ok` only on a verified outcome |
| deploy key | `/home/intentsolutions/.ssh/stci_nightly_ed25519` | GitHub deploy key `stci-nightly@intentsolutions-vps`, read-write, this repo only |

Each run: `git fetch && git reset --hard origin/main` (sanctioned only on this job-owned clone)
-> collector -> spread -> indexer for today's UTC date -> verify `data/indices/<date>.json`
(exactly four indices, every `blended_rate > 0`, `constituents_missing` on FRONTIER and
EFFICIENT reported as a warning event, never a failure) -> commit **only**
`data/indices/<date>.json` and `data/spread/<date>.json` as `STCI nightly <support@intentsolutions.io>`
with subject `data(index): publish <date>` -> push to `main`. The push triggers the
"Deploy site to VPS" workflow, which rebuilds the static JSON and ships it to `/srv/stci`.
The nightly job itself never touches `/srv/stci`.

Guards: the commit is refused if `git status --porcelain` shows anything outside the two
published paths; a recompute that produces no diff makes no commit; a date already on
`origin/main` is skipped (audit event only). Raw observations (`data/observations/*.jsonl`)
are git-ignored and stay on the VPS (ADR 014).

Alerts go through `/usr/local/bin/notify.sh` (topic `stci-nightly` -> the private Discord channel `#sys-alerts`; Buzz is retired):
a failure is a **high** event and delivers; a success or skip is **low** and is audit-logged
only (`/var/log/intentsolutions/notify-shim.log`). A missing-constituent warning is high.

## Checking on it

```bash
ssh intentsolutions
systemctl list-timers stci-nightly.timer          # next and last fire
systemctl status stci-nightly.service             # last result
journalctl -u stci-nightly.service -n 50          # systemd view
tail -50 /var/lib/intentsolutions/stci-nightly/logs/$(date -u +%F).log
cat /var/lib/intentsolutions/liveness/stci-nightly.ok    # last verified success (UTC)
curl -s https://inferencepriceindex.com/v1/index/latest.json | python3 -c 'import json,sys;print(json.load(sys.stdin)["date"])'
```

The dev-box liveness sweep also reads the public `latest.json` outside-in and pages Discord
`sys-automation` when its `date` is more than two days old (intent-os
`ops/automation/devbox-liveness/automation-liveness-sweep.sh`, row `stci-index-freshness`).

## Re-running a date

As `intentsolutions` on the VPS (never with `sudo`):

```bash
# today, by hand (same as the timer)
systemctl start stci-nightly.service

# a specific date, or a date that is already published
STCI_NIGHTLY_DATE=2026-11-20 /usr/local/sbin/stci-nightly.sh
STCI_NIGHTLY_DATE=2026-11-20 STCI_NIGHTLY_FORCE=1 /usr/local/sbin/stci-nightly.sh
```

Note that OpenRouter serves current prices only: recomputing a past date collects today's
listings under that date. Use `FORCE` for a same-day repair, not for backfilling history
(see `000-docs/005-DR-SOPS-recompute-runbook.md`).

## Planted-fault drill

```bash
STCI_NIGHTLY_FAULT_PROXY=http://127.0.0.1:9 STCI_NIGHTLY_FORCE=1 /usr/local/sbin/stci-nightly.sh; echo rc=$?
```

The dead proxy applies only to the three pipeline steps (a bare `HTTPS_PROXY` would also
blind the alert floor's own delivery). Expected: the collector cannot reach OpenRouter, the
run exits 1, `.ok` is not written, nothing is committed, and one high event reaches Discord
`#sys-alerts` (proven 2026-11-20, message id `1573385893341954260`; intent-os `ops/alert-floor/README.md`).

## Updating the script or units

Change `ops/vps/` in a PR. After merge, on the VPS:

```bash
cd /var/lib/intentsolutions/stci-nightly/repo && git fetch origin && git reset --hard origin/main
sudo bash ops/vps/install.sh
```

The installer refuses without the deploy key, re-copies all three files, rewrites the
provenance record and re-arms the timer. Compare `sha256sum ops/vps/stci-nightly.sh` with
`/usr/local/sbin/stci-nightly.sh.provenance` to confirm the deployed copy.

## Rotating the deploy key

```bash
# on the VPS, as intentsolutions
ssh-keygen -t ed25519 -N "" -C stci-nightly@intentsolutions-vps -f ~/.ssh/stci_nightly_ed25519.new
# on the dev box
gh repo deploy-key list --repo jeremylongshore/stci-standard-inference-token-cost-index
gh repo deploy-key delete <old-id> --repo jeremylongshore/stci-standard-inference-token-cost-index
ssh intentsolutions cat ~/.ssh/stci_nightly_ed25519.new.pub > /dev/shm/k.pub
gh repo deploy-key add /dev/shm/k.pub --allow-write -t stci-nightly@intentsolutions-vps \
  --repo jeremylongshore/stci-standard-inference-token-cost-index; rm /dev/shm/k.pub
# back on the VPS
mv ~/.ssh/stci_nightly_ed25519.new ~/.ssh/stci_nightly_ed25519 && mv ~/.ssh/stci_nightly_ed25519.new.pub ~/.ssh/stci_nightly_ed25519.pub
ssh -i ~/.ssh/stci_nightly_ed25519 -o IdentitiesOnly=yes -T git@github.com   # "successfully authenticated"
```

Never print or copy the private key anywhere else; the `~/.ssh/config` host
`github-stci-nightly` points at it.

## Stopping it

```bash
sudo systemctl disable --now stci-nightly.timer      # stop scheduling (service stays installed)
sudo systemctl stop stci-nightly.service             # abort a run in progress
```

To remove it entirely: disable the timer, `sudo rm /etc/systemd/system/stci-nightly.{service,timer}
/usr/local/sbin/stci-nightly.sh*`, `sudo systemctl daemon-reload`, delete the GitHub deploy key,
and remove `/var/lib/intentsolutions/stci-nightly`. Then retire the rows in intent-os
`mission-control/automations.md` and `ops/automation/registry.json` in the same session.
