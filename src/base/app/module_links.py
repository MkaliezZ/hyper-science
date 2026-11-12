"""Explicit, read-only cross-module links. No project access is inferred from pairing."""
def companion_source(runtime, subject):
    from base.app.companion.functional.workspaces import host, materialize
    spaces = host(runtime)
    source = spaces.root if subject == "legacy" else spaces.runtime(subject)
    materialize(source)
    return source

def companion_materials(runtime, subject):
    source = companion_source(runtime, subject)
    value = source._invoke_capability({"contract_version": "companion.capability.v2",
        "request_id": "research-source-list", "operation": "material.list", "payload": {}})["data"]
    return [{"material_id": m["id"], "revision": m["revision"], "source_hash": m["source_hash"],
             "title": m["title"], "subject": subject}
            for m in value["materials"] if m["owner_ref"] == "device:" + runtime.identity.id]

def read_companion_material(runtime, value):
    source = companion_source(runtime, value["subject"])
    current = source._invoke_capability({"contract_version": "companion.capability.v2",
        "request_id": "research-source-read", "operation": "material.read",
        "payload": {"material_id": value["material_id"]}})["data"]
    if current["owner_ref"] != "device:" + runtime.identity.id:
        raise PermissionError("目前仅可联动本人本机资料")
    if current["revision"] != value["revision"] or current["source_hash"] != value["source_hash"]:
        raise ValueError("伴学资料已更新，请重新选择并建立引用")
    start, end = value.get("start", 0), value.get("end")
    text = current["text"]
    end = len(text) if end is None else end
    if start >= end or end > len(text) or end - start > 20000:
        raise ValueError("请选择1—20000字的有效资料片段")
    return {"title": current["title"], "text": text[start:end], "source": value,
            "quality": {"processing": "readable", "claim_support": "unassessed", "domain_review": "not_reviewed"}}
