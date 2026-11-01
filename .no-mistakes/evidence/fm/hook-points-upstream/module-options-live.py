import pathlib,os,json,tempfile,subprocess,shutil
root=pathlib.Path.cwd(); e=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AFV2JT51JFYKCMSN0A2E6E'); lab=pathlib.Path(tempfile.mkdtemp(prefix='fm-lab.',dir=root)); log=open(e/'module-options-live.log','w')
try:
 subprocess.run(['bin/fm-lab-home.sh','create',str(lab)],check=True,capture_output=True)
 env=os.environ.copy()
 for k in list(env):
  if k.startswith('FM_'): env.pop(k,None)
 env.update(FM_HOME=str(lab),TMPDIR=str(lab),FM_HOOKS_EXTRA_DIR=str(lab/'extra'),FM_HOOK_MIRROR=str(lab/'mirror.jsonl'))
 for directory,name,body in [('hooks','20-second','{"route":{"team":"operations"}}'),('hooks','10-first','{"route":{"team":"finance"},"accepted":true}'),('extra','05-extra','{"route":{"queue":"lab"}}')]:
  folder=lab/directory/'pre-spawn.d'; folder.mkdir(parents=True,exist_ok=True)
  f=folder/name;f.write_text('#!/bin/sh\nprintf \'%s\\n\' '+"'"+body+"'"+'\n');f.chmod(0o755)
 def run(event,data,extra=None):
  en=env.copy();en.update(extra or {})
  p=subprocess.run(['bin/fm-hooks.sh','run',event],input=data,env=en,capture_output=True,text=True,timeout=15)
  log.write('event='+event+'\nstdout='+p.stdout+'stderr='+p.stderr+f'exit={p.returncode}\n');log.flush();return p
 p=run('pre-spawn','{"task_id":"module-policy"}')
 assert p.returncode==0 and json.loads(p.stdout)=={'route':{'team':'finance','queue':'lab'},'accepted':True}
 assert 'conflict on route.team: kept 10-first, ignored 20-second' in p.stderr
 assert 'finance' not in p.stderr and 'operations' not in p.stderr
 p=run('pre-spawn','{}',{'FM_HOOK_MERGE_CONFLICT':'refuse'});assert p.returncode==3 and p.stdout==''
 text='lab private example\n'+('x'*5000)
 p=run('prompt-submit',json.dumps({'prompt':text,'session_id':'s1','prompt_id':'p1'}));assert p.returncode==0
 row=json.loads((lab/'mirror.jsonl').read_text().splitlines()[-1]);assert 'text' not in row['dialog'] and row['dialog']['text_chars']==len(text)
 p=run('stop',json.dumps({'last_assistant_message':text,'session_id':'s1','generation_id':'g1'}),{'FM_HOOK_MIRROR_TEXT':'1'});assert p.returncode==0
 row=json.loads((lab/'mirror.jsonl').read_text().splitlines()[-1]);assert len(row['dialog']['text'])<=4000 and 'characters cut' in row['dialog']['text']
 shutil.copy(lab/'mirror.jsonl',e/'module-options-mirror.jsonl')
 log.write('Lexical/home-first order, extra-directory merge, conflict refusal and dialog mirror privacy/capping assertions passed.\n')
finally:
 shutil.rmtree(lab);log.write('Disposable module installation removed.\n');log.close()
