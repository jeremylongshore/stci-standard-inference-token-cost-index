#!/usr/bin/env bash
# install.sh — deploy the STCI nightly refresh onto the intentsolutions VPS.
#
# Run as root (sudo) from a checkout of origin/main on the VPS:
#   sudo bash ops/vps/install.sh
#
# It copies the script and units from THIS directory (so the deployed copies
# are byte-identical to the reviewed source), creates the job state directory
# owned by intentsolutions, seeds the liveness marker pair owned by that user
# (the liveness directory itself is root-owned, like every other VPS job), and
# arms the timer. It never runs the pipeline and never touches /srv/stci.
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[ "$(id -u)" -eq 0 ] || { echo "install.sh: run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=intentsolutions
STATE=/var/lib/intentsolutions/stci-nightly
LIVE=/var/lib/intentsolutions/liveness

for f in stci-nightly.sh stci-nightly.service stci-nightly.timer; do
  [ -s "$HERE/$f" ] || { echo "install.sh: missing $HERE/$f" >&2; exit 1; }
done
id "$USER_NAME" >/dev/null
[ -r "/home/$USER_NAME/.ssh/stci_nightly_ed25519" ] \
  || { echo "install.sh: deploy key /home/$USER_NAME/.ssh/stci_nightly_ed25519 missing (see the runbook)" >&2; exit 1; }

install -d -m 0755 -o "$USER_NAME" -g "$USER_NAME" "$STATE" "$STATE/logs"
install -d -m 0755 "$LIVE"
for m in beat ok; do
  [ -e "$LIVE/stci-nightly.$m" ] || install -m 0644 -o "$USER_NAME" -g "$USER_NAME" /dev/null "$LIVE/stci-nightly.$m"
done

install -m 0755 -o root -g root "$HERE/stci-nightly.sh" /usr/local/sbin/stci-nightly.sh
install -m 0644 -o root -g root "$HERE/stci-nightly.service" /etc/systemd/system/stci-nightly.service
install -m 0644 -o root -g root "$HERE/stci-nightly.timer" /etc/systemd/system/stci-nightly.timer
{
  echo "installed_at=$(date -u +%FT%TZ)"
  echo "source_commit=$(git -C "$HERE" rev-parse HEAD 2>/dev/null || echo unknown)"
  sha256sum "$HERE/stci-nightly.sh" "$HERE/stci-nightly.service" "$HERE/stci-nightly.timer" | sed 's#  .*/#  #'
} > /usr/local/sbin/stci-nightly.sh.provenance
chmod 0644 /usr/local/sbin/stci-nightly.sh.provenance

systemctl daemon-reload
systemctl enable --now stci-nightly.timer
systemctl list-timers stci-nightly.timer --no-pager
echo "install.sh: stci-nightly armed; provenance at /usr/local/sbin/stci-nightly.sh.provenance"
