"""Durable project jobs; bounded execution happens outside the product/DB lock."""
import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from base.app.product_lock import lock
from base.app.research.assets.references import canonical,digest,reference
from . import storage,executors

POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='hyper-research')
WORKERS={}
ACTIVE={'queued','running'}
RETRYABLE={'failed','cancelled','interrupted','timed_out'}

def ensure(db):
    db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
    db.commit()

def get(db,jid):
    row=db.execute('SELECT body FROM jobs WHERE id=?',(jid,)).fetchone()
    if not row:raise PermissionError('执行任务不属于当前科研项目')
    return json.loads(row[0])

def save(db,value):
    db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(value['id'],canonical(value).decode()))

def public(value):
    return {k:v for k,v in value.items() if k not in ['parameters','prepared']}

def event(value,state,message):
    value['state']=state;value['updated']=time.time()
    value['events'].append({'state':state,'at':value['updated'],'message':message})

def prepare(runtime,db,pid,task,p):
    from .service_v2 import resolved,readable
    from .contracts_v2 import AssetRef
    prepared=dict(p)
    refs=[]
    for name in ['direction_ref','experiment_ref','ref']:
        if p.get(name):refs.append(p[name])
    refs+=p.get('refs',[])
    values={}
    for ref in refs:
        value=resolved(runtime,db,pid,ref);values[ref['asset_id']]=value
    if task.startswith('direction.'):
        direction=values[p['direction_ref']['asset_id']]
        if direction['kind']!='direction' or not direction['content'].get('independent_ideas'):raise ValueError('请先保存本人独立提出的方向')
        problem=storage.latest(db,'problem')
        from base.app.research.assets.references import checked_body
        question=checked_body(problem) if problem else {}
        if task=='direction.scaffold':
            prepared.update({'independent_ideas':direction['content']['independent_ideas'],
                            'title':storage.metadata(db)['title'],'question':question.get('question',storage.metadata(db)['title']),
                            'constraints':question.get('constraints',''),'session_id':'session-'+uuid4().hex})
        else:
            prepared['context']={'question':question,'independent_ideas':direction['content']['independent_ideas'],
                'sources':[{'id':ref['asset_id'],'ref':ref,'text':readable(values[ref['asset_id']])[:10000],
                            'content_scope':values[ref['asset_id']]['content'].get('content_scope','research_record')}
                           for ref in p['refs']]}
    if task in ['design.generate','simulation.run'] and values[p['experiment_ref']['asset_id']]['kind']!='experiment':raise ValueError('请选择本项目已保存的实验设计')
    if task=='simulation.run' and p['input_provenance']=='observed' and not p['refs']:raise ValueError('实测参数需要关联实际观察或资料；否则请标记为假设或合成输入')
    if task=='report.audit':
        v=values[p['ref']['asset_id']]
        if v['kind']!='report':raise ValueError('请选择本项目成果简报')
        from .service_v2 import report_markdown
        prepared['text']=report_markdown(v['content'])
        prepared['research_review']={'questions':['主张是否超过材料实际能支持的范围？','是否主动保留相反材料或替代解释？','是否把相关、模拟或自述写成因果事实？','抽样、情境与缺失材料怎样限制解释？'],
            'structural_checks':v['content'].get('checks',{}),'source':'scientific-critical-thinking rule adaptation','semantic_support':'requires_review'}
    return prepared,refs

def reserve(runtime,db,pid,r,task,p,retry_of=None):
    ensure(db);db.execute('BEGIN IMMEDIATE')
    fp=digest(r.model_dump(mode='json'))
    prior=storage.replay(db,r.request_id,fp)
    if prior:return get(db,prior['job_id']),False
    if r.expected_revision is None or storage.metadata(db)['revision']!=r.expected_revision:raise ValueError('项目已更新，请重新打开后执行')
    active=sum(json.loads(x[0])['state'] in ACTIVE for x in db.execute('SELECT body FROM jobs'))
    if active>=4:raise ValueError('本项目最多同时保留4个执行中任务，请等待或取消后再试')
    prepared,refs=prepare(runtime,db,pid,task,p)
    value={'id':'rj-'+uuid4().hex,'task':task,'state':'queued','created':time.time(),'updated':time.time(),
           'parameters':p,'prepared':prepared if task.startswith('direction.') or task=='report.audit' else None,'refs':refs,'input_project_revision':r.expected_revision,
           'events':[],'retry_of':retry_of,'result_ref':None,'error':None}
    event(value,'queued','已登记，等待本机执行');save(db,value)
    storage.remember(db,r.request_id,fp,{'job_id':value['id']})
    return value,True

def key(runtime,pid,jid):return (str(runtime.folder.resolve()),runtime.identity.id,pid,jid)

def start(runtime,pid,jid):
    k=key(runtime,pid,jid)
    with lock(runtime.folder):
        if k in WORKERS:return
        cancel=threading.Event();WORKERS[k]=cancel
    POOL.submit(work,runtime,pid,jid,cancel)

def work(runtime,pid,jid,cancel):
    k=key(runtime,pid,jid)
    try:
        with lock(runtime.folder),storage.project(runtime,pid) as db:
            value=get(db,jid)
            if value['state']!='queued':return
            event(value,'running','本机执行中');save(db,value)
        last=[time.monotonic()]
        def heartbeat():
            if time.monotonic()-last[0]<1:return
            with lock(runtime.folder),storage.project(runtime,pid) as db:
                current=get(db,jid)
                if current['state']=='cancelled':cancel.set()
                current['updated']=time.time();save(db,current)
            last[0]=time.monotonic()
        task=value['task'];p=value['prepared'] or value['parameters']
        if cancel.is_set():raise executors.Cancelled('执行已取消')
        if task=='search.remote':result=executors.remote_search(p,cancel,heartbeat)
        elif task=='direction.generate':
            try:result=asyncio.run(executors.generate_directions(runtime,p,p['context'],cancel))
            except (executors.Cancelled,TimeoutError,ValueError):raise
            except Exception:raise ValueError('模型请求未完成，请检查模型配置、余额及结构化输出支持后重试') from None
        else:result=executors.execute_worker(task,p,cancel,heartbeat)
        if cancel.is_set():raise executors.Cancelled('执行已取消')
        kind={'source.parse':'source','search.remote':'search','direction.scaffold':'direction','direction.generate':'direction',
              'design.generate':'design','simulation.run':'simulation','report.audit':'review'}[task]
        with lock(runtime.folder),storage.project(runtime,pid) as db:
            db.execute('BEGIN IMMEDIATE');current=get(db,jid)
            if current['state']=='cancelled' or cancel.is_set():return
            from .service_v2 import resolved,check_source_quota
            for ref in value['refs']:resolved(runtime,db,pid,ref)
            if kind=='source':check_source_quota(db,result)
            if task=='source.parse':
                raw=__import__('base64').b64decode(result['_original_base64'],validate=True)
                result['original_sha256']=__import__('hashlib').sha256(raw).hexdigest()
            result['execution']={'job_id':jid,'task':task,'input_project_revision':value['input_project_revision'],
                'completed_project_revision':storage.metadata(db)['revision'],'input_refs':value['refs'],
                'upstream_commit':'5f2bc0341354fd5590aef76a533ada1e1e5b4e62'}
            row=storage.append(db,'ra-'+uuid4().hex,kind,result,runtime.identity.id);storage.bump(db)
            current['result_ref']=reference(pid,row);event(current,'succeeded','执行完成，产物已保存为项目资产');save(db,current)
            if task=='source.parse':
                current['parameters']={k:v for k,v in current['parameters'].items() if k!='base64'}
                current['original_ref']=current['result_ref'];save(db,current)
    except Exception as error:
        state='cancelled' if isinstance(error,executors.Cancelled) else 'timed_out' if isinstance(error,TimeoutError) else 'failed'
        try:
            with lock(runtime.folder),storage.project(runtime,pid) as db:
                current=get(db,jid)
                if current['state']!='cancelled':
                    current['error']=str(error)[:1000];event(current,state,current['error']);save(db,current)
        except Exception:pass
    finally:
        with lock(runtime.folder):WORKERS.pop(k,None)

def inspect(runtime,db,pid,jid):
    value=get(db,jid)
    if value['state'] in ACTIVE and key(runtime,pid,jid) not in WORKERS and time.time()-value['updated']>75:
        event(value,'interrupted','执行心跳已中断；未自动重做，可保留原输入重试');save(db,value)
    return public(value)

def cancel(runtime,db,pid,jid):
    value=get(db,jid)
    if value['state'] in ACTIVE:
        flag=WORKERS.get(key(runtime,pid,jid))
        if flag:flag.set()
        event(value,'cancelled','调用者取消；保留输入与事件，未产生成功产物');save(db,value)
    return public(value)
