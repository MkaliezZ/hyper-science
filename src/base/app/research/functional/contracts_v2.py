"""Additive research workflow contract; v1 remains frozen."""
from typing import Any, Literal
from pydantic import Field, model_validator
from .contracts import Strict, ProjectId, AssetId, Method, RecordSave as RecordV1

Kind = Literal['problem','record','companion_material','source','search','screening','direction','plan','experiment','design','simulation','report','review']
class AssetRef(Strict):
    project_id: ProjectId
    asset_id: AssetId
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    kind: Kind

class Request(Strict):
    contract_version: Literal['research.capability.v2']
    request_id: str = Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')
    capability: str
    project_id: ProjectId
    expected_revision: int | None = Field(default=None,ge=0)
    input: dict[str,Any] = Field(default_factory=dict)

class Source(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1,max_length=160)
    text: str = Field(min_length=1,max_length=200000)
    citation: str = Field(default='',max_length=2000)
    provenance: Literal['observed','reported','assumed','synthetic'] = 'reported'
    content_scope: Literal['full_text','excerpt','abstract','metadata'] = 'excerpt'

class RecordSave(RecordV1):
    refs: list[AssetRef] = Field(default_factory=list,max_length=16)

class LocalSearch(Strict):
    query: str = Field(min_length=1,max_length=200)
    limit: int = Field(default=10,ge=1,le=30)

class Resolve(Strict):
    ref: AssetRef
    start: int = Field(default=0,ge=0)
    end: int | None = Field(default=None,gt=0)

class RefOnly(Strict):
    ref: AssetRef

class SearchSelection(Strict):
    search_ref: AssetRef
    index: int = Field(ge=0,le=59)
    decision: Literal['include','exclude']
    reason: str = Field(min_length=1,max_length=2000)

class Direction(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1,max_length=160)
    independent_ideas: str = Field(min_length=1,max_length=8000)
    candidates: str = Field(default='',max_length=12000)
    selection: str = Field(default='',max_length=4000)
    criteria: str = Field(default='',max_length=4000)
    rivals: str = Field(default='',max_length=4000)
    refs: list[AssetRef] = Field(default_factory=list,max_length=16)

class Plan(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1,max_length=160)
    method: Method
    question: str = Field(min_length=1,max_length=4000)
    materials: str = Field(default='',max_length=4000)
    procedure: str = Field(default='',max_length=8000)
    counterevidence: str = Field(default='',max_length=4000)
    analysis: str = Field(default='',max_length=4000)
    limitations: str = Field(default='',max_length=4000)
    refs: list[AssetRef] = Field(default_factory=list,max_length=16)

class Experiment(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1,max_length=160)
    unit: str = Field(min_length=1,max_length=2000)
    comparison: str = Field(min_length=1,max_length=4000)
    measurement: str = Field(min_length=1,max_length=4000)
    independent_replication: str = Field(min_length=1,max_length=4000)
    randomization: str = Field(default='',max_length=4000)
    controls: str = Field(default='',max_length=4000)
    disconfirming: str = Field(default='',max_length=4000)
    analysis: str = Field(default='',max_length=4000)
    constraints: str = Field(default='',max_length=4000)
    refs: list[AssetRef] = Field(default_factory=list,max_length=16)

class Evidence(Strict):
    ref: AssetRef
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1,max_length=4000)
    relation: Literal['supports','contradicts','context'] = 'context'

class Claim(Strict):
    text: str = Field(min_length=1,max_length=4000)
    status: Literal['finding','interpretation','hypothesis','proposal']
    evidence: list[Evidence] = Field(default_factory=list,max_length=12)

class Report(Strict):
    asset_id: AssetId | None = None
    title: str = Field(min_length=1,max_length=160)
    method: str = Field(min_length=1,max_length=8000)
    claims: list[Claim] = Field(min_length=1,max_length=30)
    limitations: str = Field(min_length=1,max_length=8000)
    next_steps: str = Field(default='',max_length=4000)
    assistance: str = Field(default='',max_length=2000)

class Review(Strict):
    report_ref: AssetRef
    feedback: str = Field(min_length=1,max_length=8000)
    next_revision: str = Field(default='',max_length=4000)

class RemoteSearch(Strict):
    query: str = Field(min_length=1,max_length=240)
    providers: list[Literal['crossref','openalex','arxiv']] = Field(default_factory=lambda:['crossref'],min_length=1,max_length=3)
    limit: int = Field(default=10,ge=1,le=20)
    year_from: int | None = Field(default=None,ge=1500,le=2100)
    year_to: int | None = Field(default=None,ge=1500,le=2100)
    @model_validator(mode='after')
    def years(self):
        if self.year_from and self.year_to and self.year_from>self.year_to: raise ValueError('年份范围无效')
        if len(set(self.providers))!=len(self.providers): raise ValueError('检索源不能重复')
        return self

class ParseFile(Strict):
    title: str = Field(min_length=1,max_length=160)
    filename: str = Field(min_length=1,max_length=160,pattern=r'^[^/\\:]+\.(pdf|txt|md|csv|json)$')
    base64: str = Field(min_length=4,max_length=11200000)
    citation: str = Field(default='',max_length=2000)
    provenance: Literal['observed','reported','assumed','synthetic'] = 'reported'

class Scaffold(Strict):
    direction_ref: AssetRef

class Generate(Strict):
    direction_ref: AssetRef
    refs: list[AssetRef] = Field(default_factory=list,max_length=8)
    instruction: str = Field(default='',max_length=2000)
    send_selected_to_model: Literal[True]

class Design(Strict):
    experiment_ref: AssetRef
    method: Literal['blocked','simple','factorial','latin_hypercube']
    n: int = Field(default=20,ge=2,le=1000)
    arms: list[str] = Field(default_factory=lambda:['A','B'],min_length=2,max_length=6)
    factors: dict[str,list[float]] = Field(default_factory=dict,max_length=6)
    seed: int = Field(default=20261103,ge=0,le=2147483647)

class Simulation(Strict):
    experiment_ref: AssetRef
    model_id: Literal['bounded-queue.v1'] = 'bounded-queue.v1'
    input_provenance: Literal['observed','reported','assumed','synthetic']
    input_source: str = Field(min_length=1,max_length=2000)
    refs: list[AssetRef] = Field(default_factory=list,max_length=8)
    assumptions: str = Field(min_length=1,max_length=4000)
    horizon: float = Field(default=120,gt=0,le=10000,allow_inf_nan=False)
    mean_interarrival: float = Field(default=4,ge=0.01,le=10000,allow_inf_nan=False)
    mean_service: float = Field(default=6,ge=0.01,le=10000,allow_inf_nan=False)
    servers: list[int] = Field(default_factory=lambda:[2,3],min_length=1,max_length=4)
    queue_capacity: int = Field(default=20,ge=0,le=1000)
    replications: int = Field(default=10,ge=2,le=30)
    base_seed: int = Field(default=20261103,ge=0,le=2147483647)
    max_entities: int = Field(default=2000,ge=1,le=10000)
    max_events: int = Field(default=40000,ge=10,le=100000)
    @model_validator(mode='after')
    def budget(self):
        if any(type(x)!=int or x<1 or x>100 for x in self.servers) or len(set(self.servers))!=len(self.servers): raise ValueError('窗口数量无效或重复')
        if self.max_events*self.replications*len(self.servers)>5000000: raise ValueError('模拟总事件预算超过500万')
        return self

TASKS={'source.parse':ParseFile,'search.remote':RemoteSearch,'direction.scaffold':Scaffold,
       'direction.generate':Generate,'design.generate':Design,'simulation.run':Simulation,'report.audit':RefOnly}
class JobStart(Strict):
    task: Literal['source.parse','search.remote','direction.scaffold','direction.generate','design.generate','simulation.run','report.audit']
    parameters: dict[str,Any]

class JobId(Strict):
    job_id: str = Field(pattern=r'^rj-[0-9a-f]{32}$')
class Empty(Strict): pass
class Export(Strict):
    format: Literal['markdown','json'] = 'markdown'
    report_ref: AssetRef | None = None

INPUTS={'research.source.save':Source,'research.source.screen':SearchSelection,
        'research.source.original':RefOnly,'research.search.local':LocalSearch,
        'research.direction.save':Direction,'research.plan.save':Plan,'research.experiment.save':Experiment,
        'research.report.save':Report,'research.review.save':Review,'research.record.save':RecordSave,
        'research.asset.resolve':Resolve,'research.project.export':Export,
        'research.job.start':JobStart,'research.job.get':JobId,'research.job.cancel':JobId,
        'research.job.retry':JobId,'research.job.list':Empty,'research.workflow.describe':Empty}

class Result(Strict):
    contract_version: Literal['research.capability.v2'] = 'research.capability.v2'
    request_id: str
    capability: str
    execution_state: Literal['succeeded'] = 'succeeded'
    result: dict[str,Any]
    refs: list[AssetRef] = Field(default_factory=list)
    checks: dict[str,Any] = Field(default_factory=dict)
