import os,pathlib,subprocess,shutil,json
root=pathlib.Path.cwd();home=root/'.test-spawn-refusal';ev=pathlib.Path('/home/kingstyle/.no-mistakes/evidence/01M6AKTC8RC41CSCCVA0619230')
env={k:v for k,v in os.environ.items() if not k.startswith('FM_') and k!='TMUX'};env.update(FM_HOME=str(home),TMPDIR=str(root/'.test-tmp'),TMUX=str(ev/'unused-lab-socket')+',1,0')
try:
 assert not home.exists();subprocess.run([str(root/'bin/fm-lab-home.sh'),'create',str(home)],env=env,check=True,capture_output=True)
 project=home/'projects/lab';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True,capture_output=True)
 hook=home/'hooks/pre-spawn.d/10-capacity';hook.parent.mkdir(parents=True);hook.write_text('#!/bin/sh\ncat > "$FM_HOME/state/spawn-payload.json"\necho "external module: worker capacity reached" >&2\nexit 1\n');hook.chmod(0o755)
 command=[str(root/'bin/fm-spawn.sh'),'refused-task',str(project),'--mode','local-only','--yolo','off','--harness','claude','--backend','tmux']
 p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=40)
 payload=home/'state/spawn-payload.json'
 (ev/'spawn-refusal-transcript.log').write_text(json.dumps({'command':command,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'module_payload':json.loads(payload.read_text()) if payload.exists() else None,'task_metadata_created':(home/'state/refused-task.meta').exists()},indent=2)+'\n')
 assert p.returncode==3 and 'worker capacity reached' in p.stderr and payload.exists() and not (home/'state/refused-task.meta').exists()
finally:
 if home.exists():shutil.rmtree(home)
