"""Real local HTTP/stdio-MCP/HTTP-MCP checks with synthetic data only."""
import argparse
import asyncio
import json
import logging
import os
import socket
import sys
from pathlib import Path
from uuid import uuid4
import httpx
import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from base.app.local_runtime import LocalRuntime
from base.app.product_runtime import product_host
from growth_local.web import create_app

ROOT = Path(__file__).resolve().parents[1]
logging.getLogger("httpx").setLevel(logging.WARNING)

def request(op, value=None, project=None, revision=None, key=None):
    raw = {"contract_version":"research.capability.v1","request_id":key or uuid4().hex,
           "capability":"research."+op,"input":value or {}}
    if project: raw["project_id"] = project
    if revision is not None: raw["expected_revision"] = revision
    return raw

def fixture():
    folder = ROOT / "data/verify" / ("research-" + uuid4().hex)
    runtime = LocalRuntime(folder)
    runtime.setup("student", "合成科研验证")
    host = product_host(runtime)
    host.initialize(); host.select("english","materials")
    material = host.invoke_capability({"contract_version":"companion.capability.v2","request_id":"fixture-material",
        "operation":"material.save","payload":{"title":"合成观察材料","text":"这是用于工程验证的合成材料：三个服务窗口在不同时段形成不同队列。","source":"Original synthetic engineering fixture"}})["data"]["material"]
    host.select("mathematics","materials")
    return runtime, host, folder, material

async def main(serve=False, port=0):
    runtime, host, folder, material = fixture()
    app = create_app(folder, runtime=host, network=False)
    sock=socket.socket();sock.bind(("127.0.0.1",port));sock.listen(128);port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level="error",access_log=False))
    if serve:
        (folder/"qa-url.txt").write_text("http://127.0.0.1:"+str(port)+"/#start="+app.state.bootstrap,encoding="utf8")
        print(json.dumps({"synthetic":True,"port":port,"url_file":str(folder/"qa-url.txt")},ensure_ascii=False),flush=True)
        await server.serve(sockets=[sock]);return
    serving=asyncio.create_task(server.serve(sockets=[sock]))
    headers={"Authorization":"Bearer "+runtime.service.base.owner_token}
    async def mcp_call(raw, web):
        async def run(session):
            await session.initialize()
            result=await session.call_tool("invoke_research_capability",{"request":raw})
            assert not result.isError, str(result.content)
            return result.structuredContent or json.loads(result.content[0].text)
        if web:
            async with streamablehttp_client("http://127.0.0.1:"+str(port)+"/mcp/",headers=headers) as (read,write,_):
                async with ClientSession(read,write) as session:return await run(session)
        env={**os.environ,"PYTHONPATH":str(ROOT/"src"),"PYTHONUTF8":"1"}
        async with stdio_client(StdioServerParameters(command=sys.executable,
            args=["-m","growth_local","--mcp","--data",str(folder)],env=env)) as (read,write):
            async with ClientSession(read,write) as session:return await run(session)
    checks=[]
    try:
        for _ in range(100):
            if server.started:break
            await asyncio.sleep(.05)
        async with httpx.AsyncClient(base_url="http://127.0.0.1:"+str(port),headers=headers,trust_env=False,timeout=30) as client:
            async def cap(raw):
                response=await client.post("/api/local/capabilities/invoke",json=raw)
                response.raise_for_status();return response.json()
            raw=request("project.create",{"title":"合成服务流程研究","method":"design"},key="three-entry-create")
            created=await cap(raw)
            assert await mcp_call(raw,False)==created and await mcp_call(raw,True)==created
            pid=created["result"]["project"]["id"];checks.append("HTTP/independent stdio MCP/HTTP MCP create same idempotent project")
            raw=request("problem.save",{"question":"怎样改进服务流程？","context":"合成工程示例","goal":"明确比较依据"},pid,0)
            saved=await mcp_call(raw,False)
            assert await cap(raw)==saved and await mcp_call(raw,True)==saved
            checks.append("three-entry problem write receipt and refs agree")
            selected={"subject":"english","material_id":material["id"],"revision":material["revision"],"source_hash":material["source_hash"]}
            linked=await cap(request("companion.link",selected,pid,1))
            ref=linked["refs"][0]
            resolved=await cap(request("asset.resolve",{"ref":ref},pid))
            assert "合成材料" in resolved["result"]["selection"]
            assert host.current()=="mathematics"
            checks.append("explicit companion source link keeps current subject and project independent")
            second=(await cap(request("project.create",{"title":"隔离项目"})))["result"]["project"]
            denied=await client.post("/api/local/capabilities/invoke",json=request("asset.resolve",{"ref":ref},second["id"]))
            assert denied.status_code==403
            checks.append("cross-project reference rejected through real HTTP")
            raw=request("project.read",project=pid)
            expected=await cap(raw)
            assert await mcp_call(raw,False)==expected and await mcp_call(raw,True)==expected
            checks.append("three-entry project read preserves same sources and versions")
            assert (await client.get("/research/")).status_code==200
            for name in ["research.js","research.css","research-entry.js"]:
                assert (await client.get("/assets/"+name)).status_code==200
            modules=(await client.get("/api/local/modules")).json()
            assert len(modules["modules"])==5 and modules["relationship"]=="parallel_modules"
            checks.append("research page and assets served; five sibling modules declared with planned states")
        report={"ok":True,"date":"2026-11-03","phase":"D0-D1","synthetic_only":True,
                "real_user_data_modified":False,"model_called":False,"simulation_run":False,
                "domain_review":"not_reviewed","checks":checks,"data_folder":str(folder)}
        output=ROOT/"artifacts/research-foundation-transport.json";output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        print(json.dumps(report,ensure_ascii=False))
    finally:
        server.should_exit=True
        await serving

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--serve",action="store_true",help="Serve a new isolated synthetic browser fixture")
    parser.add_argument("--port",type=int,default=0)
    args=parser.parse_args()
    asyncio.run(main(args.serve,args.port))
