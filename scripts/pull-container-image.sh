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
    # Fallback list for image pull: if pulling from docker.io fails or is rate-limited,
    # fallback to ghcr.io/tuna-os mirror if applicable.
    pull_targets=("$image")
    if [[ "$image" =~ ^(docker\.io/library/|docker\.io/)?(ubuntu|debian|archlinux)(:.*)?$ ]]; then
        prefix_clean="${image#docker.io/}"
        prefix_clean="${prefix_clean#library/}"
        # E.g. ubuntu:26.04 -> ghcr.io/tuna-os/ubuntu:26.04
        pull_targets=("$image" "ghcr.io/tuna-os/$prefix_clean")
    fi

    success=0
    for target in "${pull_targets[@]}"; do
        delay=5
        for attempt in $(seq 1 "$attempts"); do
            if docker pull "$target"; then
                if [ "$target" != "$image" ]; then
                    docker tag "$target" "$image"
                fi
                success=1
                break 2
            fi
            if [ "$attempt" -eq "$attempts" ]; then
                echo "pull-container-image: attempt $attempts failed for $target" >&2
            else
                echo "pull-container-image: attempt $attempt/$attempts failed for $target; retrying in ${delay}s" >&2
                sleep "$delay"
                delay=$((delay * 2))
            fi
        done
    done

    if [ "$success" -ne 1 ]; then
        echo "pull-container-image: giving up on $image after trying all mirrors" >&2
        exit 1
    fi
done
