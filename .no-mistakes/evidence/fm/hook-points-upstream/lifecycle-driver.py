import os, pathlib, shutil, subprocess, json
root=pathlib.Path.cwd(); ev=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AKTC8RC41CSCCVA0619230'); lab=root/'.test-lifecycle'
env={k:v for k,v in os.environ.items() if not k.startswith('FM_') and k not in ('TMUX','TASKS_AXI_FILE','TASKS_AXI_BACKEND')}
env.update(FM_HOME=str(lab),TMPDIR=str(root/'.test-tmp'),TMUX=str(ev/'unused-lab-socket')+',1,0')
log=open(ev/'lifecycle-transcript.log','w',buffering=1)
def run(args,payload='',timeout=45):
    p=subprocess.run([str(x) for x in args],input=payload,env=env,text=True,capture_output=True,timeout=timeout)
    log.write('COMMAND '+ ' '.join(str(x) for x in args)+'\n'+json.dumps({'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})+'\n');return p
def hook(event,name,body):
    f=lab/'hooks'/f'{event}.d'/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755);return f
try:
    assert not lab.exists();assert run([root/'bin/fm-lab-home.sh','create',lab]).returncode==0
    shutil.copytree(root/'bin',lab/'bin');shutil.copytree(root/'docs',lab/'docs');shutil.copyfile(root/'AGENTS.md',lab/'AGENTS.md')
    subprocess.run(['git','init','-q',str(lab)],check=True,capture_output=True)
    (lab/'config/supervision-host-off').touch();(lab/'config/backlog-backend').write_text('manual\n')
    hook('session-start','10-context','cat > "$FM_HOME/state/session-payload.json"; echo "external module context: lab enabled"')
    p=run([lab/'bin/fm-session-start.sh','--reemit'],timeout=150)
    assert p.returncode==0 and 'external module context: lab enabled' in p.stdout
    log.write('SESSION MODULE PAYLOAD '+(lab/'state/session-payload.json').read_text()+'\n')
    hook('intake','10-route','cat > "$FM_HOME/state/intake-payload.json"; echo \'{"route":"operations","owner":"external-module"}\'')
    p=run([root/'bin/fm-inbox.sh','note','--request-id','hooks-validation','Inspect the disposable room checklist'])
    assert p.returncode==0
    p=run([root/'bin/fm-wake-drain.sh']);assert p.returncode==0 and 'INTAKE inbox:' in p.stdout and '"route":"operations"' in p.stdout
    log.write('INTAKE MODULE PAYLOAD '+(lab/'state/intake-payload.json').read_text()+'\n')
    hook('pre-merge','10-freeze','cat > "$FM_HOME/state/premerge-payload.json"; echo "release freeze in disposable lab" >&2; exit 1')
    meta=lab/'state/merge-task.meta';meta.write_text('window=fm:lab\nproject=lab\nworktree='+str(lab/'projects/lab')+'\n')
    p=run([root/'bin/fm-pr-merge.sh','merge-task','https://github.com/example/lab/pull/1'])
    assert p.returncode==3 and 'release freeze in disposable lab' in p.stderr and 'pr=' not in meta.read_text()
    log.write('PRE-MERGE MODULE PAYLOAD '+(lab/'state/premerge-payload.json').read_text()+'\n')
    hook('post-merge','10-record','cat >> "$FM_HOME/state/postmerge-payloads.jsonl"; echo >> "$FM_HOME/state/postmerge-payloads.jsonl"')
    p=run(['bash','-c','. "$1/bin/fm-merge-outcome-lib.sh"; for origin in self poll poll; do fm_merge_outcome_report "$FM_HOME" "$FM_HOME/state" recorded-merge https://github.com/example/lab/pull/2 "$origin" || exit; done','_',str(root)])
    assert p.returncode==0
    rows=[x for x in (lab/'state/postmerge-payloads.jsonl').read_text().splitlines() if x.strip()];assert len(rows)==1
    log.write('DEDUPLICATED MERGE MODULE OUTPUT '+rows[0]+'\n')
    shutil.rmtree(lab/'state'); (lab/'state').mkdir()
    # Reproduce the latest reported failure with the executable predecessor,
    # then replay the same input sequence against the corrected adapter.
    hook('turn-end','10-refuse','cat >/dev/null; echo "owed module action" >&2; exit 1')
    fixed=(lab/'bin/fm-turnend-guard-agy.sh').read_bytes()
    previous=subprocess.run(['git','show','d86caa33:bin/fm-turnend-guard-agy.sh'],check=True,capture_output=True).stdout
    for version,body in [('before-fix',previous),('fixed',fixed)]:
        (lab/'bin/fm-turnend-guard-agy.sh').write_bytes(body)
        (lab/'state/.turnend-hook-held').unlink(missing_ok=True)
        observations=[]
        for reason in ('NO_TOOL_CALL','USER_CANCELED','NO_TOOL_CALL'):
            p=run([lab/'bin/fm-turnend-guard-agy.sh'],json.dumps({'sessionId':'regression-session','terminationReason':reason}))
            assert p.returncode==0;observations.append(json.loads(p.stdout))
        log.write(version+' cancellation replay '+json.dumps(observations)+'\n')
        assert observations[0]['decision']=='continue' and observations[1]=={}
        if version=='before-fix':assert observations[2]=={}
        else:assert observations[2]['decision']=='continue'
    log.write('RESULT All lifecycle command checks passed; predecessor reproduced the cancellation regression.\n')
finally:
    if lab.exists():shutil.rmtree(lab)
    log.close()
