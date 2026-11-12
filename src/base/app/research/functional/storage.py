"""Project-isolated SQLite, append-only versions and encrypted-backup adapters."""
import json
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path
from base.core import now
from base.app.research.assets.references import canonical, digest, project_id, checked_body

@contextmanager
def database(path):
    if path.is_symlink():
        raise ValueError("科研数据路径不能是符号链接")
    with closing(sqlite3.connect(path, timeout=15)) as db:
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise

def folder(runtime):
    path = runtime.folder / "research"
    if path.is_symlink():
        raise ValueError("科研目录不能是符号链接")
    path.mkdir(exist_ok=True)
    return path

def project_path(base, pid):
    project_id(pid)
    path = base / "projects" / pid
    if any(p.is_symlink() for p in [base, base / "projects", path]):
        raise ValueError("科研项目路径不能是符号链接")
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("科研项目路径越界")
    return path

@contextmanager
def registry(runtime):
    with database(folder(runtime) / "registry.sqlite3") as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,owner TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,result TEXT NOT NULL);
        """)
        row = db.execute("SELECT value FROM meta WHERE key='owner'").fetchone()
        if row and row[0] != runtime.identity.id:
            raise PermissionError("科研登记不属于当前本机身份")
        db.execute("INSERT OR IGNORE INTO meta VALUES ('owner',?)", (runtime.identity.id,))
        db.commit()
        yield db

def metadata(db):
    row = db.execute("SELECT value FROM meta WHERE key='project'").fetchone()
    if not row:
        raise ValueError("科研项目缺少登记")
    return json.loads(row[0])

@contextmanager
def project(runtime, pid):
    with registry(runtime) as reg:
        row = reg.execute("SELECT owner FROM projects WHERE id=?", (pid,)).fetchone()
        if not row or row[0] != runtime.identity.id:
            raise PermissionError("科研项目不存在或不属于当前本机身份")
    path = project_path(folder(runtime), pid) / "research.sqlite3"
    if not path.is_file():
        raise ValueError("科研项目数据缺失")
    with database(path) as db:
        value = metadata(db)
        if value["id"] != pid or value["owner_device_id"] != runtime.identity.id:
            raise PermissionError("科研项目身份或目录不一致")
        yield db

def replay(db, key, fingerprint):
    prior = db.execute("SELECT fingerprint,result FROM receipts WHERE id=?", (key,)).fetchone()
    if prior:
        if prior["fingerprint"] != fingerprint:
            raise ValueError("同一操作编号的内容已改变，请使用新的操作编号")
        return json.loads(prior["result"])

def remember(db, key, fingerprint, value):
    db.execute("INSERT INTO receipts VALUES (?,?,?)", (key, fingerprint, canonical(value).decode()))

def create(runtime, request, payload):
    fingerprint = digest(request.model_dump(mode="json"))
    pid = "rp-" + digest([runtime.identity.id, request.request_id])[:32]
    with registry(runtime) as reg:
        reg.execute("BEGIN IMMEDIATE")
        prior = replay(reg, request.request_id, fingerprint)
        if prior:
            saved_path = project_path(folder(runtime), prior["project"]["id"]) / "research.sqlite3"
            if not saved_path.is_file():
                raise ValueError("科研项目数据缺失")
            with database(saved_path) as saved:
                if metadata(saved)["owner_device_id"] != runtime.identity.id:
                    raise PermissionError("科研项目不属于当前本机身份")
            return prior
        if reg.execute("SELECT COUNT(*) FROM projects").fetchone()[0] >= 200:
            raise ValueError("当前科研项目已达200个，请先整理现有项目")
        path = project_path(folder(runtime), pid)
        path.mkdir(parents=True, exist_ok=True)
        with database(path / "research.sqlite3") as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assets(id TEXT NOT NULL,version INTEGER NOT NULL,kind TEXT NOT NULL,
                    body TEXT NOT NULL,sha256 TEXT NOT NULL,author TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(id,version));
                CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,result TEXT NOT NULL);
            """)
            existing = db.execute("SELECT value FROM meta WHERE key='project'").fetchone()
            if existing:
                value = json.loads(existing[0])
                if value.get("creation_fingerprint") != fingerprint or value.get("owner_device_id") != runtime.identity.id:
                    raise ValueError("科研项目创建记录冲突")
            else:
                value = {"id": pid, **payload, "owner_device_id": runtime.identity.id, "revision": 0,
                         "created": now(), "creation_fingerprint": fingerprint}
                db.execute("INSERT INTO meta VALUES ('project',?)", (canonical(value).decode(),))
        reg.execute("INSERT INTO projects VALUES (?,?)", (pid, runtime.identity.id))
        result = {"project": public_project(value)}
        remember(reg, request.request_id, fingerprint, result)
        return result

def public_project(value):
    return {k: v for k, v in value.items() if k != "creation_fingerprint"}

def list_projects(runtime):
    with registry(runtime) as db:
        ids = [r[0] for r in db.execute("SELECT id FROM projects WHERE owner=? ORDER BY rowid DESC", (runtime.identity.id,))]
    values = []
    for pid in ids:
        with project(runtime, pid) as db:
            values.append(public_project(metadata(db)))
    return values

def latest(db, aid):
    return db.execute("SELECT * FROM assets WHERE id=? ORDER BY version DESC LIMIT 1", (aid,)).fetchone()

def append(db, aid, kind, body, owner):
    previous = latest(db, aid)
    if previous and previous["kind"] != kind:
        raise ValueError("不能更改研究记录类型")
    version = previous["version"] + 1 if previous else 1
    value = canonical(body).decode()
    db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
               (aid, version, kind, value, digest(body), owner, now()))
    return latest(db, aid)

def bump(db):
    value = metadata(db)
    value["revision"] += 1
    db.execute("UPDATE meta SET value=? WHERE key='project'", (canonical(value).decode(),))
    return public_project(value)

def validate_backup(base, owner):
    research = Path(base) / "research"
    if not research.exists():
        return []
    if research.is_symlink() or not (research / "registry.sqlite3").is_file():
        raise ValueError("科研恢复包缺少项目登记")
    with database(research / "registry.sqlite3") as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("科研登记完整性检查失败")
        row = db.execute("SELECT value FROM meta WHERE key='owner'").fetchone()
        if not row or row[0] != owner:
            raise ValueError("科研恢复包设备身份不一致")
        rows = db.execute("SELECT id,owner FROM projects").fetchall()
        ids = [r["id"] for r in rows]
        if any(r["owner"] != owner for r in rows):
            raise ValueError("科研项目归属不一致")
    projects = research / "projects"
    present = {p.name for p in projects.iterdir()} if projects.exists() else set()
    if present != set(ids):
        raise ValueError("科研项目目录与登记不一致")
    for pid in ids:
        path = project_path(research, pid) / "research.sqlite3"
        if not path.is_file():
            raise ValueError("科研项目数据库缺失")
        with database(path) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("科研项目数据库完整性检查失败")
            value = metadata(db)
            if value["id"] != pid or value["owner_device_id"] != owner:
                raise ValueError("科研项目恢复身份不一致")
            for row in db.execute("SELECT * FROM assets"):
                checked_body(row)
    return ids

def backup_into(runtime, archive, temporary):
    research = runtime.folder / "research"
    if not research.exists():
        return
    ids = validate_backup(runtime.folder, runtime.identity.id)
    names = ["research/registry.sqlite3"] + ["research/projects/" + pid + "/research.sqlite3" for pid in ids]
    for name in names:
        dest = temporary / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with database(runtime.folder / name) as live, closing(sqlite3.connect(dest)) as snapshot:
            live.backup(snapshot)
        archive.write(dest, name)
