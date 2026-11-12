"""Pure content identities; a reference is not an access credential."""
import hashlib
import json
import re

PROJECT = re.compile(r"rp-[0-9a-f]{32}\Z")
ASSET = re.compile(r"(problem|ra-[0-9a-f]{32})\Z")

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def project_id(value):
    if not isinstance(value, str) or not PROJECT.fullmatch(value):
        raise ValueError("科研项目标识无效")
    return value

def asset_id(value):
    if not isinstance(value, str) or not ASSET.fullmatch(value):
        raise ValueError("研究记录标识无效")
    return value

def reference(project, row):
    return {"project_id": project, "asset_id": row["id"], "revision": row["version"],
            "sha256": row["sha256"], "kind": row["kind"]}

def checked_body(row):
    value = json.loads(row["body"])
    if digest(value) != row["sha256"]:
        raise ValueError("研究记录完整性检查失败")
    return value
