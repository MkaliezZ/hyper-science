"""Owner-scoped research facade, independent of companion subject selection."""
from uuid import uuid4
from pydantic import ValidationError
from base.app.research.aesthetic import rules
from base.app.research.assets.references import reference, checked_body, digest
from base.app.research.functional import storage
from base.app.research.functional.contracts import Request, Result, INPUTS

def nonblank(value, field):
    if not value[field].strip():
        raise ValueError("标题、问题或正文不能为空")
    value[field] = value[field].strip()

def packed(pid, row):
    content = checked_body(row)
    if row['kind'] == 'source':
        content = {k: v for k, v in content.items() if k != '_original_base64'}
    return {"asset_id": row["id"], "revision": row["version"], "kind": row["kind"],
            "content": content, "created": row["created"], "ref": reference(pid, row)}

def resolve(runtime, db, pid, ref):
    if ref.project_id != pid:
        raise PermissionError("引用不属于当前科研项目")
    row = db.execute("SELECT * FROM assets WHERE id=? AND version=?", (ref.asset_id, ref.revision)).fetchone()
    if not row:
        raise PermissionError("研究记录不属于当前项目或版本不存在")
    if row["sha256"] != ref.sha256 or row["kind"] != ref.kind:
        raise ValueError("研究引用的版本或内容校验失败")
    value = packed(pid, row)
    if row["kind"] == "companion_material":
        from base.app.module_links import read_companion_material
        value["linked_source"] = read_companion_material(runtime, value["content"]["source"])
    return value

def describe():
    from .executors import worker_python
    try:
        worker_python(); simulation_available = True
    except ValueError:
        simulation_available = False
    return {"module": "research", "brand": "超维科研", "parent": "超维成长",
            "relationship": "parallel_modules", "scope": "current_device_owner_projects",
            "layers": {"aesthetic": "研究判断与证据要求", "functional": "能力、授权与执行", "assets": "来源、版本与定位"},
            "capabilities": list(INPUTS), "policy": rules.describe(),
            "validation": {"skills_installed": True, "skill_scope": "curated_internal_adapters", "simulation_available": simulation_available, "domain_review": "not_reviewed"},
            "sharing": "项目协作与跨设备分享尚未接入"}

def invoke(runtime, raw):
    runtime = getattr(runtime, "workspace_root", runtime)
    if runtime.role not in {"teacher", "student"}:
        raise PermissionError("请先完成本机身份设置")
    if isinstance(raw, dict) and raw.get('contract_version') == 'research.capability.v2':
        from .service_v2 import invoke as workflow_invoke
        return workflow_invoke(runtime, raw)
    try:
        request = Request.model_validate(raw)
        payload = INPUTS[request.capability].model_validate(request.input).model_dump(mode="json")
    except (ValidationError, KeyError, ValueError):
        raise ValueError("科研请求格式无效，请核对操作、必填项、长度与引用格式") from None
    from base.app.product_lock import lock
    with lock(runtime.folder):
        data, refs, checks = execute(runtime, request, payload)
    return Result(request_id=request.request_id, capability=request.capability, execution_state="succeeded",
                  result=data, refs=refs, checks=checks).model_dump(mode="json")

def execute(runtime, r, p):
    op = r.capability
    if op == "research.describe":
        return describe(), [], {}
    if op == "research.project.create":
        if r.project_id is not None or r.expected_revision is not None:
            raise ValueError("创建项目无需已有项目或修订号")
        nonblank(p, "title")
        return storage.create(runtime, r, p), [], {}
    if op == "research.project.list":
        return {"projects": storage.list_projects(runtime)}, [], {}
    if op == "research.companion.sources":
        from base.app.module_links import companion_materials
        return {"materials": companion_materials(runtime, p["subject"])}, [], {}
    if not r.project_id:
        raise ValueError("请先选择科研项目")
    pid = r.project_id
    with storage.project(runtime, pid) as db:
        if op == "research.project.read":
            value = storage.metadata(db)
            rows = db.execute("SELECT a.* FROM assets a WHERE id!='problem' AND version=(SELECT MAX(version) FROM assets b WHERE b.id=a.id) ORDER BY rowid DESC LIMIT 200").fetchall()
            problem = storage.latest(db, "problem")
            rows = ([problem] if problem else []) + list(rows)
            total = db.execute("SELECT COUNT(DISTINCT id) FROM assets").fetchone()[0]
            return {"project": storage.public_project(value), "assets": [packed(pid, row) for row in rows],
                    "coverage": {"returned": len(rows), "total": total, "truncated": total > len(rows)},
                    "policy": rules.describe()}, [], {}
        if op == "research.asset.resolve":
            from base.app.research.functional.contracts import AssetRef
            value = resolve(runtime, db, pid, AssetRef.model_validate(p["ref"]))
            text = value.get("linked_source", {}).get("text") if value["kind"] == "companion_material" else value["content"].get("text", value["content"].get("question", ""))
            end = len(text) if p["end"] is None else p["end"]
            if p["start"] >= end or end > len(text):
                raise ValueError("研究引用文字范围无效")
            value["selection"] = text[p["start"]:end]
            return value, [p["ref"]], {"integrity": "checked", "claim_support": "unassessed"}
        if op == "research.asset.history":
            rows = db.execute("SELECT * FROM assets WHERE id=? ORDER BY version DESC", (p["asset_id"],)).fetchall()
            if not rows:
                raise PermissionError("研究记录不属于当前项目")
            return {"versions": [packed(pid, row) for row in rows]}, [], {}
        db.execute("BEGIN IMMEDIATE")
        fingerprint = digest(r.model_dump(mode="json"))
        prior = storage.replay(db, r.request_id, fingerprint)
        if prior:
            return prior["data"], prior["refs"], prior["checks"]
        current = storage.metadata(db)
        if r.expected_revision is None or current["revision"] != r.expected_revision:
            raise ValueError("项目已更新或缺少修订号，请重新打开后再保存")
        if op == "research.problem.save":
            nonblank(p, "question")
            row = storage.append(db, "problem", "problem", p, runtime.identity.id)
            checks = rules.assess_problem(p, current["method"])
        elif op == "research.record.save":
            from base.app.research.functional.contracts import AssetRef
            nonblank(p, "title"); nonblank(p, "text")
            aid = p.pop("asset_id") or "ra-" + uuid4().hex
            if aid == "problem" or (r.input.get("asset_id") and not storage.latest(db, aid)):
                raise PermissionError("只能修改当前项目已有的研究记录")
            for ref in p["refs"]:
                resolve(runtime, db, pid, AssetRef.model_validate(ref))
            row = storage.append(db, aid, "record", p, runtime.identity.id)
            checks = rules.record_checks(p)
        elif op == "research.companion.link":
            from base.app.module_links import read_companion_material
            source = read_companion_material(runtime, p)
            body = {"source": p, "title": source["title"], "relation": "explicit_read_only_link",
                    "source_module": "companion", "target_module": "research"}
            row = storage.append(db, "ra-" + uuid4().hex, "companion_material", body, runtime.identity.id)
            checks = {"source_integrity": "checked_at_link_creation", "claim_support": "unassessed"}
        else:
            raise ValueError("该科研能力尚未实现")
        data = {"project": storage.bump(db), "asset": packed(pid, row)}
        refs = [reference(pid, row)]
        storage.remember(db, r.request_id, fingerprint, {"data": data, "refs": refs, "checks": checks})
        return data, refs, checks
