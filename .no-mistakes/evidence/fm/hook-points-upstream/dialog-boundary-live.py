import pathlib,subprocess,tempfile,os,json,shutil,tarfile,io
root=pathlib.Path.cwd(); evidence=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E')
lab=pathlib.Path(tempfile.mkdtemp(prefix='fm-lab.',dir=root)); log=open(evidence/'dialog-boundary-live.log','w')
try:
 subprocess.run(['bin/fm-lab-home.sh','create',str(lab)],check=True,capture_output=True)
 primary=lab/'primary'; primary.mkdir()
 archive=subprocess.check_output(['git','archive','HEAD','bin','.claude','AGENTS.md'])
 with tarfile.open(fileobj=io.BytesIO(archive)) as f: f.extractall(primary,filter='data')
 subprocess.run(['git','init','-q',str(primary)],check=True)
 env=os.environ.copy()
 for key in list(env):
  if key.startswith('FM_') or key in ['GROK_AGENT','GROK_HOOK_EVENT']: env.pop(key,None)
 env.update(FM_HOME=str(lab),CLAUDE_PROJECT_DIR=str(primary),TMPDIR=str(lab))
 settings=json.loads((primary/'.claude/settings.json').read_text())
 for event in ['prompt-submit','stop','turn-end']:
  d=lab/'hooks'/f'{event}.d';d.mkdir(parents=True)
  h=d/'10-capture';h.write_text('#!/bin/sh\njq -c --arg event "$FM_HOOK_EVENT" \'{event:$event,payload:.}\' >> "$FM_HOME/dialog-events.jsonl"\n'+('echo lab-turn-obligation >&2; exit 1\n' if event=='turn-end' else 'echo must-not-reach-model; echo test-module-failure >&2; exit 7\n'));h.chmod(0o755)
 def invoke(command,payload,expected=0,overrides=None):
  e=env.copy();e.update(overrides or {})
  p=subprocess.run(['bash','-c',command],input=json.dumps(payload),env=e,text=True,capture_output=True,timeout=15)
  log.write('$ '+command+'\ninput: '+json.dumps(payload)+'\nstdout: '+p.stdout+'\nstderr: '+p.stderr+f'\nexit={p.returncode}\n');log.flush()
  assert p.returncode==expected
  return p
 commands={}
 for native,event in [('UserPromptSubmit','prompt-submit'),('Stop','stop')]:
  commands[native]=next(h['command'] for item in settings['hooks'][native] for h in item['hooks'] if 'fm-dialog-hooks.sh' in h.get('command',''))
  payload={'hook_event_name':native,'session_id':'live-boundary-session','prompt_id':'p1','prompt':'literal :=null\nquoted " text\n\n','last_assistant_message':'Completed lab verification.','stop_hook_active':False}
  p=invoke(commands[native],payload)
  assert p.stdout==p.stderr==''
 rows=[json.loads(s) for s in (lab/'dialog-events.jsonl').read_text().splitlines()]
 assert rows[0]['payload']['prompt']=='literal :=null\nquoted " text\n\n'
 assert rows[1]['payload']['last_assistant_message']=='Completed lab verification.'
 assert rows[0]['event']=='prompt-submit' and rows[1]['event']=='stop'
 before=(lab/'dialog-events.jsonl').read_text()
 # Real task-worktree gate root, foreign host, unrelated native event all no-op.
 invoke(commands['UserPromptSubmit'],{'hook_event_name':'UserPromptSubmit','prompt':'ignored'},overrides={'CLAUDE_PROJECT_DIR':str(root)})
 invoke(commands['UserPromptSubmit'],{'hook_event_name':'UserPromptSubmit','cursor_version':'1.7','prompt':'ignored'})
 invoke(commands['UserPromptSubmit'],{'hook_event_name':'SessionStart','prompt':'ignored'})
 assert before==(lab/'dialog-events.jsonl').read_text()
 guard=str(primary/'bin/fm-turnend-guard.sh')+' --claude'
 p=invoke(guard,{'session_id':'live-turn','transcript_path':'/lab/transcript.jsonl','stop_hook_active':False},2)
 assert 'lab-turn-obligation' in p.stderr
 before=(lab/'dialog-events.jsonl').read_text()
 invoke(guard,{'session_id':'live-turn','stop_hook_active':True})
 assert before==(lab/'dialog-events.jsonl').read_text()
 shutil.copy(lab/'dialog-events.jsonl',evidence/'dialog-boundary-events.jsonl')
 shutil.copy(lab/'state/.fm-hooks.log',evidence/'dialog-module-failures.log')
 log.write('Registered command boundary assertions passed; payloads were supplied through stdin, not by a real Claude turn.\n')
finally:
 shutil.rmtree(lab);log.write('Disposable source snapshot and home removed.\n');log.close()
