"use strict";
(() => {
  const W=window.ResearchWorkbench, {state,h,field,options,notice,openProject,showDialog}=W;
  const tabs=["问题与记录","资料与检索","方向与计划","实验与模拟","成果与复盘"];
  const labels={source:"研究资料",search:"外部搜寻",screening:"筛选记录",direction:"方向探索",plan:"研究计划",experiment:"实验设计",design:"分配与运行表",simulation:"模拟结果",report:"成果简报",review:"审阅与反馈"};
  const statuses={queued:"等待执行",running:"执行中",succeeded:"已完成",failed:"失败",cancelled:"已取消",interrupted:"执行中断",timed_out:"执行超时"};
  const drafts=new Map(),requests=new Map();let tab=0,jobs=[],hits=[],searchResults=[],currentProject=null,reportEdit=null,reportVersion=null,claims=[],seenJobs=new Set(),polling=false,skipCapture=false,workflowPolicy=null;
  const sources=()=>state.assets.filter(a=>["source","record","companion_material","simulation","design"].includes(a.kind));
  const refs=(kind)=>state.assets.filter(a=>a.kind===kind);
  const select=(name,items,empty="请选择",required=true)=>'<label class="field">'+empty+'<select name="'+name+'"'+(required?' required':'')+'><option value="">'+empty+'</option>'+items.map(a=>'<option value="'+h(a.asset_id)+'">'+h(a.content.title||a.content.question||labels[a.kind])+' · v'+a.revision+'</option>').join("")+'</select></label>';
  const button=(action,label,id="",quiet=false)=>'<button type="button" data-rw="'+action+'" data-id="'+h(id)+'"'+(quiet?' class="quiet"':'')+'>'+label+'</button>';
  async function call(op,input={},write=false,key=null){
    if(key&&requests.has(key))return W.jsonFetch('/api/local/capabilities/invoke',requests.get(key));
    if(write){
      const latest=(await W.call('research.project.read')).result;
      if(input.asset_id){
        const shown=state.assets.find(a=>a.asset_id===input.asset_id),current=latest.assets.find(a=>a.asset_id===input.asset_id);
        if((input.asset_id===reportEdit?reportVersion?.sha256:shown?.ref.sha256)!==current?.ref.sha256)throw Error('这份记录已有新版本，请先打开最新版本再修订。当前输入仍保留。');
      }
      state.current=latest.project;state.assets=latest.assets;
    }
    const raw={contract_version:"research.capability.v2",request_id:key||crypto.randomUUID(),capability:"research."+op,project_id:state.current.id,input};
    if(write)raw.expected_revision=state.current.revision;
    if(key){requests.set(key,raw);if(requests.size>20)requests.delete(requests.keys().next().value);}
    try{return await W.jsonFetch("/api/local/capabilities/invoke",raw);}catch(error){if(key&&error.message.includes('项目已更新'))requests.delete(key);throw error;}
  }
  function capture(){
    if(!currentProject)return;
    const values={};document.querySelectorAll('#research-workflow form').forEach(f=>{
      values[f.id]=Array.from(f.elements).filter(e=>e.name&&e.type!=="file"&&e.type!=="submit").map(e=>({name:e.name,value:e.value,checked:e.checked}));
    });drafts.set(currentProject,values);
  }
  function restore(){
    const values=drafts.get(currentProject)||{};
    for(const [id,fields] of Object.entries(values))for(const f of fields){const el=document.getElementById(id)?.elements.namedItem(f.name);if(el&&"value" in el){el.value=f.value;if(el.type==="checkbox")el.checked=f.checked;}}
  }
  function panel(title,body){return '<section class="panel"><h2>'+title+'</h2>'+body+'</section>';}
  function render(){
    const host=document.getElementById("research-workflow");if(!host||!state.current)return;
    if(currentProject!==state.current.id){capture();currentProject=state.current.id;reportEdit=null;claims=[];hits=[];searchResults=[];jobs=[];seenJobs=new Set();}
    const work=document.getElementById("research-work");
    work.querySelectorAll(':scope > .panel').forEach((p,i)=>{p.hidden=tab===0?false:!(tab===1&&i===2);});
    let nav=work.querySelector(".research-tabs");
    if(!nav){nav=document.createElement("nav");nav.className="research-tabs";nav.setAttribute("aria-label","研究流程");work.querySelector(".project-head").after(nav);}
    nav.innerHTML=tabs.map((t,i)=>'<button type="button" data-rw="tab" data-id="'+i+'"'+(i===tab?' aria-current="step" class="active"':'')+'>'+String(i+1).padStart(2,"0")+' / '+t+'</button>').join("");
    const content=[intro(),materials(),directions(),experiments(),reports()][tab];
    host.innerHTML=content+panel("本机执行记录",'<div id="rw-jobs"><p class="small muted">正在读取执行记录…</p></div><p class="small muted">耗时任务在后台执行。取消、失败和重试保留记录；页面刷新后仍可查看。</p>');
    if(tab===1)renderHits();if(tab===4)renderClaims();restore();renderJobs();pollJobs();methodHint();
  }
  async function methodHint(){
    const form=document.getElementById('rw-plan');if(!form)return;
    if(!workflowPolicy){try{workflowPolicy=(await call('workflow.describe')).result.methods;}catch(_){return;}}
    if(!form.isConnected)return;const rule=workflowPolicy[form.elements.method.value];if(!rule)return;
    let hint=form.querySelector('.method-hint');if(!hint){hint=document.createElement('div');hint.className='note method-hint';form.elements.method.closest('label').after(hint);}
    hint.textContent=rule.focus+' 本方法需核对：'+rule.checks.join('、')+'。';
  }
  function intro(){
    return panel("沿着问题选择方法",'<p>资料、方向、计划、实验或材料分析、成果都属于同一个科研项目。按问题选择需要的环节。</p><p class="policy-hint">质性、人文材料与设计研究可以直接从材料和研究计划走向成果；实验与模拟是可选方法。</p><div class="module-strip"><a href="/">超维伴学 ↗</a><strong>超维科研</strong><span>超维项目 · 待接入</span><span>超维规划 · 待接入</span><span>超维链接 · 待接入</span></div>');
  }
  function materials(){
    return panel("导入研究资料",'<form id="rw-source">'+field("资料标题","title","",160,false,true)+field("正文或原文摘录","text","",200000,true,true)+'<div class="two"><label class="field">内容范围<select name="content_scope">'+options({excerpt:"节选",full_text:"全文",abstract:"摘要",metadata:"只有题名等元数据"},"excerpt")+'</select></label><label class="field">内容来源<select name="provenance">'+options({reported:"他人资料或自述",observed:"本人观察",assumed:"假设输入",synthetic:"合成示例"},"reported")+'</select></label></div>'+field("出处、网址或访谈说明","citation","",2000)+'<button class="primary" type="submit">保存文字资料</button></form><details><summary>导入本地原件</summary><form id="rw-file">'+field("原件标题","title","",160,false,true)+'<label class="field">选择原件<input type="file" name="file" accept=".pdf,.txt,.md,.csv,.json" required></label>'+field("出处说明","citation","",2000)+'<p class="small muted">支持 UTF-8 文字文件与含文字的 PDF；每份最多 8MB、PDF 最多 50 页。原件随项目保存。扫描件需另行OCR。</p><button type="submit">解析并保存原件</button></form></details>')+
      panel("在本项目中查找",'<form id="rw-local">'+field("要找的内容","query","",200,false,true)+'<button type="submit">检索项目资料</button></form><div id="rw-hits"></div>')+
      panel("搜寻外部学术资料",'<p class="small muted">只发送你填写的检索词与年份范围。结果是元数据及可用摘要；全文需取得后另行导入。</p><form id="rw-remote">'+field("检索词（可尝试中英文）","query","",240,false,true)+'<div class="provider-options"><label><input type="checkbox" name="crossref" checked>Crossref</label><label><input type="checkbox" name="openalex">OpenAlex</label><label><input type="checkbox" name="arxiv">arXiv</label></div><div class="two">'+field("起始年份（选填）","year_from","",4)+field("结束年份（选填）","year_to","",4)+'</div><button type="submit">开始搜寻</button></form><div id="rw-external"></div>')+
      panel("项目资料与搜寻记录",assetList(["source","search","screening"]));
  }
  function directions(){
    return panel("先留下自己的方向",'<form id="rw-direction">'+field("本轮探索名称","title","",160,false,true)+field("在 AI 建议之前，你有哪些想法？","independent_ideas","",8000,true,true)+field("其他候选与待探索可能","candidates","",12000,true)+field("比较方向的标准","criteria","",4000,true)+field("相反解释、失败条件或反例","rivals","",4000,true)+field("本人选择及理由（可先留空）","selection","",4000,true)+'<button class="primary" type="submit">保存方向探索</button></form>')+
      panel("展开方向",'<form id="rw-expand">'+select("direction",refs("direction").filter(a=>a.content.independent_ideas),"选择本人方向记录")+'<div class="actions"><button type="submit" name="mode" value="scaffold">生成方向探索工作底稿</button></div></form><details><summary>使用已配置的 AI 辅助探索</summary><form id="rw-ai">'+select("direction",refs("direction").filter(a=>a.content.independent_ideas),"选择本人方向记录")+select("source",sources(),"选择一份要提供给模型的资料（先保存资料）")+field("本轮想重点探索什么","instruction","",2000,true)+'<label class="consent"><input type="checkbox" name="consent" required>将问题卡、本人方向与所选资料节选发送给已配置模型；使用该模型账户计费。</label><button type="submit">生成 AI 方向候选</button><p class="small muted">在伴学设置中配置的模型可共用。模型给出候选后，请在方向记录里另行写下本人的选择和理由。</p></form></details>')+
      panel("研究计划",'<form id="rw-plan">'+field("计划名称","title","",160,false,true)+'<label class="field">采用的方法<select name="method">'+options(W.methods,state.current.method)+'</select></label>'+field("计划要回答的问题","question","",4000,true,true)+field("选择哪些材料或参与者，为什么","materials","",4000,true)+field("准备怎样观察、访谈、分析材料或迭代原型","procedure","",8000,true)+field("主动寻找哪些反例或相反材料","counterevidence","",4000,true)+field("怎样形成解释或比较结果","analysis","",4000,true)+field("情境、资源与解释的限制","limitations","",4000,true)+'<button type="submit">保存研究计划</button></form>')+panel("方向与计划记录",assetList(["direction","plan"]));
  }
  function experiments(){
    return panel("实验设计",'<p class="small muted">适用于需要观察、比较、分配或测试的问题。先明确研究单位、测量和反例，再生成分配表或运行模拟。</p><form id="rw-experiment">'+field("实验名称","title","",160,false,true)+field("研究单位与分析单位是什么","unit","",2000,true,true)+field("比较什么条件或方案","comparison","",4000,true,true)+field("怎样测量，主要指标是什么","measurement","",4000,true,true)+field("什么算一次独立重复，重复测量如何处理","independent_replication","",4000,true,true)+field("分配、随机化或执行顺序","randomization","",4000,true)+field("控制条件与可能的混淆","controls","",4000,true)+field("什么结果会推翻当前解释","disconfirming","",4000,true)+field("预先确定的分析方式","analysis","",4000,true)+field("现实条件、参与者保护与实施限制","constraints","",4000,true)+'<button class="primary" type="submit">保存实验设计</button></form>')+
      panel("生成分配或因素组合",'<form id="rw-design">'+select("experiment",refs("experiment"),"选择已保存的实验设计")+'<label class="field">方法<select name="method">'+options({blocked:"分块随机分配",simple:"简单随机分配",factorial:"两水平全因子",latin_hypercube:"拉丁超立方采样"},"blocked")+'</select></label><div class="two">'+field("研究单位数 / 采样点数","n","20",4)+field("随机种子","seed","20261103",10)+'</div>'+field("组别（逗号分隔，用于随机分配）","arms","A,B",200)+field("因素与低高水平（每行：因素名,低,高）","factors","窗口数,2,3\n到达间隔,3,5",2000,true)+'<button type="submit">生成计划表</button><p class="small muted">分配表不会自动证明样本独立或实验有效；参与者招募与分配隐蔽需另外安排。</p></form>')+
      panel("模拟实验：有限时段排队比较",'<p>比较不同服务窗口数量下的排队情况。当前模型使用指数到达与服务时间、先到先服务和有限队列。</p><form id="rw-simulation">'+select("experiment",refs("experiment"),"选择已保存的实验设计")+'<label class="field">参数来源<select name="input_provenance">'+options({assumed:"假设参数",synthetic:"合成示例",reported:"他人报告",observed:"本人实测（需关联依据）"},"assumed")+'</select></label>'+select("source",sources().filter(a=>["source","record","companion_material"].includes(a.kind)),"关联参数依据（实测输入必选）",false)+field("参数出处与时间单位","input_source","",2000,true,true)+field("你的模型假设与省略条件","assumptions","",4000,true,true)+'<div class="two">'+field("模拟时长","horizon","120",10)+field("平均到达间隔","mean_interarrival","4",10)+field("平均服务时长","mean_service","6",10)+field("窗口数方案（逗号分隔）","servers","2,3",30)+field("等待队列容量","queue_capacity","20",5)+field("每方案独立重复次数","replications","10",2)+field("基准种子","base_seed","20261103",10)+'</div><button class="primary" type="submit">运行有界模拟</button><p class="small muted">每次最多4个方案、每方案2–30次独立重复。置信区间只反映模型内的随机不确定性；现实效果需另行校准。</p></form>')+panel("实验与模拟产物",assetList(["experiment","design","simulation"]));
  }
  function reports(){
    return panel("成果简报",'<p>把方法、主张、可定位的原文依据与局限放在一起。暂时没有依据的内容可以保留为假设或方案。</p><form id="rw-report">'+field("简报标题","title","",160,false,true)+field("实际采用了什么研究方法与过程","method","",8000,true,true)+'<div id="rw-claims"></div>'+button("add-claim","添加一项主张")+field("局限、未解决问题与尚缺的材料","limitations","",8000,true,true)+field("下一步或修订计划","next_steps","",4000,true)+field("本轮获得的帮助与 AI 使用","assistance","",2000,true)+'<div class="actions"><button class="primary" type="submit">保存成果简报'+(reportEdit?'新版本':'')+'</button>'+(reportEdit?button("cancel-report-edit","取消修订"):"")+'</div></form>')+
      panel("反馈与复盘",'<form id="rw-review">'+select("report",refs("report"),"选择成果简报")+field("反馈：哪些判断仍需补证或修改","feedback","",8000,true,true)+field("准备怎样修订或迁移到下一问题","next_revision","",4000,true)+'<button type="submit">保存反馈记录</button></form>')+
      panel("成果与审阅记录",assetList(["report","review"]))+
      panel("导出与续接",'<div class="actions">'+button("export-markdown","导出研究过程 Markdown")+button("export-json","导出完整项目 JSON")+'</div><p class="small muted">完整项目归档含原件及历次记录。更换设备恢复本机身份时，请同时使用主入口的加密备份。</p>');
  }
  function claimHTML(c,i){
    const e=c.evidence?.[0];return '<fieldset data-claim="'+i+'"><legend>主张 '+(i+1)+'</legend>'+field("主张内容","claim_"+i,c.text||"",4000,true,true)+'<label class="field">性质<select name="status_'+i+'">'+options({finding:"资料或结果中的发现",interpretation:"解释",hypothesis:"待检验假设",proposal:"改进方案"},c.status||"hypothesis")+'</select></label><label class="field">关联依据（选填）<select name="source_'+i+'"><option value="">尚无关联依据</option>'+sources().map(a=>'<option value="'+h(a.asset_id)+'"'+(e?.ref.asset_id===a.asset_id?' selected':'')+'>'+h(a.content.title)+' · v'+a.revision+'</option>').join("")+'</select></label>'+field("原文摘录（须与所选资料一致；可从检索结果中复制）","quote_"+i,e?.quote||"",4000,true)+'<label class="field">这段材料与主张的关系<select name="relation_'+i+'">'+options({context:"提供情境",supports:"支持（作者判断）",contradicts:"相反证据"},e?.relation||"context")+'</select></label>'+(c.evidence?.length>1?'<p class="small muted">已有其他 '+(c.evidence.length-1)+' 项依据会随本次修订保留。</p>':'')+(i>0?button("remove-claim","移除此项",String(i),true):"")+'</fieldset>';
  }
  function renderClaims(){const root=document.getElementById("rw-claims");if(root){if(!claims.length)claims=[{}];root.innerHTML=claims.map(claimHTML).join("");}}
  function rememberClaims(){const form=document.getElementById("rw-report");if(!form)return;claims=Array.from(form.querySelectorAll('[data-claim]')).map((el,i)=>{
    const old=claims[i]||{},ref=sources().find(a=>a.asset_id===form.elements['source_'+i].value)?.ref;
    const quote=form.elements['quote_'+i].value,oldEvidence=old.evidence?.[0];
    return {text:form.elements['claim_'+i].value,status:form.elements['status_'+i].value,
      evidence:ref?[{...(oldEvidence?.ref.asset_id===ref.asset_id&&oldEvidence.quote===quote?oldEvidence:{ref}),quote,relation:form.elements['relation_'+i].value},...(old.evidence||[]).slice(1)]:[],quote};});}
  function assetList(kinds){
    const assets=state.assets.filter(a=>kinds.includes(a.kind));return assets.length?assets.map(a=>'<article class="asset"><div class="provenance"><span class="tag">'+h(labels[a.kind])+'</span><span class="tag">v'+a.revision+'</span>'+(a.content.origin==='model_suggestion'?'<span class="tag">AI 候选</span>':"")+'</div><h3>'+h(a.content.title||labels[a.kind])+'</h3><p class="small muted">'+h({excerpt:"节选",full_text:"全文",abstract:"摘要",metadata:"仅元数据",not_calibrated:"尚未现实校准"}[a.content.content_scope||a.content.reality_validation]||W.methods[a.content.method]||"")+'</p><div class="actions">'+button("view","打开产物",a.asset_id)+(["source"].includes(a.kind)?button("original","下载原件",a.asset_id,true):"")+(a.kind==="search"?button("search-results","查看并筛选结果",a.asset_id,true):"")+(a.kind==="report"?button("edit-report","修订简报",a.asset_id,true)+button("audit-report","检查成果表达",a.asset_id,true)+button("export-report","导出简报",a.asset_id,true):"")+button("history","历次版本",a.asset_id,true)+'</div></article>').join(""):'<p class="small muted">这一环节还没有保存的记录。</p>';
  }
  function renderHits(){const root=document.getElementById("rw-hits");if(!root)return;root.innerHTML=hits.map((m,i)=>'<article class="asset"><h3>'+h(m.title)+'</h3><p>'+h(m.quote)+'</p><p class="small muted">'+h({excerpt:"节选",full_text:"全文",abstract:"摘要",metadata:"仅元数据",research_record:"研究记录"}[m.content_scope]||m.content_scope)+' · 字符 '+m.start+'–'+m.end+(m.locator?' · 第 '+m.locator.page+' 页':"")+'</p>'+button("hit","核对所引版本",String(i))+'</article>').join("");}
  function download(filename,content,type="text/plain;charset=utf-8"){
    const blob=content instanceof Blob?content:new Blob([content],{type}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
  }
  async function start(task,parameters,key){const result=await call("job.start",{task,parameters},true,key);seenJobs.add(result.result.job.id);notice("任务已登记，可在本机执行记录中查看进度。");await pollJobs();return result;}
  async function pollJobs(){
    if(!state.current||polling)return;polling=true;const pid=state.current.id;
    try{const result=await call("job.list");if(state.current?.id!==pid)return;jobs=result.result.jobs;renderJobs();}
    catch(e){const root=document.getElementById("rw-jobs");if(root)root.textContent=e.message;}finally{polling=false;}
  }
  function renderJobs(){const root=document.getElementById("rw-jobs");if(!root)return;root.innerHTML=jobs.length?jobs.map(j=>'<div class="job-row"><strong>'+h({"source.parse":"原件解析","search.remote":"外部资料搜寻","direction.scaffold":"方向底稿","direction.generate":"AI方向候选","design.generate":"实验计划表","simulation.run":"排队模拟","report.audit":"成果表达检查"}[j.task])+'</strong><span class="job-state">'+h(statuses[j.state]||j.state)+'</span><span class="small">'+h(j.error||"")+'</span><div class="actions">'+(["queued","running"].includes(j.state)?button("cancel-job","取消",j.id,true):"")+(j.result_ref?button("refresh-job","更新项目并查看产物",j.id):"")+(["failed","cancelled","interrupted","timed_out"].includes(j.state)?button("retry-job","保留输入重试",j.id,true):"")+button("job-events","执行详情",j.id,true)+'</div></div>').join(""):'<p class="small muted">暂无后台执行任务。</p>';}
  async function save(op,data,key){const result=await call(op,data,true,key);drafts.delete(currentProject);skipCapture=true;try{await openProject(currentProject);}finally{skipCapture=false;}notice(result.checks.missing?.length?"已保存；部分研究设计仍待补充。":"已保存，依据与旧版本继续保留。");return result;}
  document.addEventListener("submit",async event=>{
    const form=event.target;if(!form.id.startsWith("rw-"))return;event.preventDefault();if(form.dataset.busy)return;
    form.dataset.busy="1";form.dataset.key ||=crypto.randomUUID();const key=form.dataset.key;const submit=event.submitter;if(submit)submit.disabled=true;
    try{
      const d=Object.fromEntries(new FormData(form));
      if(form.id==="rw-source")await save("source.save",d,key);
      else if(form.id==="rw-file"){
        const file=form.elements.file.files[0];if(file.size>8388608)throw Error("每份原件最多8MB，请拆分后再导入。");
        const base64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=()=>reject(Error("原件未读取成功"));r.readAsDataURL(file);});
        await start("source.parse",{title:d.title,filename:file.name,base64,citation:d.citation},key);
      }else if(form.id==="rw-local"){
        const result=await call("search.local",{query:d.query});hits=result.result.matches;renderHits();notice("检索了 "+result.result.coverage.eligible_documents+" 份当前可用资料，返回 "+hits.length+" 个片段。");
      }else if(form.id==="rw-remote"){
        const p={query:d.query,providers:["crossref","openalex","arxiv"].filter(k=>form.elements[k].checked),limit:10};if(d.year_from)p.year_from=Number(d.year_from);if(d.year_to)p.year_to=Number(d.year_to);await start("search.remote",p,key);
      }else if(form.id==="rw-direction")await save("direction.save",d,key);
      else if(form.id==="rw-plan")await save("plan.save",d,key);
      else if(form.id==="rw-experiment")await save("experiment.save",d,key);
      else if(["rw-expand","rw-ai"].includes(form.id)){
        const direction=state.assets.find(a=>a.asset_id===d.direction);const parameters={direction_ref:direction.ref};
        if(form.id==="rw-ai"){parameters.refs=[state.assets.find(a=>a.asset_id===d.source).ref];parameters.instruction=d.instruction;parameters.send_selected_to_model=true;}
        await start(form.id==="rw-ai"?"direction.generate":"direction.scaffold",parameters,key);
      }else if(form.id==="rw-design"){
        const p={experiment_ref:state.assets.find(a=>a.asset_id===d.experiment).ref,method:d.method,n:Number(d.n),seed:Number(d.seed),arms:d.arms.split(/[,，]/).map(s=>s.trim()),factors:{}};
        if(["factorial","latin_hypercube"].includes(d.method))for(const line of d.factors.split("\n").filter(s=>s.trim())){const [name,low,high,...rest]=line.split(/[,，]/);if(!name||low===undefined||high===undefined||rest.length)throw Error("因素请逐行填写：因素名,低水平,高水平");p.factors[name.trim()]=[Number(low),Number(high)];}
        await start("design.generate",p,key);
      }else if(form.id==="rw-simulation"){
        const p={...d,experiment_ref:state.assets.find(a=>a.asset_id===d.experiment).ref};delete p.experiment;delete p.source;const source=state.assets.find(a=>a.asset_id===d.source);if(source)p.refs=[source.ref];if(d.input_provenance==="observed"&&!source)throw Error("请先选择关联参数依据；可在资料环节导入本人观察材料。");
        for(const k of ["horizon","mean_interarrival","mean_service","queue_capacity","replications","base_seed"])p[k]=Number(p[k]);p.servers=d.servers.split(/[,，]/).map(Number);await start("simulation.run",p,key);
      }else if(form.id==="rw-report"){
        const data={title:d.title,method:d.method,limitations:d.limitations,next_steps:d.next_steps,assistance:d.assistance,claims:[]};
        for(const [i,el] of Array.from(form.querySelectorAll('[data-claim]')).entries()){
          const source=state.assets.find(a=>a.asset_id===d['source_'+i]),quote=d['quote_'+i],evidence=[];
          if(source&&quote){
            const old=claims[i]?.evidence?.[0];
            if(old?.ref.asset_id===source.asset_id&&old.quote===quote&&Number.isInteger(old.start))evidence.push({...old,relation:d['relation_'+i]});
            else{let text=source.content.text;if(!text)text=(await call("asset.resolve",{ref:source.ref})).result.selection;const start=text.indexOf(quote);if(start<0)throw Error("主张 "+(i+1)+" 的摘录与所选资料不一致，请重新核对原文。");evidence.push({ref:source.ref,start,end:start+quote.length,quote,relation:d['relation_'+i]});}
          }
          if(quote&&!source)throw Error("请为主张 "+(i+1)+" 的摘录选择来源。");
          if(claims[i]?.evidence?.length>1)evidence.push(...claims[i].evidence.slice(1));
          data.claims.push({text:d['claim_'+i],status:d['status_'+i],evidence});
        }
        if(reportEdit)data.asset_id=reportEdit;await save("report.save",data,key);reportEdit=null;claims=[{}];render();
      }else if(form.id==="rw-review")await save("review.save",{report_ref:state.assets.find(a=>a.asset_id===d.report).ref,feedback:d.feedback,next_revision:d.next_revision},key);
      if(!["rw-local"].includes(form.id))delete form.dataset.key;
    }catch(e){notice(e.message,true);}finally{delete form.dataset.busy;if(submit?.isConnected)submit.disabled=false;}
  });
  document.addEventListener("input",event=>{const form=event.target.closest('form[id^="rw-"]');if(form)delete form.dataset.key;});
  document.addEventListener('change',event=>{if(event.target.matches('#rw-plan select[name="method"]'))methodHint();});
  document.addEventListener("click",async event=>{
    const b=event.target.closest('button[data-rw]');if(!b)return;const action=b.dataset.rw,id=b.dataset.id;b.disabled=true;
    try{
      if(action==="tab"){rememberClaims();capture();tab=Number(id);render();}
      else if(action==="view")await view(state.assets.find(a=>a.asset_id===id));
      else if(action==="hit"){const m=hits[Number(id)],r=await call("asset.resolve",{ref:m.ref,start:m.start,end:m.end});showDialog(m.title,'<div class="history">'+h(r.result.selection)+'</div><p class="small muted">所引版本与位置已核对；请自行判断它与主张的关系。</p>');}
      else if(action==="original"){const a=state.assets.find(a=>a.asset_id===id),r=(await call("source.original",{ref:a.ref})).result;download(r.filename,new Blob([Uint8Array.from(atob(r.base64),c=>c.charCodeAt(0))]));}
      else if(action==="history"){const r=await W.call("research.asset.history",{asset_id:id});showDialog("历次版本",r.result.versions.map(a=>'<div class="history"><h3>v'+a.revision+' · '+h(a.created)+'</h3><pre>'+h(JSON.stringify(a.content,null,2))+'</pre></div>').join(""));}
      else if(action==="search-results")showSearch(state.assets.find(a=>a.asset_id===id));
      else if(["include","exclude"].includes(action)){
        const i=Number(id),reason=document.getElementById('rw-reason-'+i).value;if(!reason.trim())throw Error("请记录纳入或排除这份资料的理由。");
        await save("source.screen",{search_ref:searchResults.ref,index:i,decision:action,reason});document.getElementById("research-dialog").close();
      }else if(action==="cancel-job"){await call("job.cancel",{job_id:id});await pollJobs();}
      else if(action==="retry-job"){await call("job.retry",{job_id:id},true);await pollJobs();}
      else if(action==="job-events"){const j=(await call("job.get",{job_id:id})).result.job;showDialog("本次执行详情",'<ol>'+j.events.map(e=>'<li>'+h(statuses[e.state]||e.state)+' · '+h(e.message)+'</li>').join("")+'</ol><p class="small muted">'+h(j.id)+'</p>');}
      else if(action==="refresh-job"){capture();const j=jobs.find(x=>x.id===id);await openProject(state.current.id);const asset=state.assets.find(a=>a.asset_id===j.result_ref.asset_id);if(asset)await view(asset);}
      else if(action==="add-claim"){rememberClaims();capture();if(claims.length>=30)throw Error("每份简报最多30项主张");claims.push({});renderClaims();restore();}
      else if(action==="remove-claim"){rememberClaims();claims.splice(Number(id),1);renderClaims();}
      else if(action==="edit-report"){
        const a=state.assets.find(a=>a.asset_id===id);capture();const draft=drafts.get(currentProject);if(draft)delete draft['rw-report'];reportEdit=id;reportVersion=a.ref;claims=structuredClone(a.content.claims);render();const f=document.getElementById("rw-report");for(const k of ["title","method","limitations","next_steps","assistance"])f.elements[k].value=a.content[k]||"";f.scrollIntoView({behavior:"smooth",block:"start"});
      }else if(action==="cancel-report-edit"){reportEdit=null;claims=[{}];drafts.delete(currentProject);render();}
      else if(action==="audit-report")await start("report.audit",{ref:state.assets.find(a=>a.asset_id===id).ref});
      else if(action.startsWith("export-")){
        const input={format:action==="export-json"?"json":"markdown"};if(action==="export-report")input.report_ref=state.assets.find(a=>a.asset_id===id).ref;
        const r=(await call("project.export",input)).result;download(r.filename,r.content);notice("导出文件已准备。");
      }
    }catch(e){notice(e.message,true);}finally{if(b.isConnected)b.disabled=false;}
  });
  function showSearch(a){
    searchResults={ref:a.ref,items:a.content.results};const b=a.content;
    showDialog(b.title,'<p class="small">本次检索：'+h(b.query.query)+'；'+h(b.searched_at)+'</p><p class="small muted">'+h(b.text)+'</p>'+b.coverage.map(c=>'<p class="small">'+h(c.provider)+'：'+h(c.status==='succeeded'?'返回 '+c.returned+' 条，首批结果':c.error)+'</p>').join("")+b.results.map((r,i)=>'<article class="asset"><h3>'+h(r.title)+'</h3><p class="small">'+h(r.authors)+' · '+h(r.year||"年份未知")+'</p><p>'+h(r.abstract||"只有元数据；尚未取得可阅读摘要或全文。")+'</p><p class="small">'+h(r.doi||r.url)+'</p><label class="field">纳入或排除理由<textarea id="rw-reason-'+i+'" maxlength="2000"></textarea></label><div class="actions">'+button("include","纳入项目资料",String(i))+button("exclude","记录排除理由",String(i),true)+'</div></article>').join(""));
  }
  async function view(a){
    if(a.kind==="search"){showSearch(a);return;}
    const result=(await call("asset.resolve",{ref:a.ref})).result,b=result.content;let body='';
    if(a.kind==="simulation")body='<p class="note">'+h({assumed:"假设参数",synthetic:"合成示例",reported:"他人报告",observed:"本人观察"}[b.parameters.input_provenance])+'输入 · 尚未现实校准。'+h(b.comparison)+'</p>'+b.scenarios.map(s=>'<h3>'+s.servers+' 个服务窗口</h3><div class="table-scroll"><table><thead><tr><th>指标</th><th>独立重复均值与区间</th></tr></thead><tbody>'+Object.entries(s.result.intervals).map(([k,v])=>'<tr><td>'+h({average_wait:"平均等待",average_queue_length:"平均队长",average_system_time:"平均系统停留",loss_probability:"拒绝比例",server_utilization:"服务台利用率",throughput_per_time_unit:"单位时间完成数"}[k]||k)+'</td><td>'+h(v.status==="ok"?Number(v.mean).toFixed(3)+"（95%区间 "+Number(v.lower).toFixed(3)+" 至 "+Number(v.upper).toFixed(3)+"；"+v.replications+"次重复）":"部分重复没有可定义的指标")+'</td></tr>').join("")+'</tbody></table></div>').join("")+'<p class="small muted">'+h(b.assumptions.join("；"))+'</p>';
    else if(a.kind==="design")body='<div class="table-scroll"><table><thead><tr>'+Object.keys(b.rows[0]||{}).map(k=>'<th>'+h(k)+'</th>').join("")+'</tr></thead><tbody>'+b.rows.map(r=>'<tr>'+Object.values(r).map(v=>'<td>'+h(v)+'</td>').join("")+'</tr>').join("")+'</tbody></table></div><p class="small muted">'+h(b.unit_note)+'</p>';
    else if(b.origin==="model_suggestion")body=b.candidates.candidates.map(c=>'<article class="asset"><h3>'+h(c.title)+'</h3>'+Object.entries(c).filter(([k])=>k!=="title").map(([k,v])=>'<p><strong>'+h({question:"问题",method:"方法",assumptions:"假设",rivals:"相反解释",disconfirming:"推翻条件",next_evidence:"下一步材料",limitations:"限制",source_ids:"来源编号"}[k])+'：</strong>'+h(Array.isArray(v)?v.join("、"):v)+'</p>').join("")+'</article>').join("");
    else if(a.kind==='direction'&&b.register)body='<p>'+h(b.text)+'</p><h3>探索顺序</h3><ol>'+['明确范围','先独立提出方向','结构化分享','聚合相近思路','定义比较标准','独立评估','主动质疑','回到文献检查','可行性与实施条件','记录本人选择'].map(s=>'<li>'+s+'</li>').join('')+'</ol><p class="small muted">工作底稿保留空白候选、假设与决策表；生成底稿不代表这些步骤已经完成。</p>';
    else if(['plan','experiment','direction','review'].includes(a.kind)){
      const names={question:'研究问题',method:'研究方法',materials:'材料选择',procedure:'过程',counterevidence:'反例',analysis:'分析方式',limitations:'限制',unit:'研究单位',comparison:'比较条件',measurement:'测量方式',independent_replication:'独立重复',randomization:'分配顺序',controls:'控制与混淆',disconfirming:'推翻条件',constraints:'实施限制',independent_ideas:'本人方向',candidates:'其他候选',criteria:'比较标准',rivals:'相反解释',selection:'本人选择',feedback:'反馈',next_revision:'修订计划',text:'说明'};
      body=Object.entries(names).filter(([k])=>b[k]).map(([k,label])=>'<h3>'+label+'</h3><p class="history">'+h(W.methods[b[k]]||b[k])+'</p>').join('');
      if(b.language_findings)body+='<p class="small muted">自动语言检查 '+b.language_findings.length+' 项线索；中文语义与内容支持仍需逐条审阅。</p>';
      if(b.research_review){
        body+='<h3>研究判断复核</h3><ul>'+b.research_review.questions.map(q=>'<li>'+h(q)+'</li>').join('')+'</ul>';
        const checks=b.research_review.structural_checks||{};
        if(checks.unlinked_claims?.length)body+='<p class="note">尚未关联依据的主张：'+h(checks.unlinked_claims.join('、'))+'。请保留为假设/方案，或继续补充依据。</p>';
        if(checks.finding_without_support?.length)body+='<p class="note">标为发现但未关联支持材料的主张：'+h(checks.finding_without_support.join('、'))+'。请核对主张性质与证据关系。</p>';
      }
    }else body='<div class="history">'+h(result.selection)+'</div>'+(result.range.end<result.range.total?'<p class="small muted">当前显示前2万字。可通过资料检索定位其他片段；下载原件可查看全文。</p>':"");
    showDialog(b.title||labels[a.kind],body);
  }
  window.addEventListener("research:render",render);
  window.addEventListener('research:before-render',()=>{if(!skipCapture){rememberClaims();capture();}});
  setInterval(()=>{if(!document.hidden&&state.current)pollJobs();},2000);
  if(document.getElementById("research-workflow"))render();
})();
