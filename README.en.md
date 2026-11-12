# Hyper Science · 超维科研

[中文](README.md) · [User guide](docs/USER-GUIDE.en.md) · [Architecture](docs/ARCHITECTURE.md) · [Development](docs/DEVELOPMENT.md) · [Contributing](CONTRIBUTING.en.md) · [Licenses](LICENSES.md)

A local workspace for investigating real problems across science, humanities, society, design and everyday life. Define a question, collect traceable sources, choose a method, plan experiments or bounded simulations, then write and revise evidence-linked reports.

This is the public source snapshot of research workflow v0.2. The required shared BASE, identity, companion adapters and web/MCP host are included. The research module is parallel to the learning module under the future Hyper Growth parent. Projects, planning and connections remain reserved module descriptors. Shared host names/versions remain compatible; the distribution is named `hyper-science`.

Three layers retain separate responsibilities: **aesthetic** defines research judgement and standards; **functional** enforces contracts, authorization and execution; **assets** handles provenance, versioning, integrity and locators. Companion links read only explicitly selected, versioned personal text sources.

## Features

- Projects, problem cards, records, method-aware direction and research plans.
- UTF-8 text and text-bearing PDF import, local search and exact quote/version checks.
- Explicit public searches through Crossref, OpenAlex and arXiv.
- Experimental units, independent replication, controls and disconfirming evidence; randomization, two-level factorial and Latin hypercube tables.
- A bounded SimPy queue model with independent runs, parameter provenance and intervals; cancellable/retryable jobs.
- Evidence-linked claims, versioned reports, feedback, Markdown and JSON export. Optional models use the user's own configuration.

The built-in simulation models queues. Materials microstructure, mechanical properties and finite-element solvers require dedicated adapters. Source integrity checks do not establish semantic support or scientific validity.

## Run from source on Windows

Install `uv`. The host uses Python3.11 and research workers use Python3.12. The lock files preserve the Windows environment; other platforms are unverified in this publication.

```powershell
git clone https://github.com/MkaliezZ/hyper-science.git
cd hyper-science
powershell -ExecutionPolicy Bypass -File scripts/setup_science.ps1
powershell -ExecutionPolicy Bypass -File scripts/start_science.ps1
```

Create a local identity in the host page, then open 超维科研. The startup script creates a fresh instance under `data/science`. Basic manual work needs no model key. See the [user guide](docs/USER-GUIDE.en.md) for data and linkage boundaries.

## Curated open-source Skills

Pinned upstream: `K-Dense-AI/scientific-agent-skills` at `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`. Ten selected Skills inform rules or supply helpers: scientific-brainstorming, scientific-critical-thinking, hypothesis-generation, literature-review, paper-lookup, citation-management, liteparse, scientific-writing, experimental-design and simpy.

Only selected documents and unmodified helper files are vendored, with per-file hashes and MIT/Apache notices. This is not a full upstream or global Skill installation. [Implementation scope](docs/research-workflow-v02.md).

The [6061 materials example](examples/materials-6061/README.md) contains 12 synthetic hardness rows and a four-combination planning example. These are not measurements or process recommendations. A previously requested video recording remains incomplete and is not included.

See [validation](docs/VALIDATION.md) and [publication scope](PUBLICATION.json). Private project data, credentials, databases, screenshots and historical binaries are excluded. Original code retains the [MIT license](LICENSE); third-party scope is described in [LICENSES.md](LICENSES.md).
