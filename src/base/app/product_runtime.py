"""Shared module routing for 超维成长; sibling modules keep separate business state."""
MODULES = [
    {"id": "companion", "name": "超维伴学", "state": "available", "path": "/"},
    {"id": "research", "name": "超维科研", "state": "foundation", "path": "/research/"},
    {"id": "projects", "name": "超维项目", "state": "planned", "path": None},
    {"id": "planning", "name": "超维规划", "state": "planned", "path": None},
    {"id": "links", "name": "超维链接", "state": "planned", "path": None},
]

class ProductRuntime:
    def __init__(self, runtime):
        from base.app.companion.functional.workspaces import host
        root = getattr(runtime, "root", None) or getattr(runtime, "workspace_root", runtime)
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "companion", host(root))

    @property
    def workspace_root(self):
        return self.root

    def __getattr__(self, name):
        return getattr(self.companion, name)

    def __setattr__(self, name, value):
        if name in {"network", "session_key"}:
            setattr(self.root, name, value)
        else:
            object.__setattr__(self, name, value)

    def invoke_capability(self, raw):
        if isinstance(raw, dict) and str(raw.get("contract_version", "")).startswith("research."):
            return self.root.invoke_capability(raw)
        return self.companion.invoke_capability(raw)

def product_host(runtime):
    return runtime if isinstance(runtime, ProductRuntime) else ProductRuntime(runtime)
