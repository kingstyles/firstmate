#!/usr/bin/env bash
# tests/fm-lock.test.sh - behavior tests for the primary session lock.
set -u

# shellcheck source=tests/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

LOCK="$ROOT/bin/fm-lock.sh"
TMP_ROOT=$(fm_test_tmproot fm-lock-tests)

make_world() {
  local name=$1 world root home proc fakebin
  world="$TMP_ROOT/$name"
  root="$world/root"
  home="$world/home"
  proc="$world/proc"
  fakebin=$(fm_fakebin "$world")
  mkdir -p "$root" "$home/state" "$proc"
  printf '%s\n' "$root|$home|$proc|$fakebin"
}

make_detached_ps() {
  local fakebin=$1 rows=$2
  cat > "$fakebin/ps" <<SH
#!/usr/bin/env bash
case "\$*" in
  *"pid=,ppid=,comm=,args="*) printf '%s\n' '$rows'; exit 0 ;;
  *"comm="*) printf '%s\n' bash; exit 0 ;;
  *"args="*) printf '%s\n' 'bash bin/fm-lock.sh'; exit 0 ;;
  *"ppid="*) printf '%s\n' 1; exit 0 ;;
esac
exit 1
SH
  chmod +x "$fakebin/ps"
}

add_proc_cwd() {
  local proc=$1 pid=$2 cwd=$3
  mkdir -p "$proc/$pid"
  ln -s "$cwd" "$proc/$pid/cwd"
}

test_unique_root_harness_acquires_lock() {
  local rec root home proc fakebin out
  rec=$(make_world unique)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  make_detached_ps "$fakebin" '42 1 codex /usr/local/bin/codex'
  add_proc_cwd "$proc" 42 "$root"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK")

  assert_contains "$out" "lock acquired: harness pid 42" "unique root harness did not acquire the lock"
  assert_grep '42' "$home/state/.lock" "unique root harness pid was not written"
  pass "fm-lock accepts one detached harness rooted at firstmate"
}

test_direct_harness_beats_interpreter_wrapper() {
  local rec root home proc fakebin out
  rec=$(make_world wrapper)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  make_detached_ps "$fakebin" $'50 1 node node /opt/codex\n51 50 codex /opt/vendor/codex'
  add_proc_cwd "$proc" 50 "$root"
  add_proc_cwd "$proc" 51 "$root"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK")

  assert_contains "$out" "lock acquired: harness pid 51" "direct harness did not beat its interpreter wrapper"
  pass "fm-lock prefers the direct harness process over a wrapper"
}

test_multiple_root_harnesses_fail_closed() {
  local rec root home proc fakebin out status=0
  rec=$(make_world multiple)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  make_detached_ps "$fakebin" $'60 1 codex /opt/codex\n61 1 codex /opt/codex'
  add_proc_cwd "$proc" 60 "$root"
  add_proc_cwd "$proc" 61 "$root"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK" 2>&1) || status=$?

  expect_code 1 "$status" "multiple root harnesses must fail closed"
  assert_contains "$out" "cannot locate harness process in ancestry" "ambiguous fallback did not use the safe refusal"
  assert_absent "$home/state/.lock" "ambiguous fallback wrote a lock"
  pass "fm-lock rejects multiple detached harnesses in the same root"
}

test_other_root_harness_is_ignored() {
  local rec root home proc fakebin other out status=0
  rec=$(make_world other-root)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  other="$TMP_ROOT/other-root/project"
  mkdir -p "$other"
  make_detached_ps "$fakebin" '70 1 codex /opt/codex'
  add_proc_cwd "$proc" 70 "$other"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK" 2>&1) || status=$?

  expect_code 1 "$status" "a harness in another root must not acquire this lock"
  assert_contains "$out" "cannot locate harness process in ancestry" "other-root harness did not use the safe refusal"
  assert_absent "$home/state/.lock" "other-root harness wrote a lock"
  pass "fm-lock ignores detached harnesses rooted elsewhere"
}

test_distinct_direct_and_interpreted_harnesses_fail_closed() {
  local rec root home proc fakebin out status=0
  rec=$(make_world mixed)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  make_detached_ps "$fakebin" $'80 1 codex /opt/codex\n81 1 node node /opt/claude/bin/claude.js'
  add_proc_cwd "$proc" 80 "$root"
  add_proc_cwd "$proc" 81 "$root"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK" 2>&1) || status=$?

  expect_code 1 "$status" "distinct direct and interpreted harnesses must fail closed"
  assert_absent "$home/state/.lock" "mixed harnesses wrote a lock"
  pass "fm-lock rejects distinct direct and interpreted harnesses"
}

test_unrelated_interpreter_argument_is_ignored() {
  local rec root home proc fakebin out status=0
  rec=$(make_world unrelated)
  IFS='|' read -r root home proc fakebin <<EOF
$rec
EOF
  make_detached_ps "$fakebin" '90 1 node node /opt/runner.js --model codex'
  add_proc_cwd "$proc" 90 "$root"

  out=$(FM_ROOT_OVERRIDE="$root" FM_HOME="$home" FM_PROC_ROOT="$proc" PATH="$fakebin:$PATH" "$LOCK" 2>&1) || status=$?

  expect_code 1 "$status" "an unrelated interpreter must not acquire the lock"
  assert_absent "$home/state/.lock" "unrelated interpreter wrote a lock"
  pass "fm-lock ignores harness words in interpreter arguments"
}

test_unique_root_harness_acquires_lock
test_direct_harness_beats_interpreter_wrapper
test_multiple_root_harnesses_fail_closed
test_other_root_harness_is_ignored
test_distinct_direct_and_interpreted_harnesses_fail_closed
test_unrelated_interpreter_argument_is_ignored
