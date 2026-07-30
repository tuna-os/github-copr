#!/usr/bin/env bash
# Pull a container image, retrying transient registry failures.
#
# The Tideforge gates run ~50 jobs, and every one of them pulls a build image
# before it can assert anything. A registry timeout there fails the gate for a
# reason that has nothing to do with the package under test:
#
#   docker: Error response from daemon: Get "https://quay.io/v2/": context
#   deadline exceeded
#
# That is exactly what sank `dgop (el10 RPM)` and `cosmic-bg (el10 RPM
# payload)` on run 30257480665 — two red checks, zero real defects, and every
# dependent job skipped behind them. A gate that goes red on registry weather
# trains people to re-run it without reading it, which is how a real failure
# gets waved through.
#
# Pull explicitly and retry, so `docker run` later hits the local image store.
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "usage: $0 <image> [image...]" >&2
    exit 2
fi

attempts=5

for image in "$@"; do
    delay=5
    for attempt in $(seq 1 "$attempts"); do
        if docker pull "$image"; then
            break
        fi
        if [ "$attempt" -eq "$attempts" ]; then
            echo "pull-container-image: giving up on $image after $attempts attempts" >&2
            exit 1
        fi
        echo "pull-container-image: attempt $attempt/$attempts failed for $image; retrying in ${delay}s" >&2
        sleep "$delay"
        delay=$((delay * 2))
    done
done
