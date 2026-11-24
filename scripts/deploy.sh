#!/usr/bin/env bash
# Build the image on the Docker host from the committed HEAD and update the container there.
# The image stays local to that host (a registry is optional; ours sits behind an upload cap the ffmpeg layer breaks).
# Usage: bash scripts/deploy.sh   (from the repo root, with SSH access to the host)
# The host comes from KIDTUBE_HOST, or from deploy.local.env in the repo root (git-ignored), e.g.
#   KIDTUBE_HOST=root@192.168.1.10
set -euo pipefail

[ -f deploy.local.env ] && . ./deploy.local.env
HOST="${KIDTUBE_HOST:?Set KIDTUBE_HOST=user@host, or put it in deploy.local.env}"
IMAGE="kidtube"
REV="$(git rev-parse --short HEAD)"

if [ -n "$(git status --porcelain)" ]; then
  echo "Commit your changes first: the image is built from HEAD ($REV)." >&2
  exit 1
fi

echo "Building $IMAGE:$REV on $HOST"
git archive --format=tar HEAD | ssh "$HOST" "docker build -q -t $IMAGE:latest -t $IMAGE:$REV -"

# On Unraid the container comes from a template (see unraid/); update_container recreates it from that.
if ssh "$HOST" "docker inspect kidtube >/dev/null 2>&1"; then
  ssh "$HOST" "/usr/local/emhttp/plugins/dynamix.docker.manager/scripts/update_container kidtube" >/dev/null
  echo "Updated the kidtube container to $REV"
else
  echo "No kidtube container yet: add it from the template in the Unraid Docker tab (or see docs/runbooks/deploy.md)."
fi
