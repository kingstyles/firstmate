import os, pathlib, shutil, subprocess, json, time, signal
root = pathlib.Path.cwd()
evidence = pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AKTC8RC41CSCCVA0619230')
lab = root / '.test-live'
baseenv = {k:v for k,v in os.environ.items() if not k.startswith('FM_') and k not in ('TMUX','PI_CODING_AGENT','CURSOR_AGENT','CURSOR_INVOKED_AS')}
baseenv['TMPDIR'] = str(root / '.test-tmp')
processes=[]
log=open(evidence/'live-cli-transcript.log','w',buffering=1)
def record(label,value):
    log.write(label+'\n'+(value if isinstance(value,str) else json.dumps(value,indent=2))+'\n')
def run(args,payload='',env=None,timeout=25):
    p=subprocess.run([str(x) for x in args],input=payload,text=True,capture_output=True,env=env or baseenv,timeout=timeout)
    return p
try:
    assert not lab.exists()
    p=run([root/'bin/fm-lab-home.sh','create',lab]); assert p.returncode==0,p.stderr
    # Exact executable product files in a disposable plain-checkout fixture;
    # no fake harness, watcher, arm, or hook runner is installed.
    shutil.copytree(root/'bin',lab/'bin')
    shutil.copyfile(root/'AGENTS.md',lab/'AGENTS.md')
    subprocess.run(['git','init','-q',str(lab)],check=True,capture_output=True)
    env=baseenv|{'FM_HOME':str(lab),'TMUX':str(evidence/'unused-lab-socket')+',1,0'}
    def hook(event,name,body):
        path=lab/'hooks'/f'{event}.d'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('#!/bin/sh\n'+body+'\n'); path.chmod(0o755)
        return path
    hook('turn-end','10-module','cat >> "$FM_HOME/state/turn-payloads.jsonl"; echo >> "$FM_HOME/state/turn-payloads.jsonl"; echo "finish the owed reply first" >&2; exit 1')
    def agy(session,reason='NO_TOOL_CALL'):
        payload=json.dumps({'sessionId':session,'executionNum':1,'terminationReason':reason})
        p=run([lab/'bin/fm-turnend-guard-agy.sh'],payload,env)
        record('Antigravity Stop input '+payload,{'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        assert p.returncode==0
        return json.loads(p.stdout)
    assert agy('session-A')['decision']=='continue'
    assert (lab/'state/.turnend-hook-held').read_text()=='session-A'
    assert agy('session-A')=={}
    assert not (lab/'state/.turnend-hook-held').exists()
    assert agy('session-A')['decision']=='continue'
    assert agy('session-A','USER_CANCELED')=={}
    assert not (lab/'state/.turnend-hook-held').exists()
    assert agy('session-A')['decision']=='continue'
    assert agy('session-A','ERROR')=={}
    assert not (lab/'state/.turnend-hook-held').exists()
    assert agy('session-A')['decision']=='continue'
    assert agy('session-B')['decision']=='continue'
    record('Persisted turn-end module payloads', (lab/'state/turn-payloads.jsonl').read_text())
    for count in (0,1):
        payload=json.dumps({'session_id':'cursor-A','loop_count':count})
        p=run([lab/'bin/fm-turnend-guard-cursor.sh'],payload,env)
        record('Cursor stop input '+payload,{'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        assert p.returncode==0
        if count==0: assert 'finish the owed reply first' in json.loads(p.stdout)['followup_message']
        else: assert not p.stdout
    hook('prompt-submit','10-dialog','cat > "$FM_HOME/state/prompt.json"; echo must-not-reach-model; exit 7')
    hook('stop','10-dialog','cat > "$FM_HOME/state/stop.json"; echo must-not-reach-model; exit 7')
    for event,textkey in [('UserPromptSubmit','prompt'),('Stop','last_assistant_message')]:
        payload={'hook_event_name':event,'session_id':'dialog-A',textkey:'Exact text\nwith "quotes" and := null\n'}
        p=run([lab/'bin/fm-dialog-hooks.sh','claude'],json.dumps(payload),env)
        name='prompt' if event=='UserPromptSubmit' else 'stop'
        stored=json.loads((lab/f'state/{name}.json').read_text())
        record('Dialog command '+event,{'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'module_payload':stored})
        assert p.returncode==0 and p.stdout=='' and p.stderr=='' and stored[textkey]==payload[textkey]
    # Linked worker checkout is intentionally excluded from primary dialog.
    p=run([root/'bin/fm-dialog-hooks.sh','claude'],json.dumps({'hook_event_name':'UserPromptSubmit','prompt':'worker-secret'}),env)
    assert p.returncode==0 and p.stdout==''
    assert json.loads((lab/'state/prompt.json').read_text())['prompt']!='worker-secret'
    record('Linked worker dialog boundary',{'exit':p.returncode,'stdout':p.stdout,'primary_module_unchanged':True})
    # Real watcher processes: no tmux or forge replacements, no real fleet data.
    for event in ('watch-tick','heartbeat'):
        hook(event,'10-slow','printf "%s start %s\\n" "$FM_HOOK_EVENT" "$$" >> "$FM_HOME/state/watcher-events"; sleep 3; printf "%s end %s\\n" "$FM_HOOK_EVENT" "$$" >> "$FM_HOME/state/watcher-events"')
    watchenv=env|{'FM_POLL':'0.2','FM_CHECK_INTERVAL':'999999','FM_HEARTBEAT':'1','FM_HEARTBEAT_MAX':'1','FM_HOOK_TIMEOUT':'8'}
    streams=[]
    def startwatch(number):
        f=open(evidence/f'watcher-{number}.log','w'); streams.append(f)
        p=subprocess.Popen([str(root/'bin/fm-watch.sh')],env=watchenv,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(p);return p
    def until(fn):
        end=time.monotonic()+20
        while time.monotonic()<end:
            if fn():return
            time.sleep(.1)
        raise AssertionError('condition not reached')
    events=lab/'state/watcher-events'
    first=startwatch(1)
    until(lambda: events.exists() and 'heartbeat start' in events.read_text() and 'watch-tick start' in events.read_text())
    first.send_signal(signal.SIGTERM)
    # A new watcher starts while the old one is still joining slow module runs.
    second=startwatch(2)
    first.wait(timeout=20)
    second.wait(timeout=20)
    record('Concurrent replacement while old hooks drain', {'exit':second.returncode,'output':(evidence/'watcher-2.log').read_text()})
    second=startwatch(3)
    until(lambda: len([x for x in events.read_text().splitlines() if x.startswith('watch-tick start')])>=2)
    second.send_signal(signal.SIGTERM);second.wait(timeout=20)
    rows=events.read_text().splitlines();record('Real watcher handoff module trace',rows)
    for event in ('watch-tick','heartbeat'):
        active=set()
        for row in rows:
            e,phase,pid=row.split()
            if e!=event:continue
            if phase=='start': assert not active,('overlapping modules',rows); active.add(pid)
            else: assert pid in active;active.remove(pid)
        assert not active
    record('Watcher exits',{'first':first.returncode,'second':second.returncode,'no_overlapping_modules':True,'all_module_runs_completed':True})
    for f in streams:f.close()
    record('RESULT','All direct public-interface checks passed; native harness launch was not simulated.')
finally:
    for p in processes:
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    if lab.exists():shutil.rmtree(lab)
    log.close()
