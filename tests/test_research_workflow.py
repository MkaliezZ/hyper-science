"""Workflow scope, negative evidence checks and real curated helper execution."""
import asyncio
import base64
import json
import threading
import time
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from test_local_runtime import instance
from test_research_foundation import create,call,read
from base.app.research.functional import jobs,storage,executors
from base.app.research.functional.contracts_v2 import Request,Result
from growth_local.web import create_app
from growth_local.mcp import create_mcp

def synthetic_pdf():
    stream=b'BT /F1 12 Tf 72 720 Td (SYNTHETIC RESEARCH PDF) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
      b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    raw=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(raw));raw+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    pos=len(raw);raw+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets[1:])
    return raw+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(pos).encode()+b'\n%%EOF\n'

def raw(op,p,pid,revision=None,key=None):
    r={'contract_version':'research.capability.v2','request_id':key or uuid4().hex,'capability':'research.'+op,'project_id':pid,'input':p}
    if revision is not None:r['expected_revision']=revision
    return r

def v2(r,pid,op,p=None,key=None):
    revision=call(r,'project.read',project=pid)['result']['project']['revision']
    return r.invoke_capability(raw(op,p or {},pid,revision,key))

def job(r,pid,task,p):return v2(r,pid,'job.start',{'task':task,'parameters':p})['result']['job']

def wait(r,pid,jid):
    started=time.monotonic()
    while time.monotonic()-started<60:
        value=v2(r,pid,'job.get',{'job_id':jid})['result']['job']
        if value['state'] not in jobs.ACTIVE:return value
        time.sleep(.08)
    pytest.fail('Job did not complete within bounded test time')

def experiment(r,pid):
    return v2(r,pid,'experiment.save',{'title':'合成排队比较','unit':'一次模拟独立重复',
       'comparison':'比较2和3窗口','measurement':'有限时限内已完成顾客的平均等待',
       'independent_replication':'每次独立到达/服务随机流；顾客并非独立重复'})['refs'][0]

def test_source_search_versions_exact_quotes_and_cross_project(tmp_path):
    r=instance(tmp_path,'student','S');p=create(r);pid=p['id'];other=create(r)
    value=v2(r,pid,'source.save',{'title':'合成田野笔记','text':'食堂排队问题。午间窗口队伍较长。','provenance':'synthetic'})
    ref=value['refs'][0]
    matches=v2(r,pid,'search.local',{'query':'午间排队'})['result']['matches'];assert matches and matches[0]['quote'].startswith('食堂')
    assert not v2(r,other['id'],'search.local',{'query':'排队'})['result']['matches']
    with pytest.raises(PermissionError):v2(r,other['id'],'asset.resolve',{'ref':ref})
    b={'title':'研究简报','method':'材料分析','claims':[{'text':'笔记中记录午间队伍较长','status':'finding',
       'evidence':[{'ref':ref,'start':0,'end':7,'quote':'食堂排队问题。','relation':'supports'}]}],
       'limitations':'仅有合成示例，不能推断现实','next_steps':'补充真实观察'}
    report=v2(r,pid,'report.save',b);assert report['checks']['quote_integrity']=='checked'
    bad=json.loads(json.dumps(b));bad['claims'][0]['evidence'][0]['quote']='编造引文'
    with pytest.raises(ValueError,match='字符位置'):v2(r,pid,'report.save',bad)
    updated=v2(r,pid,'source.save',{'asset_id':ref['asset_id'],'title':'新版本','text':'另一个窗口的新观察'})
    assert updated['refs'][0]['revision']==2
    assert not v2(r,pid,'search.local',{'query':'午间'})['result']['matches']
    assert v2(r,pid,'asset.resolve',{'ref':ref})['result']['selection'].startswith('食堂')
    exported=v2(r,pid,'project.export',{'format':'markdown','report_ref':report['refs'][0]})['result']['content']
    assert ref['sha256'] in exported and '合成' in exported
    no_support=v2(r,pid,'report.save',{**b,'claims':[{'text':'暂定想法','status':'hypothesis','evidence':[]}]})
    assert no_support['checks']['unlinked_claims']==[1]

def test_metadata_not_claim_evidence_and_source_scope(tmp_path):
    r=instance(tmp_path,'student','S');pid=create(r)['id']
    ref=v2(r,pid,'source.save',{'title':'仅有题名','text':'排队研究题名','content_scope':'metadata'})['refs'][0]
    with pytest.raises(ValueError,match='元数据'):
        v2(r,pid,'report.save',{'title':'不能成立的报告','method':'没有读全文','claims':[{'text':'有改善','status':'finding','evidence':[{'ref':ref,'start':0,'end':2,'quote':'排队','relation':'supports'}]}],'limitations':'未知'})

def test_real_text_parse_original_idempotent_job_and_cancel_retry(tmp_path,monkeypatch):
    r=instance(tmp_path,'student','S');pid=create(r)['id'];text='合成原件\n访谈与设计改进。'
    request=raw('job.start',{'task':'source.parse','parameters':{'title':'合成原件','filename':'notes.txt','base64':base64.b64encode(text.encode()).decode()}},pid,0,'once')
    first=r.invoke_capability(request)['result']['job'];assert r.invoke_capability(request)['result']['job']['id']==first['id']
    done=wait(r,pid,first['id']);assert done['state']=='succeeded',done
    original=v2(r,pid,'source.original',{'ref':done['result_ref']})['result'];assert base64.b64decode(original['base64']).decode()==text
    assert '_original_base64' not in read(r,{'id':pid})['assets'][0]['content']
    original_execute=executors.execute_worker
    def block(task,p,cancel,heartbeat=lambda:None,**kwargs):
        if task=='source.parse':
            for _ in range(100):
                if cancel.wait(.01):raise executors.Cancelled('cancel test')
        return original_execute(task,p,cancel,heartbeat,**kwargs)
    monkeypatch.setattr(executors,'execute_worker',block)
    slow=job(r,pid,'source.parse',request['input']['parameters'])
    assert v2(r,pid,'job.cancel',{'job_id':slow['id']})['result']['job']['state']=='cancelled'
    assert wait(r,pid,slow['id'])['result_ref'] is None
    retried=v2(r,pid,'job.retry',{'job_id':slow['id']})['result']['job']
    assert retried['retry_of']==slow['id'] and wait(r,pid,retried['id'])['state']=='succeeded'

def test_real_scaffold_experimental_design_and_simpy_reproducibility(tmp_path):
    r=instance(tmp_path,'teacher','T');pid=create(r,method='simulation')['id']
    direction=v2(r,pid,'direction.save',{'title':'本人方向','independent_ideas':'先观察高峰，再比较窗口配置。'})['refs'][0]
    scaffold=wait(r,pid,job(r,pid,'direction.scaffold',{'direction_ref':direction})['id'])
    assert scaffold['state']=='succeeded',scaffold
    content=v2(r,pid,'asset.resolve',{'ref':scaffold['result_ref']})['result']['content']
    assert content['register']['ideas']==[] and content['register']['workflow'][1]['stage']=='independent-generation'
    ref=experiment(r,pid)
    design=wait(r,pid,job(r,pid,'design.generate',{'experiment_ref':ref,'method':'factorial','factors':{'窗口':[2,3],'到达间隔':[3,5]}})['id'])
    assert design['state']=='succeeded',design
    assert len(v2(r,pid,'asset.resolve',{'ref':design['result_ref']})['result']['content']['rows'])==4
    parameters={'experiment_ref':ref,'input_provenance':'synthetic','input_source':'工程测试','assumptions':'指数分布，仅合成示例','servers':[2,3],'replications':3,'horizon':30.0}
    outputs=[]
    for _ in range(2):
        done=wait(r,pid,job(r,pid,'simulation.run',parameters)['id']);assert done['state']=='succeeded',done
        outputs.append(v2(r,pid,'asset.resolve',{'ref':done['result_ref']})['result']['content'])
    assert outputs[0]['scenarios']==outputs[1]['scenarios']
    assert outputs[0]['reality_validation']=='not_calibrated'
    with pytest.raises(ValueError):job(r,pid,'simulation.run',{**parameters,'servers':[0]})
    with pytest.raises(ValueError):job(r,pid,'simulation.run',{**parameters,'max_events':100000,'replications':30})
    with pytest.raises(ValueError,match='实测'):job(r,pid,'simulation.run',{**parameters,'input_provenance':'observed'})

def test_remote_search_partial_limits_and_no_private_context():
    urls=[]
    def handler(request):
        urls.append(str(request.url))
        if request.url.host=='api.openalex.org':return httpx.Response(429)
        return httpx.Response(200,json={'message':{'total-results':100,'items':[{'title':['Synthetic queue'],'DOI':'10.0/x','published':{'date-parts':[[2026]]}}]}})
    def factory(**kwargs):return httpx.Client(transport=httpx.MockTransport(handler),**kwargs)
    result=executors.remote_search({'query':'queue','providers':['crossref','openalex'],'limit':2},threading.Event(),client_factory=factory)
    assert result['complete'] is False and result['after_dedup']==1
    assert result['coverage'][1]['status']=='failed' and '限流' in result['coverage'][1]['error']
    assert all('PRIVATE' not in url for url in urls) and 'bibtex' in result['results'][0]

def test_failure_interruption_and_project_scoped_jobs(tmp_path):
    r=instance(tmp_path,'student','S');pid=create(r)['id'];other=create(r)['id']
    bad=job(r,pid,'source.parse',{'title':'失败原件','filename':'bad.txt','base64':'!!!!'})
    assert wait(r,pid,bad['id'])['state']=='failed'
    with pytest.raises(PermissionError):v2(r,other,'job.get',{'job_id':bad['id']})
    with storage.project(r,pid) as db:
        value=jobs.get(db,bad['id']);value['state']='running';value['updated']=time.time()-100;jobs.save(db,value)
    assert v2(r,pid,'job.get',{'job_id':bad['id']})['result']['job']['state']=='interrupted'

def test_v2_http_and_mcp_share_scope_and_frozen_v1(tmp_path):
    r=instance(tmp_path,'student','S');pid=create(r)['id'];request=raw('source.save',{'title':'同一入口','text':'Synthetic source'},pid,0,'transport')
    app=create_app(r.folder,runtime=r,network=False)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        assert client.post('/api/local/capabilities/invoke',json=request).status_code==401
        client.post('/api/local/session',json={'bootstrap':app.state.bootstrap})
        response=client.post('/api/local/capabilities/invoke',json=request);assert response.status_code==200,response.text
        expected=response.json()
        async def invoke():return await create_mcp(r).call_tool('invoke_research_capability',{'request':request})
        result=asyncio.run(invoke());actual=result[1] if isinstance(result,tuple) else json.loads(result[0].text)
        assert actual==expected
    root=Path(__file__).resolve().parents[1]
    for name,cls in [('request',Request),('result',Result)]:assert json.loads((root/'docs/contracts'/('research.capability.v2.'+name+'.schema.json')).read_text(encoding='utf8'))==cls.model_json_schema()

def test_real_liteparse_pdf_coordinates_and_encrypted_restore(tmp_path):
    from base.app.local_runtime import LocalRuntime
    from base.app.local_backup import export_backup,restore_backup
    from test_local_runtime import MemoryVault
    r=instance(tmp_path/'source','student','S');pid=create(r)['id'];original=synthetic_pdf()
    parsed=wait(r,pid,job(r,pid,'source.parse',{'title':'合成PDF','filename':'fixture.pdf','base64':base64.b64encode(original).decode(),'provenance':'synthetic'})['id'])
    assert parsed['state']=='succeeded',parsed
    value=v2(r,pid,'asset.resolve',{'ref':parsed['result_ref']})['result']['content']
    assert 'SYNTHETIC RESEARCH PDF' in value['text'] and value['boxes'] and value['pages'][0]['page']==1
    assert value['ocr']=='disabled' and value['network_used'] is False
    encrypted=export_backup(r,'synthetic-password-12')
    restored=LocalRuntime(tmp_path/'restored',MemoryVault());restore_backup(restored,encrypted,'synthetic-password-12');restored=LocalRuntime(restored.folder,restored.vault)
    assert base64.b64decode(v2(restored,pid,'source.original',{'ref':parsed['result_ref']})['result']['base64'])==original
    assert v2(restored,pid,'job.get',{'job_id':parsed['id']})['result']['job']['state']=='succeeded'

@pytest.mark.parametrize('method',['qualitative','humanities','design'])
def test_broad_methods_do_not_require_experiment_or_statistics(tmp_path,method):
    r=instance(tmp_path,'student','S');pid=create(r,method=method)['id']
    source=v2(r,pid,'source.save',{'title':'情境材料','text':'合成材料A：使用者认为入口不清楚。合成材料B：熟悉者并不觉得困难。','provenance':'synthetic'})['refs'][0]
    plan=v2(r,pid,'plan.save',{'title':'广义研究计划','method':method,'question':'不同使用者为何有不同理解？',
       'materials':'说明取材边界与出处','procedure':'比较材料，保留不同声音','counterevidence':'主动保留不感到困难的例子',
       'analysis':'结合语境对照解释','limitations':'合成工程案例，无现实结论','refs':[source]})
    assert plan['checks']['method']['checks'] and plan['checks']['domain_review']=='not_reviewed'
    report=v2(r,pid,'report.save',{'title':'方法适配示例','method':method,'claims':[{'text':'材料呈现不同看法','status':'interpretation',
        'evidence':[{'ref':source,'start':0,'end':5,'quote':'合成材料A','relation':'context'}]}],'limitations':'合成材料仅验证记录流程'})
    review=wait(r,pid,job(r,pid,'report.audit',{'ref':report['refs'][0]})['id'])
    assert review['state']=='succeeded',review
    assert not refs_of_kind(r,pid,'experiment') and not refs_of_kind(r,pid,'simulation')

def refs_of_kind(r,pid,kind):return [a for a in read(r,{'id':pid})['assets'] if a['kind']==kind]

def test_structured_direction_agent_uses_only_selected_sources_and_never_selects(tmp_path):
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse,ToolCallPart
    r=instance(tmp_path,'student','S');seen=[]
    async def answer(messages,info):
        seen.extend(str(m) for m in messages)
        candidate={'title':'观察路线','question':'怎样改善？','method':'设计研究','assumptions':'待核查',
           'rivals':'使用者熟悉程度','disconfirming':'新旧使用者没有差别','next_evidence':'补充情境访谈','limitations':'无现实资料','source_ids':['source-1']}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,{'candidates':[candidate,{**candidate,'title':'材料路线'}],'unknowns':['现实差异']} )])
    p={'instruction':'比较多种研究方向','refs':[],'direction_ref':{'asset_id':'test'}}
    context={'independent_ideas':'本人先提出观察','sources':[{'id':'source-1','text':'SELECTED SYNTHETIC CONTEXT'}]}
    result=asyncio.run(executors.generate_directions(r,p,context,threading.Event(),FunctionModel(answer)))
    assert result['selection']=='not_selected' and result['origin']=='model_suggestion'
    assert any('SELECTED SYNTHETIC CONTEXT' in m for m in seen)
    context['sources']=[]
    with pytest.raises(ValueError,match='来源编号'):asyncio.run(executors.generate_directions(r,p,context,threading.Event(),FunctionModel(answer)))

def test_real_registered_simulation_child_is_terminated_on_cancel(tmp_path,monkeypatch):
    r=instance(tmp_path,'student','S');pid=create(r)['id'];ref=experiment(r,pid)
    spawned=threading.Event();processes=[];original=executors.subprocess.Popen
    def tracked(*args,**kwargs):
        child=original(*args,**kwargs);processes.append(child);spawned.set();return child
    monkeypatch.setattr(executors.subprocess,'Popen',tracked)
    parameters={'experiment_ref':ref,'input_provenance':'synthetic','input_source':'取消验收','assumptions':'合成固定队列',
       'horizon':10000.0,'mean_interarrival':.01,'mean_service':6.0,'servers':[2],'replications':30,'max_events':100000,'max_entities':10000}
    started=job(r,pid,'simulation.run',parameters)
    assert spawned.wait(10),'Actual registered worker was not spawned'
    assert v2(r,pid,'job.cancel',{'job_id':started['id']})['result']['job']['state']=='cancelled'
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and any(p.poll() is None for p in processes):time.sleep(.05)
    assert processes and all(p.poll() is not None for p in processes)
    assert wait(r,pid,started['id'])['result_ref'] is None

def test_real_simulation_event_budget_failure_is_preserved(tmp_path):
    r=instance(tmp_path,'student','S');pid=create(r)['id'];ref=experiment(r,pid)
    started=job(r,pid,'simulation.run',{'experiment_ref':ref,'input_provenance':'synthetic','input_source':'事件上限验收',
       'assumptions':'合成固定队列','horizon':1000.0,'servers':[2],'replications':2,'max_events':10})
    done=wait(r,pid,started['id']);assert done['state']=='failed' and 'max_events' in done['error']
    assert done['events'][-1]['state']=='failed' and done['result_ref'] is None
