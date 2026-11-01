import os, subprocess, pathlib, time, signal, json
root=pathlib.Path.cwd(); base=root/'.gate-live'; lab=base/'home'
subprocess.run(['bash','bin/fm-lab-home.sh','create',str(lab)],check=True,stdout=subprocess.DEVNULL)
env=os.environ.copy()
for k in list(env):
 if k.startswith('FM_') or k in ['TMUX','REX_SESSION','REX_BLOCK']: env.pop(k,None)
env.update(FM_HOME=str(lab),TMUX_TMPDIR=str(lab/'tmux'),FM_BACKEND='tmux',FM_POLL='0.1',FM_SIGNAL_GRACE='1',FM_CHECK_INTERVAL='999999',FM_HEARTBEAT='1',FM_HEARTBEAT_MAX='1',FM_HOOK_TIMEOUT='15')
(lab/'tmux').mkdir(); procs=[]; log=[]
def note(s): log.append(s); print(s,flush=True)
def wait(pred,seconds=15):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if pred(): return
  time.sleep(.025)
 raise AssertionError('timed out')
def start(label):
 f=open(base/(label+'.log'),'w'); p=subprocess.Popen(['bash','bin/fm-watch.sh'],env=env,stdout=f,stderr=subprocess.STDOUT); procs.append(p); return p
def stop(p):
 t=time.monotonic(); p.terminate(); p.wait(timeout=5); return time.monotonic()-t
try:
 for event in ['watch-tick','heartbeat']:
  d=lab/'hooks'/f'{event}.d'; d.mkdir(parents=True)
  h=d/'10-observe'; h.write_text('#!/bin/sh\ncat > "$FM_HOME/state/'+event+'-payload.json"\nif ! mkdir "$FM_HOME/state/'+event+'-running" 2>/dev/null; then touch "$FM_HOME/state/'+event+'-overlap"; fi\necho start >> "$FM_HOME/state/'+event+'-trace"\nsleep 7\nrmdir "$FM_HOME/state/'+event+'-running"\necho done >> "$FM_HOME/state/'+event+'-trace"\n'); h.chmod(0o755)
 p=start('first'); wait(lambda: all((lab/'state'/f'{e}-running').exists() for e in ['watch-tick','heartbeat']))
 markers={}
 for e in ['watch-tick','heartbeat']:
  wait(lambda e=e: (lab/'state'/f'.fm-hook-{e}.pid').exists())
  markers[e]=(lab/'state'/f'.fm-hook-{e}.pid').read_text().strip(); assert len(markers[e].split())>=2,markers
  note(e+' payload: '+(lab/'state'/f'{e}-payload.json').read_text().strip()); note(e+' identity marker: '+markers[e])
 elapsed=stop(p); note(f'first watcher stopped after {elapsed:.3f}s while both seven-second hooks still ran')
 assert all((lab/'state'/f'{e}-running').exists() for e in markers)
 p=start('successor'); time.sleep(2)
 for e in markers:
  assert (lab/'state'/f'{e}-trace').read_text().splitlines()==['start'],e
  assert not (lab/'state'/f'{e}-overlap').exists(),e
 note('successor suppressed both in-flight hooks across handoff')
 wait(lambda: all('done' in (lab/'state'/f'{e}-trace').read_text() for e in markers),12)
 stop(p)
 # Let any newly scheduled hooks finish before changing their executable.
 time.sleep(8)
 for e in markers:
  assert not (lab/'state'/f'{e}-overlap').exists(),e
  (lab/'hooks'/f'{e}.d'/'10-observe').write_text('#!/bin/sh\ncat > "$FM_HOME/state/'+e+'-reused-payload.json"\n')
  (lab/'state'/f'.fm-hook-{e}.pid').write_text(f'{os.getpid()} linux-starttime=1 cmdline-hex=00\n')
 p=start('reused-pid'); wait(lambda: all((lab/'state'/f'{e}-reused-payload.json').exists() for e in markers)); stop(p)
 note('both events ran despite stale markers naming this live driver PID with a different identity')
 for e in markers: note(e+' final trace: '+json.dumps((lab/'state'/f'{e}-trace').read_text().splitlines()))
finally:
 for p in procs:
  if p.poll() is None: p.terminate(); p.wait(timeout=5)
 evidence=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6ANWTAFP19Q340YCRKM7S8P')
 (evidence/'live-watcher.txt').write_text('\n'.join(log)+'\n')
 for f in base.glob('*.log'): (evidence/('live-watcher-'+f.name)).write_text(f.read_text())
