#!/usr/bin/env bash
set -eu
E=/home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E
LAB=$(mktemp -d "$PWD/fm-lab.XXXXXX")
cleanup() { rm -rf "$LAB"; }
trap cleanup EXIT
bin/fm-lab-home.sh create "$LAB"
mkdir -p "$LAB/hooks/session-start.d"
touch "$LAB/config/supervision-host-off"
cat > "$LAB/hooks/session-start.d/10-context" <<'HOOK'
#!/bin/sh
cat > "$FM_HOME/session-payload.json"
printf 'External module: lab session context delivered.\n'
HOOK
chmod +x "$LAB/hooks/session-start.d/10-context"
env -u FM_ROOT_OVERRIDE -u FM_STATE_OVERRIDE -u FM_CONFIG_OVERRIDE -u FM_DATA_OVERRIDE -u FM_PROJECTS_OVERRIDE FM_HOME="$LAB" TMPDIR="$LAB" bin/fm-session-start.sh --reemit --source hooks-live > "$E/startup-digest.txt" 2>&1
cp "$LAB/session-payload.json" "$E/startup-payload.json"
python3 - "$E" <<'PY'
import pathlib,json,sys
p=pathlib.Path(sys.argv[1]); s=(p/'startup-digest.txt').read_text(); j=json.loads((p/'startup-payload.json').read_text())
assert 'ADD-ON HOOKS (session-start)' in s
assert 'External module: lab session context delivered.' in s
assert j['reemit'] is True and j['source']=='hooks-live'
print(json.dumps(j))
PY
