exec(open('.gate-live/cli-scenarios.py').read().split('try:\n events=')[0].replace("lab=root/'.gate-live/cli-home'","lab=root/'.gate-live/spawn-home'"))
try:
 project=lab/'projects'/'disposable'; project.mkdir()
 run(['git','init','-q','-b','main',str(project)])
 run(['git','-C',str(project),'-c','user.name=Validation','-c','user.email=validation@example.invalid','commit','--allow-empty','-qm','fixture'])
 d=lab/'data'/'admission'; d.mkdir(); (d/'brief.md').write_text('# Disposable admission check\nDo not launch.\n')
 hook('pre-spawn','10-deny','cat > "$FM_HOME/state/admission-payload.json"; echo "disposable capacity reached" >&2; exit 1')
 p=run(['bash','bin/fm-spawn.sh','admission',str(project),'--mode','local-only','--yolo','off','--harness','claude'])
 assert p.returncode==3 and 'disposable capacity reached' in p.stdout+p.stderr, p.stdout+p.stderr
 assert not (lab/'state'/'admission.meta').exists()
 out.append('Admission refused with no task record; payload: '+(lab/'state'/'admission-payload.json').read_text())
finally:
 (ev/'live-pre-spawn.txt').write_text('\n\n'.join(out))
