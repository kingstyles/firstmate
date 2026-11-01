#!/usr/bin/env bash
set -eu
LAB=$(mktemp -d "$PWD/fm-lab.XXXXXX")
trap 'rm -rf "$LAB"' EXIT
bin/fm-lab-home.sh create "$LAB"
mkdir -p "$LAB/projects/demo" "$LAB/data/refuse" "$LAB/hooks/pre-spawn.d"
git -C "$LAB/projects/demo" init -q -b main
printf '# Task\n## Captain\047s intent\nExercise the installed admission hook.\n\n## Firstmate spec\nRefuse this disposable launch before creating anything.\n' > "$LAB/data/refuse/brief.md"
printf '#!/bin/sh\ncat > "$FM_HOME/spawn-payload.json"\necho "lab launch refused by module" >&2\nexit 1\n' > "$LAB/hooks/pre-spawn.d/10-refuse"
chmod +x "$LAB/hooks/pre-spawn.d/10-refuse"
set +e
env -u FM_ROOT_OVERRIDE -u FM_STATE_OVERRIDE -u FM_CONFIG_OVERRIDE -u FM_DATA_OVERRIDE -u FM_PROJECTS_OVERRIDE FM_HOME="$LAB" TMPDIR="$LAB" bin/fm-spawn.sh refuse "$LAB/projects/demo" --mode local-only --yolo off --harness claude
status=$?
set -e
printf 'spawn exit=%s\n' "$status"
[ "$status" -eq 3 ]
[ ! -e "$LAB/state/refuse.meta" ]
cp "$LAB/spawn-payload.json" /home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E/spawn-refusal-payload.json
cat "$LAB/spawn-payload.json"
