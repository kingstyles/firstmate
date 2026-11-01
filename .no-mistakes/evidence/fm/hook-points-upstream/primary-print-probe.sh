#!/usr/bin/env bash
set -eu
E=/home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E
LAB=$(mktemp -d "$PWD/lXXX")
cleanup() {
 TMUX_TMPDIR="$LAB/tmux" tmux -L fm-lab kill-server 2>/dev/null || true
 rm -rf "$LAB"
}
trap cleanup EXIT
bin/fm-lab-home.sh create "$LAB"
mkdir -p "$LAB/tmux" "$LAB/hooks/session-start.d" "$LAB/hooks/prompt-submit.d" "$LAB/hooks/stop.d"
touch "$LAB/config/supervision-host-off"
for event in session-start prompt-submit stop; do
 cat > "$LAB/hooks/$event.d/10-record" <<'HOOK'
#!/bin/sh
jq -c --arg event "$FM_HOOK_EVENT" '{event:$event,payload:.}' >> "$FM_HOME/primary-events.jsonl"
HOOK
 chmod +x "$LAB/hooks/$event.d/10-record"
done
env -u NO_MISTAKES_GATE -u FM_GATE_REFUSE_BYPASS -u FM_ROOT_OVERRIDE -u FM_STATE_OVERRIDE -u FM_DATA_OVERRIDE -u FM_CONFIG_OVERRIDE -u FM_PROJECTS_OVERRIDE TMUX_TMPDIR="$LAB/tmux" tmux -L fm-lab new-session -d -s primary -x 120 -y 40 -c "$PWD" -e FM_HOME="$LAB" claude -p --no-session-persistence --tools '' -- 'Reply with HOOK_LAB_ACK only. Do not use any tools or change any files.'
TMUX_TMPDIR="$LAB/tmux" tmux -L fm-lab set-option -w -t primary remain-on-exit on
sleep 35
TMUX_TMPDIR="$LAB/tmux" tmux -L fm-lab capture-pane -p -t primary > "$E/primary-print-screen.txt"
if [ -f "$LAB/primary-events.jsonl" ]; then cp "$LAB/primary-events.jsonl" "$E/primary-print-events.jsonl"; fi
cat "$E/primary-print-screen.txt"
