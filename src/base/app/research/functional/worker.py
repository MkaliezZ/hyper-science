"""Registered local tasks only. Executed by the separate Python 3.12 environment."""
import base64
import importlib.util
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

VENDOR=Path(__file__).resolve().parent/'vendor'/'scientific_agent_skills'

def module(skill,name):
    folder=VENDOR/skill
    sys.path.insert(0,str(folder))
    sys.modules.pop('_common',None)
    key='research_vendor_'+skill.replace('-','_')+'_'+name
    spec=importlib.util.spec_from_file_location(key,folder/(name+'.py'))
    value=importlib.util.module_from_spec(spec);sys.modules[key]=value
    spec.loader.exec_module(value)
    return value

def run(task,p):
    if task=='source.parse':
        raw=base64.b64decode(p['base64'],validate=True)
        if len(raw)>8*1024*1024:raise ValueError('原件超过8MB')
        suffix=Path(p['filename']).suffix.lower()
        pages=[];boxes=[]
        if suffix=='.pdf':
            from pypdf import PdfReader
            from liteparse import LiteParse
            with tempfile.TemporaryDirectory(prefix='research-parse-') as temp:
                file=Path(temp)/'original.pdf';file.write_bytes(raw)
                reader=PdfReader(file)
                if reader.is_encrypted:raise ValueError('请先提供可打开的PDF副本')
                if len(reader.pages)>50:raise ValueError('首版每份PDF最多50页')
                parsed=LiteParse(ocr_enabled=False,quiet=True).parse(str(file))
                parts=[];pos=0
                for page in parsed.pages:
                    text='\n'.join(i.text for i in page.text_items if i.text)
                    if parts:parts.append('\n\n');pos+=2
                    pages.append({'page':page.page_num,'start':pos,'end':pos+len(text)})
                    for item in page.text_items[:4000]:
                        boxes.append({'page':page.page_num,'text':item.text,'x':item.x,'y':item.y,'width':item.width,'height':item.height})
                    parts.append(text);pos+=len(text)
                text=''.join(parts);parser='liteparse==2.15.0 (OCR disabled)'
        else:
            text=raw.decode('utf-8-sig');parser='utf8-text.v1'
        if not text.strip():raise ValueError('未提取到可检索文字；扫描件需另行OCR，本次保留失败记录')
        if len(text)>200000:raise ValueError('提取文字超过20万字，请拆分原件后导入')
        return {'title':p['title'],'text':text,'citation':p['citation'],'provenance':p['provenance'],
                'content_scope':'full_text','filename':p['filename'],'_original_base64':p['base64'],
                'parser':parser,'pages':pages,'boxes':boxes,'ocr':'disabled','network_used':False}
    if task=='direction.scaffold':
        brain=module('scientific-brainstorming','session_scaffold')
        return {'title':'方向探索工作底稿','text':p['independent_ideas'],
                'register':brain.build_scaffold(session_id=p['session_id'],title=p['title'],question=p['question'][:2000],
                    participant_ids=['current-owner'],constraints=[p['constraints'][:500]] if p['constraints'] else []),
                'origin':'upstream_procedural_scaffold','independent_ideas_ref':p['direction_ref']}
    if task=='design.generate':
        if p['method'] in ['simple','blocked']:
            lib=module('experimental-design','randomization')
            if len(set(p['arms']))!=len(p['arms']) or any(not a.strip() or len(a)>80 for a in p['arms']):raise ValueError('组别名称应简短且互不相同')
            fn=lib.simple_randomization if p['method']=='simple' else lib.block_randomization
            table=fn(p['n'],arms=p['arms'],seed=p['seed'])
        else:
            lib=module('experimental-design','doe_designs')
            factors=p['factors']
            if not factors or any(not k.strip() or len(k)>80 or len(v)!=2 or v[0]>=v[1] for k,v in factors.items()):raise ValueError('每个因素需要两个有限数值：低水平、高水平')
            table=(lib.two_level_factorial(factors,seed=p['seed']) if p['method']=='factorial'
                   else lib.latin_hypercube(factors,n_samples=p['n'],seed=p['seed']))
        return {'title':'实验分配与运行表','text':table.to_csv(index=False),'parameters':p,
                'rows':table.to_dict(orient='records'),'unit_note':'表内unit_id是计划位置；实际研究单位、独立性与分配隐蔽需另外确认。',
                'upstream':'experimental-design','reality_validation':'not_calibrated'}
    if task=='simulation.run':
        lib=module('simpy','replication_runner')
        scenarios=[]
        for servers in p['servers']:
            config={'analysis_mode':'terminating','horizon':p['horizon'],'warm_up':0.0,'servers':servers,
                    'queue_capacity':p['queue_capacity'],'mean_interarrival':p['mean_interarrival'],
                    'mean_service':p['mean_service'],'base_seed':p['base_seed'],
                    'max_entities':p['max_entities'],'max_events':p['max_events']}
            result=lib.run_experiment(lib.ExperimentConfig.from_mapping({'model':config,'replications':p['replications'],'confidence':0.95}))
            scenarios.append({'servers':servers,'result':result})
        text='\n'.join('窗口数 '+str(s['servers'])+'：平均等待 '+str(s['result']['intervals']['average_wait']) for s in scenarios)
        return {'title':'有界排队模型比较','text':text,'model_id':'bounded-queue.v1','parameters':p,'scenarios':scenarios,
                'assumptions':['到达间隔和服务时长服从指数分布','同质服务台，先到先服务','有限排队容量，满员拒绝','固定观察时限，未完成顾客存在右删失'],
                'comparison':'各场景共用基准种子；区间为各场景独立重复均值区间，未估计场景差的区间。',
                'sensitivity':'窗口数比较；到达率/服务率等敏感性请修改参数另行运行。',
                'reality_validation':'not_calibrated','causal_claim':'not_established','network_used':False}
    if task=='papers.normalize':
        records=p['records'];result=[]
        paper=module('paper-lookup','openalex_abstract')
        for r in records:
            if r.get('_openalex'):
                v=paper.summarize(r.pop('_openalex'));r['abstract']=v.get('abstract') or '';r['abstract_warnings']=v.get('abstract_warnings',[])
            result.append(r)
        lit=module('literature-review','search_databases');unique=lit.deduplicate_results(result)
        cite=module('citation-management','_common')
        for i,r in enumerate(unique):
            r['bibtex']=cite.render_entry('article','research'+str(i+1),{'title':r.get('title',''),'doi':r.get('doi',''),'year':str(r.get('year') or ''),'author':r.get('authors','')})
        return {'results':unique,'before_dedup':len(result),'after_dedup':len(unique),'deduplication':'normalized DOI; exact title for DOI-less records; no study-level equivalence claim'}
    if task=='report.audit':
        lint=module('scientific-writing','lint_manuscript')
        issues=[asdict(i) for i in lint.lint_text(p['text'],None)]
        causal=module('hypothesis-generation','lint_causal_claims')
        return {'title':'成果表达检查','text':'自动检查仅提供语言与结构线索；中文语义、引文是否支持主张和方法有效性需逐条审阅。',
                'language_findings':issues,'causal_language':causal.lint(p['text']),
                'report_ref':p['ref'],'research_review':p.get('research_review',{}),'semantic_support':'requires_review','domain_review':'not_reviewed'}
    raise ValueError('未登记的科研执行任务')

def main():
    if sys.platform!='win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    raw=sys.stdin.buffer.read(12*1024*1024+1)
    if len(raw)>12*1024*1024:raise ValueError('执行请求过大')
    request=json.loads(raw)
    try:
        result={'ok':True,'result':run(request['task'],request['parameters'])}
    except Exception as error:
        result={'ok':False,'error':str(error)[:1000]}
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf8'))

if __name__=='__main__':main()
