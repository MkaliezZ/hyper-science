"""Independent research workflows, authorization and provenance in one facade."""
import base64
import hashlib
import json
from uuid import uuid4
from pydantic import ValidationError
from base.app.product_lock import lock
from base.app.research.aesthetic import workflow
from base.app.research.assets.references import checked_body,digest,reference
from base.app.research.assets.retrieval import search
from . import contracts_v2 as c,storage,jobs
from .service import packed,resolve,nonblank

def resolved(runtime,db,pid,ref):return resolve(runtime,db,pid,c.AssetRef.model_validate(ref))

def readable(value):
    b=value['content']
    if value['kind']=='companion_material':return value['linked_source']['text']
    if value['kind']=='report':return report_markdown(b)
    return b.get('text') or b.get('question') or b.get('independent_ideas') or json.dumps(b,ensure_ascii=False,indent=2)

def check_source_quota(db,body,aid=None):
    rows=db.execute("SELECT a.* FROM assets a WHERE kind='source' AND version=(SELECT MAX(version) FROM assets b WHERE b.id=a.id)").fetchall()
    if len(rows)>=100 and aid not in {r['id'] for r in rows}:raise ValueError('每个项目最多100份来源，请另建项目继续研究')
    size=sum(len(checked_body(r).get('_original_base64','')) for r in db.execute("SELECT * FROM assets WHERE kind='source'"))
    if size+len(body.get('_original_base64',''))>45*1024*1024:raise ValueError('本项目原件总量超过上限，请拆分项目')

def report_markdown(b):
    parts=['# '+b['title'],'## 研究方法',b['method'],'## 主张与依据']
    for i,claim in enumerate(b['claims'],1):
        parts+=['### '+str(i)+'. '+claim['text'],'状态：'+claim['status']]
        for e in claim['evidence']:
            r=e['ref'];parts+=['> '+e['quote'].replace('\n','\n> '),
             '关系（作者声明）：'+e['relation']+'；项目 '+r['project_id']+' / '+r['asset_id']+' v'+str(r['revision'])+'；字符 '+str(e['start'])+'–'+str(e['end'])+'；SHA256 '+r['sha256']]
        if not claim['evidence']:parts+=['尚无关联依据。']
    parts+=['## 局限与尚未知',b['limitations'],'## 下一步',b.get('next_steps',''),'## 获得的帮助',b.get('assistance','') or '未记录',
            '引文完整性与内容支持分别审阅；当前未完成领域审定、现实校准或能力评价。']
    return '\n\n'.join(parts)

def invoke(runtime,raw):
    try:
        r=c.Request.model_validate(raw);model=c.INPUTS[r.capability];p=model.model_validate(r.input).model_dump(mode='json')
        if r.capability=='research.job.start':p['parameters']=c.TASKS[p['task']].model_validate(p['parameters']).model_dump(mode='json')
    except (KeyError,ValueError,ValidationError):raise ValueError('科研工作流请求格式无效，请核对字段、数量、引用与参数范围') from None
    launch=None
    with lock(runtime.folder),storage.project(runtime,r.project_id) as db:
        jobs.ensure(db)
        data,refs,checks,launch=execute(runtime,db,r,p)
    if launch:jobs.start(runtime,r.project_id,launch)
    return c.Result(request_id=r.request_id,capability=r.capability,result=data,refs=refs,checks=checks).model_dump(mode='json')

def execute(runtime,db,r,p):
    op=r.capability;pid=r.project_id
    if op=='research.workflow.describe':
        from .executors import worker_python
        try:environment=str(worker_python());available=True
        except ValueError:environment='not_installed';available=False
        return {'layers':{'aesthetic':workflow.VERSION,'functional':'research.capability.v2','assets':'immutable-project-refs'},
                'methods':workflow.METHODS,'capabilities':list(c.INPUTS),'tasks':list(c.TASKS),'worker_available':available,
                'worker_environment':environment,'source_formats':['UTF-8 text','text-native PDF <=50 pages'],
                'source_limits':{'file_bytes':8388608,'text_characters':200000,'sources_per_project':100},
                'simulation_models':['bounded-queue.v1'],'sharing':'current_device_owner_only','model_config':'shared_explicit_selection_only'},[],{},None
    if op=='research.job.list':
        rows=db.execute('SELECT id FROM jobs ORDER BY rowid DESC LIMIT 40').fetchall()
        return {'jobs':[jobs.inspect(runtime,db,pid,x[0]) for x in rows]},[],{},None
    if op=='research.job.get':return {'job':jobs.inspect(runtime,db,pid,p['job_id'])},[],{},None
    if op=='research.job.cancel':return {'job':jobs.cancel(runtime,db,pid,p['job_id'])},[],{},None
    if op in ['research.job.start','research.job.retry']:
        retry=None
        if op.endswith('retry'):
            previous=jobs.get(db,p['job_id']);retry=previous['id']
            if previous['state'] not in jobs.RETRYABLE:raise ValueError('只有失败、取消、超时或中断的任务可以重试')
            task=previous['task'];parameters=previous['parameters']
        else:task=p['task'];parameters=p['parameters']
        value,launch=jobs.reserve(runtime,db,pid,r,task,parameters,retry)
        return {'job':jobs.public(value)},[],{},value['id'] if launch else None
    if op=='research.asset.resolve':
        value=resolved(runtime,db,pid,p['ref']);text=readable(value);end=p['end'] if p['end'] is not None else min(len(text),p['start']+20000)
        if not 0<=p['start']<end<=len(text) or end-p['start']>20000:raise ValueError('每次可打开最多2万字，请选择有效范围')
        value['selection']=text[p['start']:end];value['range']={'start':p['start'],'end':end,'total':len(text)}
        return value,[p['ref']],{'integrity':'checked','claim_support':'unassessed'},None
    if op=='research.source.original':
        value=resolved(runtime,db,pid,p['ref'])
        if value['kind']!='source':raise ValueError('只有导入资料具有独立原件')
        original=checked_body(db.execute('SELECT * FROM assets WHERE id=? AND version=?',(p['ref']['asset_id'],p['ref']['revision'])).fetchone())
        encoded=original.get('_original_base64') or base64.b64encode(original['text'].encode('utf8')).decode()
        raw=base64.b64decode(encoded,validate=True)
        if original.get('original_sha256') and hashlib.sha256(raw).hexdigest()!=original['original_sha256']:raise ValueError('原件完整性校验失败')
        return {'filename':original.get('filename','source.txt'),'base64':encoded,'sha256':hashlib.sha256(raw).hexdigest()},[p['ref']],{'integrity':'checked'},None
    if op=='research.search.local':
        docs=[];unavailable=[]
        for row in db.execute("SELECT a.* FROM assets a WHERE kind IN ('source','record','companion_material') AND version=(SELECT MAX(version) FROM assets b WHERE b.id=a.id)"):
            try:
                value=resolved(runtime,db,pid,reference(pid,row));body=value['content']
                docs.append({'ref':value['ref'],'title':body.get('title','研究资料'),'text':readable(value),
                             'scope':body.get('content_scope','research_record'),'pages':body.get('pages',[])})
            except ValueError:unavailable.append(reference(pid,row))
        return {'matches':search(docs,p['query'],p['limit']),
                'coverage':{'eligible_documents':len(docs),'unavailable':unavailable,'project_id':pid,'version':'latest-only','ranking':'lexical BM25 with CJK unigrams/bigrams'},
                'query':p['query'],'claim_support':'requires_review'},[],{},None
    if op=='research.project.export':
        if p['report_ref']:
            value=resolved(runtime,db,pid,p['report_ref'])
            if value['kind']!='report':raise ValueError('请选择成果简报')
            # Revalidate every linked source at export, including companion revocation.
            for claim in value['content']['claims']:
                for e in claim['evidence']:resolved(runtime,db,pid,e['ref'])
            content=report_markdown(value['content']);refs=[p['report_ref']]
        else:
            rows=db.execute('SELECT * FROM assets ORDER BY rowid').fetchall()
            content={'schema':'research.project-export.v1','project':storage.public_project(storage.metadata(db)),
                     'assets':[{'ref':reference(pid,row),'content':checked_body(row)} for row in rows],
                     'jobs':[json.loads(x[0]) for x in db.execute('SELECT body FROM jobs')],
                     'notice':'项目归档副本；恢复设备身份请使用主入口的加密备份。'};refs=[]
            if p['format']=='markdown':
                content='# '+content['project']['title']+'\n\n'+'\n\n'.join('## '+row['kind']+' '+str(row['version'])+'\n\n'+readable(resolved(runtime,db,pid,reference(pid,row))) for row in rows)
        return {'filename':'research-'+pid+('.md' if p['format']=='markdown' else '.json'),
                'content':content if isinstance(content,str) and p['format']=='markdown' else json.dumps(content,ensure_ascii=False,indent=2)},refs,{},None
    db.execute('BEGIN IMMEDIATE');fp=digest(r.model_dump(mode='json'));prior=storage.replay(db,r.request_id,fp)
    if prior:return prior['data'],prior['refs'],prior['checks'],None
    if r.expected_revision is None or storage.metadata(db)['revision']!=r.expected_revision:raise ValueError('项目已更新，请重新打开后再保存')
    checks={};kind={'research.source.save':'source','research.direction.save':'direction','research.plan.save':'plan',
                    'research.experiment.save':'experiment','research.report.save':'report','research.review.save':'review',
                    'research.source.screen':'screening','research.record.save':'record'}.get(op)
    if kind is None:raise ValueError('未实现的科研工作流能力')
    aid=p.pop('asset_id',None) or 'ra-'+uuid4().hex
    if r.input.get('asset_id') and not storage.latest(db,aid):raise PermissionError('只能修订本项目已有资产')
    if 'title' in p:nonblank(p,'title')
    for ref in p.get('refs',[]):resolved(runtime,db,pid,ref)
    if kind=='source':
        nonblank(p,'text');p['parser']='manual-text.v1';check_source_quota(db,p,aid)
    elif kind=='direction':
        nonblank(p,'independent_ideas');checks=workflow.directions_checks(p)
    elif kind=='plan':checks=workflow.plan_checks(p)
    elif kind=='experiment':checks=workflow.experiment_checks(p)
    elif kind=='report':
        for claim in p['claims']:
            for e in claim['evidence']:
                value=resolved(runtime,db,pid,e['ref']);text=readable(value)
                if value['kind']=='source' and value['content'].get('content_scope')=='metadata':raise ValueError('元数据不能充当内容证据；请导入正文或摘要后定位')
                if e['start']>=e['end'] or text[e['start']:e['end']]!=e['quote'] or e['end']>len(text):raise ValueError('主张引用与所引版本、字符位置不一致')
        checks=workflow.report_checks(p);p['checks']=checks
    elif kind=='review':
        if resolved(runtime,db,pid,p['report_ref'])['kind']!='report':raise ValueError('反馈必须关联本项目成果简报')
        p['reviewer']='current-device-caller-declared';checks={'domain_review':'not_authenticated','ability_judgment':'not_assessed'}
    elif kind=='record':nonblank(p,'text')
    elif kind=='screening':
        v=resolved(runtime,db,pid,p['search_ref'])
        if v['kind']!='search' or p['index']>=len(v['content']['results']):raise ValueError('检索结果编号无效')
        selected=v['content']['results'][p['index']];p['selected_metadata']=selected
        if p['decision']=='include':
            text=selected.get('abstract') or selected['title']
            source={'title':selected['title'][:160],'text':text,'citation':selected.get('doi') or selected.get('url',''),
                    'provenance':'reported','content_scope':'abstract' if selected.get('abstract') else 'metadata',
                    'metadata':selected,'search_ref':p['search_ref'],'screening_reason':p['reason'],'parser':'provider-metadata'}
            check_source_quota(db,source)
            row=storage.append(db,'ra-'+uuid4().hex,'source',source,runtime.identity.id);p['created_source_ref']=reference(pid,row)
    row=storage.append(db,aid,kind,p,runtime.identity.id)
    data={'project':storage.bump(db),'asset':packed(pid,row)};refs=[reference(pid,row)]
    storage.remember(db,r.request_id,fp,{'data':data,'refs':refs,'checks':checks})
    return data,refs,checks,None
