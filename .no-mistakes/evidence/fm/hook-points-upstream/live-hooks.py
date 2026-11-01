import os, pathlib, subprocess, tempfile, json, time, shutil, shlex
root=pathlib.Path.cwd()
evidence=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E')
lab=pathlib.Path(tempfile.mkdtemp(prefix='fm-lab.',dir=root))
log=open(evidence/'live-hooks.log','w')
env=os.environ.copy()
for key in list(env):
    if key.startswith(('FM_', 'NO_MISTAKES_GATE')) or key=='CLAUDE_PROJECT_DIR': env.pop(key,None)
env.update(FM_HOME=str(lab),TMPDIR=str(lab))
def run(args,data=None,extra=None,ok=(0,),timeout=35):
    e=env.copy(); e.update(extra or {})
    p=subprocess.run(args,input=data,text=True,capture_output=True,env=e,cwd=root,timeout=timeout)
    log.write('$ '+shlex.join(map(str,args))+'\n')
    if data is not None: log.write('stdin: '+data+'\n')
    log.write(p.stdout+p.stderr+f'\nexit={p.returncode}\n'); log.flush()
    assert p.returncode in ok,(args,p.returncode,p.stdout,p.stderr)
    return p

def hook(event,name,body):
    d=lab/'hooks'/f'{event}.d'; d.mkdir(parents=True,exist_ok=True)
    f=d/name; f.write_text('#!/bin/sh\n'+body+'\n'); f.chmod(0o755)
def recording(event,name='10-record',extra=''):
    hook(event,name,'jq -c --arg event "$FM_HOOK_EVENT" --arg hook '+shlex.quote(name)+' \'{event:$event,hook:$hook,payload:.}\' >> "$FM_HOME/events.jsonl"\n'+extra)
def events():
    return [json.loads(s) for s in (lab/'events.jsonl').read_text().splitlines()]
try:
    run(['bin/fm-lab-home.sh','create',str(lab)])
    (lab/'config'/'supervision-host-off').touch()
    all_events='session-start intake pre-spawn post-spawn watch-tick heartbeat turn-end pre-merge post-merge teardown prompt-submit stop'.split()
    for event in all_events:
        p=run(['bash','-c','"$1" run "$2"; cat','_',str(root/'bin/fm-hooks.sh'),event],data='untouched\n')
        assert p.stdout=='untouched\n'
    for event in all_events:
        recording(event,extra='printf \'addon session context\\n\'' if event=='session-start' else ('printf \'{"route":{"team":"operations"}}\\n\'' if event in ['intake','pre-spawn'] else ''))
    payload={'task_id':'lab-task','project_dir':'/srv/app:=null','text':'quote " newline\nend','cycle':7,'forced':False}
    for event in all_events:
        p=run(['bin/fm-hooks.sh','run',event],data=json.dumps(payload),extra={'FM_HOOK_MIRROR':str(lab/'mirror.jsonl')})
        assert events()[-1]['event']==event and events()[-1]['payload']==payload
        if event not in ('session-start','intake','pre-spawn'): assert p.stdout==''
    # Real payload-builder -> runner -> installed module, including R2.
    run(['bash','-c','. bin/fm-hooks-lib.sh; fm_hooks_emit post-spawn project_dir=/srv/app:=null count:=3 ready:=true'])
    assert events()[-1]['payload']=={'project_dir':'/srv/app:=null','count':3,'ready':True}
    # Public runner refusal boundaries and non-blocking continuation.
    for event in ['pre-spawn','turn-end','pre-merge','post-spawn','post-merge','teardown','watch-tick','heartbeat']:
        hook(event,'20-refuse','echo lab-policy-refusal >&2; exit 9')
        recording(event,'30-after')
        before=len(events())
        p=run(['bin/fm-hooks.sh','run',event],data='{}',ok=(3,) if event in ['pre-spawn','turn-end','pre-merge'] else (0,))
        added=events()[before:]
        assert [v['hook'] for v in added]==(['10-record'] if p.returncode==3 else ['10-record','30-after'])
        assert 'lab-policy-refusal' in p.stderr
        (lab/'hooks'/f'{event}.d'/'20-refuse').unlink(); (lab/'hooks'/f'{event}.d'/'30-after').unlink()
    # R3: all-zero timeout must bound a genuinely slow subprocess.
    hook('pre-merge','05-slow','exec sleep 30')
    start=time.monotonic()
    p=run(['bin/fm-hooks.sh','run','pre-merge'],data='{}',extra={'FM_HOOK_TIMEOUT':'00'},ok=(3,),timeout=22)
    elapsed=time.monotonic()-start
    assert 9<=elapsed<20 and 'timed out after 10s' in p.stderr
    log.write(f'Observed zero-valued timeout duration: {elapsed:.2f}s\n')
    (lab/'hooks/pre-merge.d/05-slow').unlink()
    # Intake: user captures a note through actual product; drain calls installed module.
    run(['bin/fm-inbox.sh','note','--request-id','hook-lab-intake','--json','Route the lab maintenance idea'])
    p=run(['bin/fm-wake-drain.sh'])
    assert 'INTAKE inbox:' in p.stdout and '"operations"' in p.stdout
    intake=[v for v in events() if v['event']=='intake'][-1]['payload']
    assert intake['surface']=='inbox' and pathlib.Path(intake['text_file']).is_file()
    # Pre-merge: production command refuses before recording or contacting forge.
    hook('pre-merge','05-freeze','echo lab-release-freeze >&2; exit 1')
    (lab/'state/lab-merge.meta').write_text('window=fm:lab-merge\nproject=lab\nworktree='+str(lab/'projects')+'\n')
    p=run(['bin/fm-pr-merge.sh','lab-merge','https://github.com/example/repo/pull/7'],ok=(3,))
    assert 'lab-release-freeze' in p.stderr and 'nothing was merged or recorded' in p.stderr
    assert 'pr=' not in (lab/'state/lab-merge.meta').read_text()
    (lab/'hooks/pre-merge.d/05-freeze').unlink()
    # Shared confirmed-merge product boundary, real persistence and dedupe; no forge stub.
    p=run(['bash','-c','''. bin/fm-merge-outcome-lib.sh
fm_merge_outcome_report "$FM_HOME" "$FM_HOME/state" queued https://github.com/example/repo/pull/8 poll || exit
fm_merge_outcome_report "$FM_HOME" "$FM_HOME/state" queued https://github.com/example/repo/pull/8 poll || exit
fm_merge_outcome_report "$FM_HOME" "$FM_HOME/state" immediate https://github.com/example/repo/pull/9 self || exit
fm_merge_outcome_report "$FM_HOME" "$FM_HOME/state" immediate https://github.com/example/repo/pull/9 poll || exit
cat "$FM_HOME/state/queued.pr-poll-merge-notified" "$FM_HOME/state/immediate.pr-poll-merge-notified"
'''])
    merges=[v for v in events() if v['event']=='post-merge' and v['payload'].get('task_id') in ['queued','immediate']]
    assert len(merges)==2
    # Start real watcher with private home; capture its actual tick and heartbeat hooks.
    watch_home=lab/'watch-home'
    run(['bin/fm-lab-home.sh','create',str(watch_home)])
    (watch_home/'config/supervision-host-off').touch()
    watch_env=env.copy(); watch_env.update(FM_HOME=str(watch_home),FM_HOOKS_EXTRA_DIR=str(lab/'hooks'),FM_POLL='1',FM_HEARTBEAT='1',FM_HEARTBEAT_MAX='1')
    watcher=subprocess.Popen(['bin/fm-watch.sh'],env=watch_env,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    try:
        time.sleep(5)
    finally:
        if watcher.poll() is None: watcher.terminate()
        try: out=watcher.communicate(timeout=8)[0]
        except subprocess.TimeoutExpired:
            watcher.kill(); out=watcher.communicate()[0]
    log.write('$ FM_POLL=1 FM_HEARTBEAT=1 bin/fm-watch.sh\n'+out+f'\nexit={watcher.returncode}\n')
    watch_events=[json.loads(s) for s in (watch_home/'events.jsonl').read_text().splitlines()]
    with (lab/'events.jsonl').open('a') as f:
        for row in watch_events: f.write(json.dumps(row)+'\n')
    actual_tick=[v for v in watch_events if v['event']=='watch-tick' and 'watcher_pid' in v['payload']]
    actual_heartbeat=[v for v in watch_events if v['event']=='heartbeat' and list(v['payload'])==['home']]
    log.write('Actual watcher tick events: '+json.dumps(actual_tick)+'\nActual heartbeat events: '+json.dumps(actual_heartbeat)+'\n'); log.flush()
    # Preserve actual installed-module output, mirrors and durable merge records.
    shutil.copy(lab/'events.jsonl',evidence/'installed-hook-events.jsonl')
    shutil.copy(lab/'mirror.jsonl',evidence/'hook-mirror.jsonl')
    shutil.copy(lab/'state/.wake-queue',evidence/'lab-wake-queue.txt')
    assert actual_tick and actual_heartbeat, 'watcher did not reach both lifecycle points'
    log.write('All manual assertions passed.\n')
finally:
    shutil.rmtree(lab)
    log.write('Disposable lab removed.\n'); log.close()
