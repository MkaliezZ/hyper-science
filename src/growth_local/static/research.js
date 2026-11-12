"use strict";
(() => {
  const app = document.getElementById("research-app");
  const state = {projects: [], current: null, assets: [], status: null, sources: [], editing: null};
  const methods = {undecided:"尚未确定",empirical:"观察与比较",qualitative:"访谈与质性",humanities:"人文材料",design:"设计改进",simulation:"模型与模拟"};
  const types = {note:"研究札记",observation:"观察",interpretation:"解释",hypothesis:"假设",decision:"决策",reflection:"反思",evidence:"证据"};
  const origins = {observed:"本人观察",reported:"他人报告或自述",assumed:"假设输入",synthetic:"合成示例"};
  const h = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const uid = () => crypto.randomUUID();
  const options = (items, selected) => Object.entries(items).map(([v,label]) => '<option value="'+h(v)+'"'+(v===selected?' selected':'')+'>'+h(label)+'</option>').join("");
  function notice(text, error=false) {
    const el = document.getElementById("research-notice");
    el.textContent = text; el.className = "show"+(error?" error":"");
    clearTimeout(notice.timer); notice.timer = setTimeout(() => el.className="", error?9000:4500);
  }
  async function jsonFetch(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "本次操作未完成，请重新打开后再试。");
    return data;
  }
  async function call(capability, input={}, write=false, key=null, project=null) {
    const version=capability==="research.record.save"&&input.refs?.some(r=>!["problem","record","companion_material"].includes(r.kind))?"research.capability.v2":"research.capability.v1";
    const request = {contract_version:version,request_id:key||uid(),capability,input};
    if (project || (state.current && !["research.describe","research.project.create","research.project.list","research.companion.sources"].includes(capability))) request.project_id = project || state.current.id;
    if (write && state.current) request.expected_revision = state.current.revision;
    return jsonFetch("/api/local/capabilities/invoke", request);
  }
  const field = (label,name,value="",max=2000,area=false,required=false) => '<label class="field">'+label+(area?'<textarea':'<input')+' name="'+name+'" maxlength="'+max+'"'+(required?' required':'')+(area?' rows="3">'+h(value)+'</textarea>':' value="'+h(value)+'">')+'</label>';
  function shell() {
    window.dispatchEvent(new CustomEvent('research:before-render'));
    app.innerHTML = '<section class="hero"><div class="eyebrow">RESEARCH / 研究工作空间</div><h1>从一个问题，开始研究。</h1><p class="muted">超维科研是超维成长下的独立板块，与超维伴学平行。把问题、依据和每一次修改留下来，让下一步有迹可循。</p><p><span class="scope">本人本机项目</span><span class="scope">独立保存</span><span class="scope">按需联动伴学资料</span></p><p class="small muted">从问题与材料出发，探索方向、设计研究、执行模拟，形成可回查依据的成果。</p></section><div class="layout"><aside class="sidebar"><section class="panel"><h2>我的研究项目</h2><div class="project-list">'+(state.projects.length?state.projects.map(p=>'<button type="button" class="project-item'+(state.current?.id===p.id?' active':'')+'" data-action="open" data-id="'+h(p.id)+'">'+h(p.title)+'<span>'+h(methods[p.method])+' · 修订 '+p.revision+'</span></button>').join(""):'<p class="small muted">建立第一个项目，记录你想弄清楚的问题。</p>')+'</div></section><section class="panel"><h2>建立新项目</h2><form id="research-create">'+field("项目名称","title","",160,false,true)+'<label class="field">研究方向<select name="method">'+options(methods,"undecided")+'</select></label>'+field("项目说明（选填）","description","",4000,true)+'<button class="primary" type="submit">建立项目 →</button></form></section></aside><section id="research-work"></section></div><p class="footer">资料与研究记录保存在这台设备。项目协作和跨设备分享将在独立授权能力接入后开放。</p>';
    renderWork();
  }
  function renderWork() {
    const work = document.getElementById("research-work");
    if (!state.current) { work.innerHTML='<div class="empty"><h2>你想弄清楚什么？</h2><p class="muted">选择已有项目，或先建立一个新项目。</p></div>'; return; }
    const problem = state.assets.find(a=>a.kind==="problem")?.content || {};
    const edit = state.assets.find(a=>a.asset_id===state.editing)?.content || {};
    const records = state.assets.filter(a=>["record","companion_material"].includes(a.kind));
    const subjects = Object.fromEntries([["legacy","本机历史资料"],...(state.status.workspace?.subjects||[]).map(s=>[s.id,s.name])]);
    work.innerHTML='<div class="project-head"><div><div class="section-label">CURRENT PROJECT</div><h2>'+h(state.current.title)+'</h2><p class="muted small">'+h(methods[state.current.method])+' · 修订 '+state.current.revision+'</p></div><button type="button" data-action="reload" class="quiet">重新打开项目</button></div><section class="panel"><h2>01 / 把问题说清楚</h2><form id="research-problem">'+field("想研究的问题","question",problem.question,4000,true,true)+field("发生在什么情境","context",problem.context,4000,true)+'<div class="two">'+field("什么变化才有意义","goal",problem.goal,2000,true)+field("时间、资料与资源限制","constraints",problem.constraints,2000,true)+'</div><p class="policy-hint">先记录已有认识和缺项，再决定采用哪种方法。问题可以随着研究继续修订。</p><div class="actions"><button class="primary" type="submit">保存问题卡</button>'+(state.assets.some(a=>a.kind==="problem")?'<button type="button" class="quiet" data-action="history" data-id="problem">查看历次问题</button>':'')+'</div></form></section><section class="panel"><h2>02 / '+(state.editing?'修改研究记录':'留下一条研究记录')+'</h2><form id="research-record">'+field("记录标题","title",edit.title,160,false,true)+'<div class="two"><label class="field">记录类型<select name="record_type">'+options(types,edit.record_type||"note")+'</select></label><label class="field">内容来自<select name="provenance">'+options(origins,edit.provenance||"reported")+'</select></label></div>'+field("正文","text",edit.text,20000,true,true)+field("出处或资料说明（选填）","citation",edit.citation,2000)+field("本次获得了什么帮助（选填）","assistance",edit.assistance,1000)+'<label class="field">关联本项目已有依据（选填）<select name="ref"><option value="">暂不关联</option>'+state.assets.filter(a=>a.asset_id!==state.editing).map(a=>'<option value="'+h(a.asset_id)+'">'+h(a.content.title||a.content.question||"问题卡")+'</option>').join("")+'</select></label><div class="actions"><button class="primary" type="submit">'+(state.editing?'保存新版本':'保存研究记录')+'</button>'+(state.editing?'<button type="button" data-action="cancel-edit" class="quiet">取消修改</button>':'')+'</div></form></section><section class="panel"><h2>03 / 联动本人伴学资料</h2><p class="small muted">明确选择某个学科中的本机文字资料，建立只读引用。返回科研时仍保留当前项目；伴学的学科与学习状态独立。</p><div class="two"><label class="field">资料所在工作区<select id="research-source-subject">'+options(subjects,state.status.workspace?.active||"legacy")+'</select></label><div class="field"><span>读取所选范围</span><button type="button" data-action="load-sources">查看这份资料库</button></div></div><div id="research-source-list"></div></section><section class="panel"><h2>研究过程与依据 <span class="muted small">'+records.length+' 条</span></h2>'+(records.length?records.map(assetCard).join(""):'<p class="muted">从一次观察、一段材料或一个待检验的解释开始记录。</p>')+'</section>';
    work.insertAdjacentHTML("beforeend",'<section id="research-workflow"></section>');
    window.dispatchEvent(new CustomEvent("research:render"));
  }
  function assetCard(a) {
    const b=a.content;
    if(a.kind==="companion_material") {
      const subject=(state.status.workspace?.subjects||[]).find(s=>s.id===b.source.subject)?.name||'本机历史资料';
      return '<article class="asset"><span class="tag">伴学资料引用</span><h3>'+h(b.title)+'</h3><p class="muted small">来源工作区：'+h(subject)+' · 来源修订 '+b.source.revision+'</p><div class="actions"><button type="button" data-action="resolve" data-id="'+h(a.asset_id)+'">打开并核对来源</button><button type="button" class="quiet" data-action="history" data-id="'+h(a.asset_id)+'">引用记录</button></div></article>';
    }
    return '<article class="asset"><div class="provenance"><span class="tag">'+h(types[b.record_type])+'</span><span class="tag">'+h(origins[b.provenance])+'</span><span class="tag">版本 '+a.revision+'</span></div><h3>'+h(b.title)+'</h3><p>'+h(b.text)+'</p>'+(b.citation?'<p class="small muted">出处：'+h(b.citation)+'</p>':'')+'<div class="actions"><button type="button" class="quiet" data-action="edit" data-id="'+h(a.asset_id)+'">修改并保留旧版</button><button type="button" class="quiet" data-action="history" data-id="'+h(a.asset_id)+'">查看版本</button></div></article>';
  }
  async function openProject(id) {
    const result=await call("research.project.read",{},false,null,id);
    state.current=result.result.project; state.assets=result.result.assets; state.editing=null; state.sources=[];
    state.projects=(await call("research.project.list")).result.projects;
    const url=new URL(location.href);url.searchParams.set("project",id);history.replaceState(null,"",url);
    try{sessionStorage.setItem('hyper-growth:research:'+state.status.device_id,id);}catch(_){}
    shell();
    if(result.result.coverage.truncated) notice("当前显示最近200条记录，完整历史仍保存在项目中。");
  }
  function showDialog(title,html) {
    document.getElementById("research-dialog-content").innerHTML='<h2>'+h(title)+'</h2>'+html;
    document.getElementById("research-dialog").showModal();
  }
  app.addEventListener("input", event => { const form=event.target.closest("form"); if(form) delete form.dataset.requestId; });
  app.addEventListener("submit", async event => {
    const form=event.target;if(!form.id.startsWith("research-")) return;
    event.preventDefault();if(form.dataset.busy) return;
    form.dataset.busy="1";const button=form.querySelector('button[type="submit"]');button.disabled=true;
    form.dataset.requestId ||= uid();
    try{
      const data=Object.fromEntries(new FormData(form));let result;
      if(form.id==="research-create"){
        result=await call("research.project.create",data,false,form.dataset.requestId);
        await openProject(result.result.project.id);document.querySelector('#research-problem textarea')?.focus();notice("项目已建立。先记录想研究的问题。");
      }else if(form.id==="research-problem"){
        result=await call("research.problem.save",data,true,form.dataset.requestId);await openProject(state.current.id);
        const missing=result.checks.missing||[];notice(missing.length?"已保存。可继续补充："+missing.join("、"):"问题卡已保存。");
      }else if(form.id==="research-record"){
        const ref=state.assets.find(a=>a.asset_id===data.ref)?.ref;delete data.ref;
        const previous=state.assets.find(a=>a.asset_id===state.editing)?.content.refs||[];
        data.refs=[...previous];
        if(ref&&!data.refs.some(r=>r.asset_id===ref.asset_id&&r.revision===ref.revision))data.refs.push(ref);
        if(state.editing) data.asset_id=state.editing;
        result=await call("research.record.save",data,true,form.dataset.requestId);await openProject(state.current.id);notice("研究记录已保存，旧版本继续保留。");
      }
    }catch(error){notice(error.message,true);}finally{delete form.dataset.busy;if(button.isConnected)button.disabled=false;}
  });
  app.addEventListener("click", async event=>{
    const button=event.target.closest("button[data-action]");if(!button) return;
    const id=button.dataset.id;button.disabled=true;
    try{
      if(button.dataset.action==="open") await openProject(id);
      else if(button.dataset.action==="reload") await openProject(state.current.id);
      else if(button.dataset.action==="edit"){state.editing=id;renderWork();document.querySelector('#research-record input')?.focus();}
      else if(button.dataset.action==="cancel-edit"){state.editing=null;renderWork();}
      else if(button.dataset.action==="history"){
        const result=await call("research.asset.history",{asset_id:id});
        showDialog("历次记录",result.result.versions.map(a=>'<div class="history"><h3>版本 '+a.revision+'</h3><p>'+h(a.content.text||a.content.question||a.content.title)+'</p><p class="small muted">'+h(a.created)+'</p></div>').join(""));
      }else if(button.dataset.action==="resolve"){
        const asset=state.assets.find(a=>a.asset_id===id);
        const result=await call("research.asset.resolve",{ref:asset.ref});
        showDialog(asset.content.title,'<div class="history">'+h(result.result.selection)+'</div><p class="small muted">来源与所引版本一致。内容是否支持研究结论，仍需结合问题判断。</p>');
      }else if(button.dataset.action==="load-sources"){
        const subject=document.getElementById("research-source-subject").value;
        state.sources=(await call("research.companion.sources",{subject})).result.materials;
        document.getElementById("research-source-list").innerHTML=state.sources.length?'<label class="field">选择资料<select id="research-source-choice">'+state.sources.map((m,i)=>'<option value="'+i+'">'+h(m.title)+'</option>').join("")+'</select></label><button type="button" data-action="link-source">将所选资料引用到当前项目</button>':'<p class="small muted">这个工作区尚无本人文字资料。可在伴学资料库保存后再来选择。</p>';
      }else if(button.dataset.action==="link-source"){
        const selected=state.sources[Number(document.getElementById("research-source-choice").value)];
        const {title,...source}=selected;
        await call("research.companion.link",source,true);await openProject(state.current.id);notice("已建立只读资料引用。");
      }
    }catch(error){notice(error.message,true);}finally{if(button.isConnected)button.disabled=false;}
  });
  document.getElementById("research-dialog-close").addEventListener("click",()=>document.getElementById("research-dialog").close());
  async function boot(){
    try{
      state.status=await jsonFetch("/api/local/status");
      if(!state.status.profile?.role){app.innerHTML='<div class="empty"><h1>先建立本机身份</h1><p>科研与伴学共享本机身份，研究内容按项目独立保存。</p><a href="/">返回本机入口完成设置</a></div>';return;}
      state.projects=(await call("research.project.list")).result.projects;
      let remembered=null;
      try{remembered=sessionStorage.getItem('hyper-growth:research:'+state.status.device_id);}catch(_){}
      const selected=new URLSearchParams(location.search).get("project")||(state.projects.some(p=>p.id===remembered)?remembered:null);
      if(selected) await openProject(selected); else shell();
    }catch(error){app.innerHTML='<div class="empty"><h1>科研空间尚未打开</h1><p>'+h(error.message)+'</p><a href="/">从本机入口重新打开</a></div>';}
  }
  window.ResearchWorkbench={state,h,field,options,notice,jsonFetch,call,openProject,showDialog,methods};
  boot();
})();
