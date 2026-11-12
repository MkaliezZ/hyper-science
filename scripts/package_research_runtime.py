"""Copy a local managed CPython plus the locked environment into a new build."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--distribution',type=Path,required=True);args=parser.parse_args()
    output=args.distribution.resolve()
    if not output.is_relative_to((ROOT/'dist').resolve()) or not (output/'HyperGrowthResearch.exe').is_file():raise ValueError('请选择本工程dist中的新科研验收构建')
    target=output/'research-runtime'
    if target.exists():raise ValueError('此构建已包含运行环境；请使用新的分发目录，保留原包')
    python=ROOT/'.venv-research/Scripts/python.exe'
    runtime=Path(subprocess.check_output([str(python),'-I','-c','import sys;print(sys.base_prefix)'],text=True).strip()).resolve()
    if runtime.name!='cpython-3.12.7-windows-x86_64-none' or not (runtime/'python.exe').is_file():raise ValueError('只接受已核对的uv托管CPython3.12.7运行时')
    shutil.copytree(runtime,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    packages=ROOT/'.venv-research/Lib/site-packages'
    shutil.copytree(packages,target/'Lib/site-packages',dirs_exist_ok=True,
       ignore=shutil.ignore_patterns('__pycache__','*.pyc','_virtualenv.py','_virtualenv.pth'))
    for source in [ROOT/'requirements-research.lock',ROOT/'docs/research-workflow-v02.md']:
        shutil.copy2(source,output/source.name)
    shutil.copy2(ROOT/'docs/research-third-party-notices.md',output/'THIRD_PARTY_RESEARCH.md')
    (output/'Start-Research-Acceptance.cmd').write_text('@echo off\r\nsetlocal\r\n"%~dp0HyperGrowthResearch.exe" --data "%LOCALAPPDATA%\\HyperGrowthResearchAcceptance\\v0.2"\r\n',encoding='ascii',newline='')
    (output/'开始验收.txt').write_text('超维科研 v0.2 工程验收包\n\n双击 Start-Research-Acceptance.cmd。首次设置本人身份，再点击“超维科研”。\n此快捷入口使用独立验收数据目录，不读取或迁移原伴学数据。需要复用既有资料时，可在验收空间显式恢复加密备份后核对。\n\n伴学与科研平行独立。科研按项目保存，伴学按学科保存；只读联动资料须明确选择。\n已附本地科研运行环境。AI探索需要使用者自己的模型配置。\n\n完整操作说明见 research-workflow-v02.md。当前为本机Windows工程验收，真实模型服务、领域审定与现实校准另验；未公开部署。\n',encoding='utf-8-sig')
    info={'python_source':'uv managed CPython 3.12.7 standalone installation','environment':'requirements-research.lock',
          'status':'engineering_acceptance_candidate','files':{}}
    for path in output.rglob('*'):
        if path.is_file():info['files'][str(path.relative_to(output)).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
    (output/'research-distribution-manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'distribution':str(output),'files':len(info['files']),'runtime_included':True},ensure_ascii=False))

if __name__=='__main__':main()
