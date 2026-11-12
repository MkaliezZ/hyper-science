"""D1 checks use synthetic local devices; they do not validate research effectiveness."""
import ast
import asyncio
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from base.app.local_runtime import LocalRuntime
from base.app.local_backup import export_backup, restore_backup
from base.app.product_runtime import product_host
from base.app.research.functional import storage
from base.app.research.functional.contracts import Request, Result, INPUTS
from growth_local.web import create_app
from growth_local.mcp import create_mcp
from test_local_runtime import instance, MemoryVault
from test_workspaces import w, select
from test_companion_study import material

def raw(op, p=None, project=None, revision=None, key=None):
    result={"contract_version":"research.capability.v1","request_id":key or uuid4().hex,
            "capability":"research."+op,"input":p or {}}
    if project:result["project_id"]=project
    if revision is not None:result["expected_revision"]=revision
    return result

def call(r, op, p=None, project=None, revision=None, key=None):
    return r.invoke_capability(raw(op,p,project,revision,key))

def create(r, title="合成研究", method="undecided", key=None):
    return call(r,"project.create",{"title":title,"method":method},key=key)["result"]["project"]

def read(r, p):
    return call(r,"project.read",project=p["id"])["result"]

def test_create_problem_versions_receipts_restart_and_no_ability_claim(tmp_path):
    r=instance(tmp_path,"student","S")
    p=create(r,method="humanities",key="create-once")
    assert create(r,method="humanities",key="create-once")==p
    with pytest.raises(ValueError):create(r,title="changed",key="create-once")
    request=raw("problem.save",{"question":"这段地方史材料如何解释？"},p["id"],0,"problem-once")
    result=r.invoke_capability(request)
    assert result["checks"]["missing"] and result["checks"]["domain_review"]=="not_reviewed"
    assert "材料" in result["checks"]["guidance"]
    first=result["refs"][0]
    record=call(r,"record.save",{"title":"初始观察","text":"合成片段","provenance":"synthetic","refs":[first]},p["id"],1)
    assert record["checks"]["ability_judgment"]=="not_assessed"
    assert r.invoke_capability(request)==result
    with pytest.raises(ValueError):call(r,"problem.save",{"question":"过期修改"},p["id"],0)
    call(r,"problem.save",{"question":"修订后的问题","context":"合成情境"},p["id"],2)
    versions=call(r,"asset.history",{"asset_id":"problem"},p["id"])["result"]["versions"]
    assert [x["revision"] for x in versions]==[2,1]
    assert versions[1]["content"]["question"]=="这段地方史材料如何解释？"
    restarted=LocalRuntime(r.folder,r.vault)
    assert read(restarted,p)["project"]["revision"]==3
    assert call(restarted,"asset.resolve",{"ref":first},p["id"])["result"]["selection"]=="这段地方史材料如何解释？"
    assert not read(restarted,p)["policy"].get("mastery")

def test_projects_isolated_tampered_refs_rejected_and_no_raw_actor(tmp_path):
    r=instance(tmp_path/"a","teacher","T");a=create(r,"A");b=create(r,"B")
    result=call(r,"record.save",{"title":"A私有记录","text":"SYNTHETIC PRIVATE A"},a["id"],0)
    ref=result["refs"][0]
    assert not read(r,b)["assets"]
    with pytest.raises(PermissionError):call(r,"asset.resolve",{"ref":ref},b["id"])
    with pytest.raises(PermissionError):call(r,"record.save",{"asset_id":ref["asset_id"],"title":"跨项目改写","text":"x"},b["id"],0)
    with pytest.raises(ValueError):call(r,"asset.resolve",{"ref":{**ref,"sha256":"0"*64}},a["id"])
    bad=raw("project.list");bad["actor_id"]="teacher"
    with pytest.raises(ValueError):r.invoke_capability(bad)
    with pytest.raises(ValueError):r.invoke_capability({**raw("project.read"),"project_id":"../../outside"})
    other=instance(tmp_path/"b","student","S")
    shutil.copytree(r.folder/"research",other.folder/"research")
    with pytest.raises(PermissionError):call(other,"project.list")
    with r.db() as db:
        assert not any(x[0].startswith('research_') for x in db.execute("SELECT name FROM sqlite_master").fetchall())

def test_source_bridge_is_explicit_owned_versioned_and_does_not_switch_subject(tmp_path):
    r=instance(tmp_path,"student","S");w(r,"initialize");select(r,"english")
    source=material(r);p=create(r)
    source_text=r.invoke_capability({'contract_version':'companion.capability.v2','request_id':'source-actual',
        'operation':'material.read','payload':{'material_id':source['id']}})['data']['text']
    select(r,"mathematics")
    host=product_host(r)
    listing=host.invoke_capability(raw("companion.sources",{"subject":"english"}))["result"]["materials"]
    selected=next(x for x in listing if x["material_id"]==source["id"])
    selected.pop("title")
    linked=host.invoke_capability(raw("companion.link",selected,p["id"],0))
    assert host.current()=="mathematics" and read(host,p)["project"]["revision"]==1
    resolved=call(r,"asset.resolve",{"ref":linked["refs"][0]},p["id"])["result"]
    assert resolved["selection"]==source_text
    assert "text" not in read(r,p)["assets"][0]["content"]
    select(r,"english")
    r.invoke_capability({"contract_version":"companion.capability.v2","request_id":"change-source","operation":"material.save",
        "payload":{"material_id":source["id"],"expected_revision":source["revision"],"title":"changed","text":"changed text","source":"synthetic"}})
    select(r,"mathematics")
    with pytest.raises(ValueError,match="资料已更新"):call(r,"asset.resolve",{"ref":linked["refs"][0]},p["id"])
    assert read(r,p)["assets"][0]["content"]["source"]["source_hash"]==source["source_hash"]
    assert host.current()=="mathematics"

def test_shared_entry_keeps_research_independent_of_legacy_and_experience(tmp_path):
    r=instance(tmp_path,"student","S");w(r,"initialize");select(r,"legacy")
    host=product_host(r);p=create(host)
    assert host.current()=="legacy"
    before=host.invoke_capability({"contract_version":"companion.capability.v11","request_id":"e","operation":"experience.read","payload":{}})
    call(host,"record.save",{"title":"记录","text":"保持独立","provenance":"synthetic"},p["id"],0)
    after=host.invoke_capability({"contract_version":"companion.capability.v11","request_id":"e","operation":"experience.read","payload":{}})
    assert before==after
    select(r,"english");select(r,"mathematics")
    assert read(host,p)["assets"][0]["content"]["text"]=="保持独立"
    assert call(host,"describe")["result"]["relationship"]=="parallel_modules"
    assert not (r.folder/"subjects/mathematics/research").exists()

def test_optimistic_writes_and_creation_failure_retry(tmp_path,monkeypatch):
    r=instance(tmp_path,"teacher","T");p=create(r)
    def write(i):
        try:
            return call(r,"record.save",{"title":str(i),"text":"x"},p["id"],0)["execution_state"]
        except ValueError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write,range(2)))==["conflict","succeeded"]
    old=storage.remember
    def fail(*args):
        raise ValueError("synthetic interruption")
    with monkeypatch.context() as m:
        m.setattr(storage,"remember",fail)
        with pytest.raises(ValueError):create(r,"interrupted",key="retry-create")
    recovered=create(r,"interrupted",key="retry-create")
    assert recovered["revision"]==0
    assert len(call(r,"project.list")["result"]["projects"])==2
    assert len(storage.validate_backup(r.folder,r.identity.id))==2

def test_research_backup_recovery_and_integrity(tmp_path):
    r=instance(tmp_path/"source","student","S");p=create(r)
    saved=call(r,"record.save",{"title":"恢复测试","text":"合成可恢复记录"},p["id"],0)
    password="synthetic-password-12"
    encrypted=export_backup(r,password)
    restored=LocalRuntime(tmp_path/"restored",MemoryVault())
    restore_backup(restored,encrypted,password)
    restored=LocalRuntime(restored.folder,restored.vault)
    assert read(restored,p)["assets"][0]["content"]["text"]=="合成可恢复记录"
    assert restored.identity.id==r.identity.id
    with storage.project(r,p["id"]) as db:
        db.execute("UPDATE assets SET body=? WHERE id=?",('{"text":"tampered"}',saved["refs"][0]["asset_id"]))
    with pytest.raises(ValueError,match="完整性"):read(r,p)
    with pytest.raises(ValueError,match="完整性"):export_backup(r,password)

def test_authenticated_http_and_mcp_use_same_independent_facade(tmp_path):
    r=instance(tmp_path,"student","S");w(r,"initialize");select(r,"mathematics")
    app=create_app(r.folder,runtime=r,network=False)
    with TestClient(app,base_url="http://127.0.0.1") as client:
        request=raw("project.create",{"title":"网页闭环"},"",None,"web-create")
        assert client.post("/api/local/capabilities/invoke",json=request).status_code==401
        assert client.post("/api/local/session",json={"bootstrap":app.state.bootstrap}).status_code==200
        response=client.post("/api/local/capabilities/invoke",headers={"x-growth-workspace":"english"},json=request)
        assert response.status_code==200,response.text
        p=response.json()["result"]["project"]
        assert client.get("/research/").status_code==200
        assert client.get("/assets/research.js").status_code==200
        assert len(client.get("/api/local/modules").json()["modules"])==5
        assert client.post("/api/local/capabilities/invoke",headers={"x-growth-workspace":"english"},
            json={"request_id":"bad","operation":"architecture.describe"}).status_code==400
        request=raw("project.read",project=p["id"])
        expected=r.invoke_capability(request)
        assert client.post("/api/local/capabilities/invoke",json=request).json()==expected
        async def mcp_call():
            return await create_mcp(r).call_tool("invoke_research_capability",{"request":request})
        result=asyncio.run(mcp_call())
        actual=result[1] if isinstance(result,tuple) else json.loads(result[0].text if isinstance(result,list) else result.content[0].text)
        assert actual==expected
    assert product_host(r).current()=="mathematics"

def test_contract_snapshots_and_three_layer_dependencies():
    folder=Path(__file__).resolve().parents[1]
    for name,model in [("request",Request),("result",Result)]:
        assert json.loads((folder/("docs/contracts/research.capability.v1."+name+".schema.json")).read_text(encoding="utf8"))==model.model_json_schema()
    layer_root=folder/"src/base/app/research"
    assert {p.name for p in layer_root.iterdir() if p.is_dir() and not p.name.startswith("_")}=={"aesthetic","functional","assets"}
    banned={"aesthetic":["base.app.research.functional","base.app.research.assets","base.app.local_runtime","sqlite3","httpx","fastapi","subprocess"],
            "assets":["base.app.research.functional","base.app.research.aesthetic","base.app.local_runtime","sqlite3","httpx","fastapi","subprocess"],
            "functional":["base.app.local_runtime","growth_local","fastapi","base.app.companion"]}
    for layer,forbidden in banned.items():
        for file in (layer_root/layer).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf8"))):
                names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or ""] if isinstance(node,ast.ImportFrom) else []
                assert not any(n==prefix or n.startswith(prefix+".") for n in names for prefix in forbidden),(file,names)
