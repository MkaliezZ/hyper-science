"""Strict v1 foundation contracts. Trusted device identity is never in the payload."""
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

ProjectId = Annotated[str, Field(pattern=r"^rp-[0-9a-f]{32}$")]
AssetId = Annotated[str, Field(pattern=r"^(problem|ra-[0-9a-f]{32})$")]
Method = Literal["undecided", "empirical", "qualitative", "humanities", "design", "simulation"]

class AssetRef(Strict):
    project_id: ProjectId
    asset_id: AssetId
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["problem", "record", "companion_material"]

class Request(Strict):
    contract_version: Literal["research.capability.v1"]
    request_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    capability: Literal["research.describe", "research.project.create", "research.project.list",
        "research.project.read", "research.problem.save", "research.record.save",
        "research.asset.resolve", "research.asset.history", "research.companion.sources", "research.companion.link"]
    project_id: ProjectId | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    input: dict[str, Any] = Field(default_factory=dict)

class Empty(Strict):
    pass

class ProjectCreate(Strict):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    method: Method = "undecided"

class ProblemSave(Strict):
    question: str = Field(min_length=1, max_length=4000)
    context: str = Field(default="", max_length=4000)
    goal: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)

class RecordSave(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=20000)
    record_type: Literal["observation", "interpretation", "hypothesis", "decision", "reflection", "note", "evidence"] = "note"
    provenance: Literal["observed", "reported", "assumed", "synthetic"] = "reported"
    citation: str = Field(default="", max_length=2000)
    assistance: str = Field(default="", max_length=1000)
    refs: list[AssetRef] = Field(default_factory=list, max_length=16)

class Resolve(Strict):
    ref: AssetRef
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, gt=0)

class History(Strict):
    asset_id: AssetId

class CompanionLink(Strict):
    subject: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    material_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, gt=0)

class CompanionSources(Strict):
    subject: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")

class Result(Strict):
    contract_version: Literal["research.capability.v1"] = "research.capability.v1"
    request_id: str
    capability: str
    execution_state: Literal["succeeded"]
    result: dict[str, Any]
    refs: list[AssetRef] = Field(default_factory=list)
    checks: dict[str, Any] = Field(default_factory=dict)

INPUTS = {
    "research.describe": Empty, "research.project.create": ProjectCreate, "research.project.list": Empty,
    "research.project.read": Empty, "research.problem.save": ProblemSave, "research.record.save": RecordSave,
    "research.asset.resolve": Resolve, "research.asset.history": History, "research.companion.link": CompanionLink,
    "research.companion.sources": CompanionSources,
}
