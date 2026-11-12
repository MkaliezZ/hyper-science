"""Bounded subprocess and explicit public-query adapters. No project-wide upload."""
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from html import unescape
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
import httpx
from .contracts_v2 import TASKS

class Cancelled(Exception): pass

def worker_python():
    if getattr(sys,'frozen',False):
        path=Path(sys.executable).parent/'research-runtime'/'python.exe'
    else:
        path=Path(__file__).resolve().parents[5]/'.venv-research'/'Scripts'/'python.exe'
        if sys.platform!='win32':path=path.parents[1]/'bin'/'python'
    if not path.is_file():raise ValueError('科研执行环境尚未安装，请运行科研环境安装脚本后重试。')
    return path

def execute_worker(task,p,cancel,heartbeat=lambda:None,timeout=50):
    python=worker_python();script=Path(__file__).with_name('worker.py')
    # A source-built runtime and frozen distributions use the same reviewed worker.
    if not script.is_file() and getattr(sys,'frozen',False):script=Path(sys._MEIPASS)/'base/app/research/functional/worker.py'
    with tempfile.TemporaryDirectory(prefix='hyper-research-job-') as temp:
        path=Path(temp)
        (path/'input.json').write_text(json.dumps({'task':task,'parameters':p},ensure_ascii=False,allow_nan=False),encoding='utf8')
        with (path/'input.json').open('rb') as inp,(path/'output.json').open('wb') as out,(path/'error.txt').open('wb') as err:
            proc=subprocess.Popen([str(python),'-I',str(script)],stdin=inp,stdout=out,stderr=err,
                    cwd=temp,creationflags=0x08000000 if sys.platform=='win32' else 0)
            start=time.monotonic()
            try:
                while proc.poll() is None:
                    if cancel.is_set():raise Cancelled('本次执行已取消')
                    if time.monotonic()-start>timeout:raise TimeoutError('本次执行达到时限，已终止；可调整参数后重试')
                    if (path/'output.json').stat().st_size+(path/'error.txt').stat().st_size>12*1024*1024:raise ValueError('执行输出超限，已终止')
                    heartbeat();time.sleep(.08)
                if cancel.is_set():raise Cancelled('本次执行已取消')
                if proc.returncode:raise ValueError('科研执行进程异常退出；检查环境与输入后重试')
            finally:
                if proc.poll() is None:proc.kill()
                proc.wait(timeout=5)
        if (path/'output.json').stat().st_size>12*1024*1024:raise ValueError('执行输出超限')
        result=json.loads((path/'output.json').read_text(encoding='utf8'))
        if not result.get('ok'):raise ValueError(result.get('error','科研执行未完成'))
        return result['result']

def _public_response(client,url,params,cancel):
    if cancel.is_set():raise Cancelled('检索已取消')
    with client.stream('GET',url,params=params) as response:
        if response.status_code==429:raise ValueError('服务限流，请稍后重试')
        if response.status_code in [401,403]:raise ValueError('检索服务需要有效访问权限或配置')
        response.raise_for_status();parts=[];size=0
        for chunk in response.iter_bytes():
            if cancel.is_set():raise Cancelled('检索已取消')
            size+=len(chunk)
            if size>2*1024*1024:raise ValueError('检索响应超过2MB上限')
            parts.append(chunk)
        return b''.join(parts)

def remote_search(p,cancel,heartbeat=lambda:None,client_factory=httpx.Client):
    records=[];coverage=[];raw_responses=[]
    with client_factory(timeout=httpx.Timeout(12,connect=5),follow_redirects=False,
             headers={'User-Agent':'HyperResearch/0.2 (local user-initiated research)'}) as client:
        for provider in p['providers']:
            heartbeat()
            try:
                if provider=='crossref':
                    filters=[]
                    if p.get('year_from'):filters.append('from-pub-date:'+str(p['year_from'])+'-01-01')
                    if p.get('year_to'):filters.append('until-pub-date:'+str(p['year_to'])+'-12-31')
                    params={'query':p['query'],'rows':p['limit']}
                    if filters:params['filter']=','.join(filters)
                    raw=_public_response(client,'https://api.crossref.org/works',params,cancel)
                    value=json.loads(raw);items=value['message']['items'];total=value['message'].get('total-results')
                    for w in items:
                        date=(w.get('published') or w.get('issued') or {}).get('date-parts',[[None]])
                        records.append({'provider':provider,'title':str((w.get('title') or ['无标题'])[0])[:1000],
                          'doi':w.get('DOI',''),'url':w.get('URL',''),'year':date[0][0],
                          'authors':'; '.join(' '.join([a.get('given',''),a.get('family','')]).strip() for a in w.get('author',[])[:30]),
                          'abstract':unescape(__import__('re').sub('<[^>]+>',' ',w.get('abstract','')))[:30000]})
                elif provider=='openalex':
                    params={'search':p['query'],'per-page':p['limit']}
                    filters=[]
                    if p.get('year_from'):filters.append('from_publication_date:'+str(p['year_from'])+'-01-01')
                    if p.get('year_to'):filters.append('to_publication_date:'+str(p['year_to'])+'-12-31')
                    if filters:params['filter']=','.join(filters)
                    raw=_public_response(client,'https://api.openalex.org/works',params,cancel);value=json.loads(raw)
                    items=value['results'];total=value.get('meta',{}).get('count')
                    for w in items:
                        records.append({'provider':provider,'title':str(w.get('display_name',''))[:1000],'doi':w.get('doi') or '',
                          'url':w.get('id',''),'year':w.get('publication_year'),'authors':'; '.join(a.get('author',{}).get('display_name','') for a in w.get('authorships',[])[:30]),'_openalex':w})
                else:
                    query='all:'+p['query']
                    # The remote arXiv query is explicit; date filtering is recorded locally below.
                    raw=_public_response(client,'https://export.arxiv.org/api/query',{'search_query':query,'max_results':p['limit']},cancel)
                    ns={'a':'http://www.w3.org/2005/Atom','o':'http://a9.com/-/spec/opensearch/1.1/'};value=ET.fromstring(raw)
                    total=value.findtext('o:totalResults',default='',namespaces=ns);items=value.findall('a:entry',ns)
                    for w in items:
                        year=int((w.findtext('a:published','0000',ns))[:4])
                        if p.get('year_from') and year<p['year_from'] or p.get('year_to') and year>p['year_to']:continue
                        records.append({'provider':provider,'title':w.findtext('a:title','',ns).strip(),'doi':'',
                           'url':w.findtext('a:id','',ns),'year':year,'authors':'; '.join(a.findtext('a:name','',ns) for a in w.findall('a:author',ns)),
                           'abstract':w.findtext('a:summary','',ns).strip()[:30000]})
                coverage.append({'provider':provider,'status':'succeeded','returned':len(items),'estimated_total':total,'pagination':'first_page_only','date_filter':'local_after_first_page' if provider=='arxiv' else 'provider_query'})
                raw_responses.append({'provider':provider,'sha256':hashlib.sha256(raw).hexdigest(),'response_utf8':raw.decode('utf8')})
            except Cancelled:raise
            except Exception as error:
                message=str(error) if isinstance(error,ValueError) else '网络或服务响应异常，请稍后重试'
                coverage.append({'provider':provider,'status':'failed','error':message[:200]})
    normalized=execute_worker('papers.normalize',{'records':records},cancel,heartbeat)
    return {'title':'资料搜寻：'+p['query'],'query':p,'coverage':coverage,'raw_responses':raw_responses,**normalized,
            'searched_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'text':'本次为有界学术元数据与可用摘要搜寻。未获取全文，未穷尽数据库；无结果不表示没有既有研究。',
            'network_used':True,'sent_to_provider':'explicit_query_and_filters_only',
            'complete':all(c['status']=='succeeded' for c in coverage)}

async def generate_directions(runtime,p,context,cancel,model_override=None):
    from pydantic import BaseModel,Field
    from pydantic_ai import Agent,UsageLimits
    from base.app.local_agent import make_model
    from base.app.research.aesthetic.workflow import AI_INSTRUCTIONS
    class Candidate(BaseModel):
        title:str=Field(max_length=160)
        question:str=Field(max_length=2000)
        method:str=Field(max_length=1000)
        assumptions:str=Field(max_length=2000)
        rivals:str=Field(max_length=2000)
        disconfirming:str=Field(max_length=2000)
        next_evidence:str=Field(max_length=2000)
        limitations:str=Field(max_length=2000)
        source_ids:list[str]=Field(default_factory=list,max_length=8)
    class Output(BaseModel):
        candidates:list[Candidate]=Field(min_length=2,max_length=5)
        unknowns:list[str]=Field(default_factory=list,max_length=12)
    settings=runtime.config('model',{})
    model=model_override or make_model(settings,runtime.model_key())
    agent=Agent(model,output_type=Output,instructions=AI_INSTRUCTIONS)
    task=asyncio.create_task(agent.run(json.dumps({'user_instruction':p['instruction'],'selected_context':context},ensure_ascii=False),
        usage_limits=UsageLimits(request_limit=2),model_settings={'timeout':40,'max_tokens':5000}))
    try:
        started=time.monotonic()
        while not task.done():
            if cancel.is_set():raise Cancelled('模型请求已取消')
            if time.monotonic()-started>50:raise TimeoutError('模型请求超时')
            await asyncio.sleep(.1)
        result=await task
        value=result.output.model_dump(mode='json')
        allowed={s['id'] for s in context.get('sources',[])}
        if any(set(c['source_ids'])-allowed for c in value['candidates']):raise ValueError('模型返回了未提供的来源编号，请缩小资料范围后重试')
        return {'title':'AI研究方向候选','text':json.dumps(value,ensure_ascii=False,indent=2),'candidates':value,
                'source_refs':p['refs'],'independent_ideas_ref':p['direction_ref'],'origin':'model_suggestion',
                'model':{'provider':settings.get('provider'),'model':settings.get('model')},
                'sent_context_sha256':hashlib.sha256(json.dumps(context,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                'selection':'not_selected','domain_review':'not_reviewed'}
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
