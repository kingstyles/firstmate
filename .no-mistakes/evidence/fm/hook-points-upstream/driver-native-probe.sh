#!/bin/bash
set -u
LAB="$PWD/.gate-live/native-home"
[ -e "$LAB/.fm-lab-home" ] || bash bin/fm-lab-home.sh create "$LAB" >/dev/null
mkdir -p "$LAB/tmux"
touch "$LAB/config/supervision-host"
# Use the lab-local relative directory because the absolute worktree path exceeds Unix socket limits.
export TMUX_TMPDIR=.gate-live/native-home/tmux
env -u NO_MISTAKES_GATE -u FM_GATE_REFUSE_BYPASS -u FM_ROOT_OVERRIDE -u FM_STATE_OVERRIDE -u FM_DATA_OVERRIDE -u FM_CONFIG_OVERRIDE -u FM_PROJECTS_OVERRIDE -u CLAUDECODE tmux -S .gate-live/fm-lab new-session -d -s primary -x 120 -y 40 -c "$PWD" -e FM_HOME="$LAB" claude
rc=$?
if [ "$rc" -eq 0 ]; then
  sleep 4
  tmux -S .gate-live/fm-lab capture-pane -p -t primary
  tmux -S .gate-live/fm-lab kill-server
fi
exit "$rc"
