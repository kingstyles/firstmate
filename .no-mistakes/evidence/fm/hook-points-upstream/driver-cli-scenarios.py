import os, pathlib, subprocess, json
root=pathlib.Path.cwd(); lab=root/'.gate-live/cli-home'; ev=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6ANWTAFP19Q340YCRKM7S8P'); out=[]
subprocess.run(['bash','bin/fm-lab-home.sh','create',str(lab)],check=True,stdout=subprocess.DEVNULL)
env=os.environ.copy()
for k in list(env):
 if k.startswith('FM_') or k in ['TMUX','REX_SESSION','REX_BLOCK','TASKS_AXI_FILE','TASKS_AXI_BACKEND']: env.pop(k,None)
env.update(FM_HOME=str(lab),TMUX_TMPDIR=str(lab/'tmux'),FM_BACKEND='tmux')
(lab/'tmux').mkdir()
def run(cmd,data='',**kw):
 p=subprocess.run(cmd,input=data,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=60,**kw)
 out.append('$ '+' '.join(cmd)+'\nexit='+str(p.returncode)+'\n'+p.stdout+p.stderr); return p
def hook(event,name,body):
 d=lab/'hooks'/f'{event}.d'; d.mkdir(parents=True,exist_ok=True); h=d/name; h.write_text('#!/bin/sh\n'+body+'\n'); h.chmod(0o755); return h
try:
 events='session-start intake pre-spawn post-spawn watch-tick heartbeat turn-end pre-merge post-merge teardown prompt-submit stop'.split()
 for event in events:
  hook(event,'10-observe','cat >> "$FM_HOME/state/events.jsonl"; printf "\\n" >> "$FM_HOME/state/events.jsonl"')
  p=run(['bash','bin/fm-hooks.sh','run',event],json.dumps({'scenario':'public-cli','event':event,'path':'/srv/app:=null'})); assert p.returncode==0
 rows=[json.loads(l) for l in (lab/'state/events.jsonl').read_text().splitlines()]
 assert [r['event'] for r in rows]==events; out.append('Installed external module received these public CLI event payloads:\n'+json.dumps(rows,indent=2))
 # Real CLI admission control, not a remote forge stub.
 h=hook('pre-merge','20-refuse','echo "temporary release freeze" >&2; exit 1')
 (lab/'state'/'freeze.meta').write_text('window=fm-lab:freeze\nproject=disposable\nworktree='+str(lab/'unused')+'\n')
 before=(lab/'state'/'freeze.meta').read_bytes()
 p=run(['bash','bin/fm-pr-merge.sh','freeze','https://github.com/example/disposable/pull/1'])
 assert p.returncode==3 and 'temporary release freeze' in p.stderr+p.stdout
 assert (lab/'state'/'freeze.meta').read_bytes()==before
 out.append('Refused merge left its task record byte-for-byte unchanged. No merge was attempted.')
 # Actual durable inbox and wake drain interface.
 h.unlink()
 (lab/'config'/'supervision-host-off').touch(); (lab/'state'/'inbox').mkdir()
 (lab/'state'/'inbox'/'note1.note').write_text('id=note1\n--\nReview disposable hook validation\n')
 hook('intake','20-route','cat > "$FM_HOME/state/intake-payload.json"; echo \'{"route":"validation"}\'')
 p=run(['bash','-c','. bin/fm-wake-lib.sh; fm_wake_append check inbox:note1 "check: captain inbox note note1 - Review disposable hook validation"']); assert p.returncode==0
 p=run(['bash','bin/fm-wake-drain.sh']); assert p.returncode==0 and 'INTAKE inbox:note1: {"route":"validation"}' in p.stdout
 out.append('Presented intake payload: '+(lab/'state'/'intake-payload.json').read_text())
 # Read-only startup reaches the real appended session-start module.
 hook('session-start','20-context','cat > "$FM_HOME/state/start-payload.json"; echo "DISPOSABLE ADD-ON READY"')
 (lab/'state'/'.lock').write_text(str(os.getpid())+'\n')
 p=run(['bash','bin/fm-session-start.sh','--reemit','--source','live-cli'])
 assert 'DISPOSABLE ADD-ON READY' in p.stdout
 out.append('Startup hook payload: '+(lab/'state'/'start-payload.json').read_text())
finally:
 (ev/'live-cli-scenarios.txt').write_text('\n\n'.join(out))
