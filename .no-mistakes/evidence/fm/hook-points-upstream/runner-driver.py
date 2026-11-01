import os,pathlib,subprocess,json,shutil,time
root=pathlib.Path.cwd();home=root/'.test-runner';ev=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AKTC8RC41CSCCVA0619230');log=open(ev/'runner-transcript.log','w',buffering=1)
env={k:v for k,v in os.environ.items() if not k.startswith('FM_')};env.update(FM_HOME=str(home),TMPDIR=str(root/'.test-tmp'))
def cmd(args,payload='',extra={}):
 p=subprocess.run([str(a) for a in args],env=env|extra,input=payload,text=True,capture_output=True,timeout=20);log.write(json.dumps({'command':[str(a) for a in args],'input':payload,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})+'\n');return p
def hook(event,name,body,parent=None):
 p=(parent or home/'hooks')/f'{event}.d'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
try:
 assert not home.exists();assert cmd([root/'bin/fm-lab-home.sh','create',home]).returncode==0
 events='session-start intake pre-spawn post-spawn watch-tick heartbeat turn-end pre-merge post-merge teardown prompt-submit stop'.split()
 for event in events:
  p=cmd([root/'bin/fm-hooks.sh','run',event],'sentinel');assert p.returncode==0 and not p.stdout and not p.stderr
 for event in events:
  hook(event,'10-receipt','printf "%s " "$FM_HOOK_EVENT" >> "$FM_HOME/state/receipts"; cat >> "$FM_HOME/state/receipts"')
  p=cmd([root/'bin/fm-hooks.sh','run',event],json.dumps({'task_id':'lab-1','project_dir':'/srv/app:=null','event':event}));assert p.returncode==0
 log.write('INSTALLED MODULE RECEIPTS\n'+(home/'state/receipts').read_text()+'\n')
 # Additional folder and deterministic deep merge with first-writer conflict policy.
 hook('intake','10-receipt','echo \'{"route":{"owner":"first","priority":2}}\'')
 hook('intake','20-enrich','echo \'{"route":{"owner":"second","tag":"room"}}\'')
 extra=home/'extra';hook('intake','05-extra','echo \'{"external":true}\'',extra)
 p=cmd([root/'bin/fm-hooks.sh','run','intake'],'{}',{'FM_HOOKS_EXTRA_DIR':str(extra)})
 assert json.loads(p.stdout)=={'route':{'owner':'first','priority':2,'tag':'room'},'external':True}
 assert 'conflict on route.owner' in p.stderr
 hook('pre-spawn','10-receipt','echo \'{"owner":"first"}\'')
 hook('pre-spawn','20-conflict','echo \'{"owner":"second"}\'')
 p=cmd([root/'bin/fm-hooks.sh','run','pre-spawn'],'{}',{'FM_HOOK_MERGE_CONFLICT':'refuse'});assert p.returncode==3
 hook('pre-merge','10-receipt','exec sleep 30')
 start=time.monotonic();p=cmd([root/'bin/fm-hooks.sh','run','pre-merge'],'{}',{'FM_HOOK_TIMEOUT':'00'});elapsed=time.monotonic()-start
 assert p.returncode==3 and 'timed out after 10s' in p.stderr and elapsed<15
 log.write('ZERO TIMEOUT ELAPSED '+str(round(elapsed,2))+' seconds\n')
 mirror=home/'state/mirror.jsonl'
 p=cmd([root/'bin/fm-hooks.sh','run','prompt-submit'],json.dumps({'session_id':'lab-1','prompt':'private disposable note'}),{'FM_HOOK_MIRROR':str(mirror)})
 row=json.loads(mirror.read_text());assert 'private disposable note' not in mirror.read_text();log.write('DIGEST-ONLY MIRROR '+json.dumps(row)+'\n')
 log.write('RESULT All runner contract checks passed.\n')
finally:
 if home.exists():shutil.rmtree(home)
 log.close()
