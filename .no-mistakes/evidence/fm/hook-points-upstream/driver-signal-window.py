exec(open('.gate-live/drive.py').read().split('try:\n for event')[0].replace("lab=base/'home'","lab=base/'signal-home-2'"))
import threading
try:
 for event in ['watch-tick','heartbeat']:
  # Select exactly one event, with no other hook folder installed.
  for d in (lab/'hooks').glob('*.d') if (lab/'hooks').exists() else []:
   import shutil; shutil.rmtree(d)
  d=lab/'hooks'/f'{event}.d'; d.mkdir(parents=True)
  h=d/'10-slow'; h.write_text('#!/bin/sh\ncat > "$FM_HOME/state/payload.json"\necho start >> "$FM_HOME/state/trace"\nsleep 6\necho done >> "$FM_HOME/state/trace"\n'); h.chmod(0o755)
  marker=lab/'state'/f'.fm-hook-{event}.pid'
  fakebin=lab/'delay-bin'; fakebin.mkdir(exist_ok=True)
  od=fakebin/'od'
  od.write_text('''#!/bin/bash
marker="$FM_HOME/state/.fm-hook-$DELAY_EVENT.pid"
if [ -f "$marker" ] && [ ! -e "$FM_HOME/state/release" ]; then
 pid=$(cut -d ' ' -f 1 "$marker")
 case "$*" in *"/proc/$pid/cmdline"*)
  touch "$FM_HOME/state/stalled"
  while [ ! -e "$FM_HOME/state/release" ]; do sleep .02; done
 ;; esac
fi
exec /usr/bin/od "$@"
'''); od.chmod(0o755)
  env['PATH']=str(fakebin)+':'+os.environ['PATH']; env['DELAY_EVENT']=event
  (lab/'state'/'stalled').unlink(missing_ok=True); (lab/'state'/'release').unlink(missing_ok=True)
  trace=lab/'state'/'trace'; trace.unlink(missing_ok=True)
  p=start(event+'-publication')
  wait(lambda: (lab/'state'/'stalled').exists())
  t=time.monotonic(); p.send_signal(signal.SIGTERM); time.sleep(.1)
  assert p.poll() is None, 'watcher exited before publishing the blocked marker'
  # Drain the deliberately stalled publication after TERM, before the slow hook ends.
  (lab/'state'/'release').touch()
  p.wait(timeout=5)
  record=marker.read_text()
  p.wait(timeout=5)
  assert len(record.split())>=3,repr(record)
  note(f'{event}: TERM during blocked marker publication was deferred; full marker={record.strip()}; exit after {time.monotonic()-t:.3f}s')
  assert trace.read_text().splitlines()==['start']
  marker.write_text(record)
  p=start(event+'-publication-successor'); time.sleep(1)
  assert trace.read_text().splitlines()==['start'], 'overlap across signal window'
  stop(p); wait(lambda:'done' in trace.read_text(),8)
  note(event+': successor respected complete identity marker; no overlap and stop did not await hook')
finally:
 for p in procs:
  if p.poll() is None: p.terminate(); p.wait(timeout=5)
 pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6ANWTAFP19Q340YCRKM7S8P/live-signal-publication.txt').write_text('\n'.join(log)+'\n')
