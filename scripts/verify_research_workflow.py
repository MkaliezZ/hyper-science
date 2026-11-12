"""Real HTTP/MCP workflow acceptance, optionally against the new frozen build."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
import httpx
import uvicorn
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from verify_research import fixture,request as v1,ROOT
from growth_local.web import create_app

def v2(op,p,pid,revision=None,key=None):
    value={'contract_version':'research.capability.v2','request_id':key or uuid4().hex,'capability':'research.'+op,'project_id':pid,'input':p}
    if revision is not None:value['expected_revision']=revision
    return value

async def main(frozen=None,external=False,tag='source'):
    runtime,host,folder,material=fixture();checks=[];network=[];process=None;server=None;serving=None
    if frozen:
        executable=Path(frozen).resolve();assert executable.is_file()
        process=subprocess.Popen([str(executable),'--web','--no-browser','--data',str(folder)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
        for _ in range(300):
            launch=folder/'qa-launch-url.txt'
            if launch.exists():break
            if process.poll() is not None:raise RuntimeError('Frozen program exited during startup')
            await asyncio.sleep(.1)
        else:raise RuntimeError('Frozen startup did not become ready')
        port=int(json.loads((folder/'running.json').read_text())['port'])
    else:
        app=create_app(folder,runtime=host,network=False);sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128);port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False));serving=asyncio.create_task(server.serve(sockets=[sock]))
        for _ in range(200):
            if server.started:break
            await asyncio.sleep(.05)
    headers={'Authorization':'Bearer '+runtime.service.base.owner_token};base='http://127.0.0.1:'+str(port)
    async def mcp(raw,web=False):
        async def run(session):
            await session.initialize();result=await session.call_tool('invoke_research_capability',{'request':raw});assert not result.isError,str(result.content)
            return result.structuredContent or json.loads(result.content[0].text)
        if web:
            async with streamablehttp_client(base+'/mcp/',headers=headers) as (read,write,_):
                async with ClientSession(read,write) as session:return await run(session)
        command=str(executable.parent/'HyperGrowthResearchMCP.exe') if frozen else sys.executable
        args=['--mcp','--data',str(folder)] if frozen else ['-m','growth_local','--mcp','--data',str(folder)]
        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUTF8':'1'}
        async with stdio_client(StdioServerParameters(command=command,args=args,env=env)) as (read,write):
            async with ClientSession(read,write) as session:return await run(session)
    try:
        async with httpx.AsyncClient(base_url=base,headers=headers,timeout=60,trust_env=False) as client:
            async def cap(raw):
                response=await client.post('/api/local/capabilities/invoke',json=raw);response.raise_for_status();return response.json()
            async def read(pid):return (await cap(v1('project.read',project=pid)))['result']
            async def use(pid,op,p=None,key=None):return await cap(v2(op,p or {},pid,(await read(pid))['project']['revision'],key))
            async def wait(pid,jid):
                for _ in range(600):
                    j=(await use(pid,'job.get',{'job_id':jid}))['result']['job']
                    if j['state'] not in ['queued','running']:return j
                    await asyncio.sleep(.1)
                raise RuntimeError('Job exceeded verification deadline')
            async def job(pid,task,parameters):
                started=(await use(pid,'job.start',{'task':task,'parameters':parameters}))['result']['job']
                done=await wait(pid,started['id']);assert done['state']=='succeeded',done;return done
            pid=(await cap(v1('project.create',{'title':'合成工程验收：食堂排队','method':'simulation'})))['result']['project']['id']
            await cap(v1('problem.save',{'question':'合成模型中不同窗口配置如何影响等待？','context':'非现实调查','goal':'比较模型输出','constraints':'合成参数、固定模型'},pid,0))
            raw=v2('source.save',{'title':'合成参数依据','text':'合成示例参数：平均到达间隔4分钟，平均服务6分钟。','provenance':'synthetic'},pid,1,'three-entry-source')
            saved=await cap(raw);assert await mcp(raw)==saved and await mcp(raw,True)==saved
            checks.append('v2 HTTP, independent stdio MCP and HTTP MCP share same idempotent write and immutable refs')
            source=saved['refs'][0]
            parameters={'title':'UTF8原件','filename':'fixture.txt','base64':base64.b64encode('合成原件：食堂排队的文字记录。'.encode()).decode(),'provenance':'synthetic'}
            parsed=await job(pid,'source.parse',parameters);original=(await use(pid,'source.original',{'ref':parsed['result_ref']}))['result']
            assert base64.b64decode(original['base64']).decode().startswith('合成原件')
            matches=(await use(pid,'search.local',{'query':'食堂排队'}))['result']['matches'];assert matches and matches[0]['ref']['project_id']==pid
            checks.append('actual UTF8 parse, original retrieval and bounded current-project lexical search')
            linked=await cap(v1('companion.link',{'subject':'english','material_id':material['id'],'revision':material['revision'],'source_hash':material['source_hash']},pid,(await read(pid))['project']['revision']))
            assert host.current()=='mathematics'
            other=(await cap(v1('project.create',{'title':'另一个隔离项目'})))['result']['project']['id']
            denied=await client.post('/api/local/capabilities/invoke',json=v2('asset.resolve',{'ref':source},other));assert denied.status_code==403
            checks.append('companion source is explicit; math workspace unchanged; cross-project refs denied over HTTP')
            direction=await use(pid,'direction.save',{'title':'独立思考','independent_ideas':'先观察，再比较配置；另考虑分时进入。','criteria':'可验证和资源限制','rivals':'到达率不同'})
            await job(pid,'direction.scaffold',{'direction_ref':direction['refs'][0]})
            exp=await use(pid,'experiment.save',{'title':'排队模型比较','unit':'一次独立模拟重复','comparison':'2与3窗口','measurement':'已完成顾客的平均等待','independent_replication':'独立到达和服务随机流；顾客不是重复单位','randomization':'固定种子派生独立随机流','controls':'保持输入分布一致','disconfirming':'增加窗口未改善等待或损失率','analysis':'重复均值与区间','constraints':'没有现实校准'})
            expref=exp['refs'][0]
            await job(pid,'design.generate',{'experiment_ref':expref,'method':'blocked','n':20,'arms':['A','B'],'seed':7})
            sim=await job(pid,'simulation.run',{'experiment_ref':expref,'input_provenance':'synthetic','input_source':'合成验收参数；分钟','assumptions':'同质服务台、指数到达与服务、有限排队','horizon':60.0,'servers':[2,3],'replications':4})
            simulation=(await use(pid,'asset.resolve',{'ref':sim['result_ref']}))['result']['content']
            assert len(simulation['scenarios'])==2 and simulation['reality_validation']=='not_calibrated'
            checks.append('pinned brainstorming scaffold, blocked allocation and real bounded SimPy replications executed')
            quote='合成示例参数'
            report=await use(pid,'report.save',{'title':'合成研究简报','method':'明确参数来源，运行固定排队模型并比较重复结果',
                'claims':[{'text':'本轮模型使用合成示例参数，不能直接代表现实。','status':'finding','evidence':[{'ref':source,'start':0,'end':len(quote),'quote':quote,'relation':'supports'}]}],
                'limitations':'指数分布、有限时段与未完成顾客删失；尚无真实观察和现实校准','next_steps':'收集实际到达与服务数据','assistance':'已使用本地Skill程序；未使用真实模型服务'})
            await job(pid,'report.audit',{'ref':report['refs'][0]})
            await use(pid,'review.save',{'report_ref':report['refs'][0],'feedback':'补充相反解释，并保持模拟和现实分开','next_revision':'增加到达率敏感性比较'})
            exported=(await use(pid,'project.export',{'format':'markdown','report_ref':report['refs'][0]}))['result']['content'];assert source['sha256'] in exported
            full=(await use(pid,'project.export',{'format':'markdown'}))['result']['content'];assert '合成观察材料' in full or '三个服务窗口' in full
            checks.append('source-bound report, actual writing/causal-language checks, feedback and exports including linked companion material')
            for method in ['qualitative','humanities','design']:
                case=(await cap(v1('project.create',{'title':'合成方法验收-'+method,'method':method})))['result']['project']['id']
                plan=await use(case,'plan.save',{'title':'材料研究计划','method':method,'question':'不同情境如何形成不同理解？','materials':'合成材料，说明选择理由','procedure':'比较材料并保留不同声音','counterevidence':'寻找不支持当前解释的案例','analysis':'结合语境解释','limitations':'仅验证工程流程'})
                assert plan['checks']['domain_review']=='not_reviewed'
            checks.append('qualitative, humanities and design plans remain independent of experiment/statistics requirements')
            if external:
                searched=await job(pid,'search.remote',{'query':'queue simulation waiting time','providers':['crossref'],'limit':3})
                value=(await use(pid,'asset.resolve',{'ref':searched['result_ref']}))['result']['content']
                network=value['coverage'];assert any(c['status']=='succeeded' for c in network),network
                assert value['results'] and value['sent_to_provider']=='explicit_query_and_filters_only'
                checks.append('live public Crossref search returned bounded metadata; full text and exhaustive coverage not claimed')
            assert (await client.get('/research/')).status_code==200 and (await client.get('/assets/research-workflow.js')).status_code==200
            for name in ['research.js','research-workflow.js','research.css']:
                actual=await client.get('/assets/'+name);assert actual.content==(ROOT/'src/growth_local/static'/name).read_bytes(),name+' is stale in target'
            if frozen:
                actual=executable.parent/'_internal/base/app/research/functional/worker.py'
                assert actual.read_bytes()==(ROOT/'src/base/app/research/functional/worker.py').read_bytes(),'Frozen worker script is stale'
            modules=(await client.get('/api/local/modules')).json();assert len(modules['modules'])==5
            checks.append('research page and exact current static assets served; frozen worker matches source; five parallel modules preserved')
            allassets=(await read(pid))['assets'];assert len(allassets)>10
        sourcefiles=[*ROOT.glob('src/base/app/research/**/*.py'),*ROOT.glob('src/growth_local/static/research*'),ROOT/'src/growth_local/web.py',ROOT/'src/growth_local/mcp.py',ROOT/'requirements-research.lock']
        report={'ok':True,'date':'2026-11-03','phase':'D2-D6-engineering','synthetic_only':True,'real_user_data_modified':False,
                'model_service_called':False,'simulation_run':True,'domain_review':'not_reviewed','reality_calibration':'not_performed','public_deployment':False,
                'target':str(executable) if frozen else 'source-runtime','target_os':sys.platform,'checks':checks,'live_network':network,'data_folder':str(folder),
                'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sourcefiles}}
        output=ROOT/'artifacts'/('research-workflow-'+tag+'.json');output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'ok':True,'checks':len(checks),'artifact':str(output),'frozen':bool(frozen),'live_network':network},ensure_ascii=False))
    finally:
        if server:server.should_exit=True;await serving
        if process:
            try:
                async with httpx.AsyncClient(base_url=base,headers=headers,trust_env=False) as client:await client.post('/api/local/exit')
                process.wait(timeout=10)
            except Exception:
                if process.poll() is None:process.terminate();process.wait(timeout=5)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--frozen');p.add_argument('--external',action='store_true');p.add_argument('--tag',default='source');a=p.parse_args();asyncio.run(main(a.frozen,a.external,a.tag))
