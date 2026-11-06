#!/usr/bin/env bash
# pip install "$@", retrying while a dependency released minutes ago is not yet
# on the PyPI mirror the runners see ("No matching distribution found"): a
# fresh release of batoolset-gui / qtpy-ai-sidecar failed every job that
# installed too early (2026-11-05, 2026-11-06). Any other error fails at once.
# Up to 20 tries, 30 s apart (10 min); a normal run does not wait.
set -u
tries=20
for i in $(seq 1 "$tries"); do
    # no cache: pip would otherwise reuse the index page it got on the first try
    if out=$(pip install --no-cache-dir "$@" 2>&1); then
        echo "$out"
        exit 0
    fi
    echo "$out"
    if ! grep -q "No matching distribution found" <<<"$out"; then
        exit 1
    fi
    if [ "$i" -lt "$tries" ]; then
        echo "::notice::A required version is not on the PyPI mirror yet (try $i/$tries); retrying in 30 s"
        sleep 30
    fi
done
echo "::error::Still not on the PyPI mirror after $tries tries"
exit 1
