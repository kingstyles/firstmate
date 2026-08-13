#!/usr/bin/env bash
# Acquire or inspect the per-home firstmate session lock.
# Writes the harness (agent) process PID found by walking the shell's ancestry.
# Detached tool runners fall back to the single harness whose cwd is this repo.
# That PID lives as long as the firstmate session, unlike a transient subshell.
# Usage: fm-lock.sh           acquire; exit 1 if another live session holds it
#        fm-lock.sh status    print holder and liveness; always exits 0
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FM_ROOT="${FM_ROOT_OVERRIDE:-$(cd "$SCRIPT_DIR/.." && pwd)}"
FM_HOME="${FM_HOME:-${FM_ROOT_OVERRIDE:-$FM_ROOT}}"
STATE="${FM_STATE_OVERRIDE:-$FM_HOME/state}"
LOCK="$STATE/.lock"
mkdir -p "$STATE"

# Known harness command names; extend when a new adapter is verified.
HARNESS_RE='claude|codex|opencode|grok|^pi$'
PROC_ROOT=${FM_PROC_ROOT:-/proc}

root_harness_pid() {
  local pid ppid comm args cwd name command entrypoint harness candidates=''
  local -a direct_pids=() interpreted_pids=()
  local -A direct_names=() direct_parents=() interpreted_names=()
  while read -r pid ppid comm args; do
    [ -n "$pid" ] || continue
    cwd=$(readlink -f "$PROC_ROOT/$pid/cwd" 2>/dev/null) || continue
    [ "$cwd" = "$FM_ROOT" ] || continue
    name=$(basename "$comm")
    case "$name" in
      claude|codex|opencode|grok|pi)
        direct_pids+=("$pid")
        direct_names["$pid"]=$name
        direct_parents["$pid"]=$ppid
        ;;
      node|nodejs|python|python3)
        read -r command entrypoint _ <<< "$args"
        [ -n "${entrypoint:-}" ] || continue
        harness=$(printf '%s\n' "$entrypoint" | grep -oE '(^|/)(claude|codex|opencode|grok|pi)(\.[^/]*)?($|/)' | head -n 1 | sed -E 's#^/##; s#/.*$##; s/\..*$//')
        [ -n "$harness" ] || continue
        interpreted_pids+=("$pid")
        interpreted_names["$pid"]=$harness
        ;;
    esac
  done < <(ps -eo pid=,ppid=,comm=,args= 2>/dev/null)

  for pid in "${direct_pids[@]}"; do
    candidates="$candidates${candidates:+ }$pid"
  done
  for pid in "${interpreted_pids[@]}"; do
    local wrapped=0 direct_pid
    for direct_pid in "${direct_pids[@]}"; do
      if [ "${direct_parents[$direct_pid]}" = "$pid" ] && [ "${direct_names[$direct_pid]}" = "${interpreted_names[$pid]}" ]; then
        wrapped=1
        break
      fi
    done
    [ "$wrapped" -eq 1 ] || candidates="$candidates${candidates:+ }$pid"
  done
  # shellcheck disable=SC2086 # Intentional word splitting counts candidate PIDs.
  set -- $candidates
  [ "$#" -eq 1 ] || return 1
  printf '%s\n' "$1"
}

harness_pid() {
  local pid=$$ comm args
  for _ in 1 2 3 4 5 6 7 8; do
    comm=$(ps -o comm= -p "$pid" 2>/dev/null) || return 1
    args=$(ps -o args= -p "$pid" 2>/dev/null)
    if printf '%s' "$(basename "$comm")" | grep -qE "$HARNESS_RE"; then
      echo "$pid"; return 0
    fi
    # Bare interpreter (e.g. node): match the harness name in its script path.
    case "$comm" in
      *node*|*python*) printf '%s' "$args" | grep -qE "$HARNESS_RE" && { echo "$pid"; return 0; } ;;
    esac
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -z "$pid" ] || [ "$pid" -le 1 ]; then
      break
    fi
  done
  root_harness_pid
}

holder_alive() {  # true if $1 is a live process that looks like a harness
  local pid=$1 comm
  kill -0 "$pid" 2>/dev/null || return 1
  comm=$(ps -o comm= -p "$pid" 2>/dev/null) || return 1
  printf '%s' "$(basename "$comm") $(ps -o args= -p "$pid" 2>/dev/null)" | grep -qE "$HARNESS_RE"
}

if [ "${1:-}" = "status" ]; then
  if [ ! -f "$LOCK" ]; then echo "lock: free"; exit 0; fi
  old=$(cat "$LOCK")
  if holder_alive "$old"; then echo "lock: held by live harness pid $old"; else echo "lock: stale (pid $old dead or not a harness)"; fi
  exit 0
fi

me=$(harness_pid) || { echo "error: cannot locate harness process in ancestry" >&2; exit 1; }
if [ -f "$LOCK" ]; then
  old=$(cat "$LOCK")
  if [ "$old" != "$me" ] && holder_alive "$old"; then
    echo "error: another live firstmate session holds the lock (pid $old); operate read-only until resolved" >&2
    exit 1
  fi
fi
echo "$me" > "$LOCK"
echo "lock acquired: harness pid $me"
