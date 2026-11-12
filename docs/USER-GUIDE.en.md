# Hyper Science user guide

[中文](USER-GUIDE.zh-CN.md) · [Home](../README.en.md)

1. Follow the Windows setup/start commands. Create a local identity in the host page, then open 超维科研. The default launcher uses a fresh repository-local instance.
2. Create a project. In 问题与记录, save the question, context, intended change and constraints.
3. In 资料与检索, paste text or import an original UTF-8/text-bearing PDF file. Limits: 8MB per file and 50 PDF pages. OCR and Office conversion are outside this version. Record source and content scope.
4. Search within the project and recheck source versions. Explicitly choose public literature queries through Crossref/OpenAlex/arXiv. Metadata is not paper full text.
5. In 方向与计划, save your own ideas, alternatives, selection criteria and rival explanations before generating a scaffold. Optional model candidates require your configuration and selected material. Save the method, procedure, analysis and limitations.
6. In 实验与模拟, define units, comparisons, measurements, independent replication, controls and disconfirming observations. Select the saved experiment and generate a randomization, two-level factorial or Latin hypercube table. Planned combinations are distinct from independently executed replicates.
7. The built-in simulation is a bounded queue model. Record units, provenance, assumptions, repetitions and seed. It cannot predict materials hardness or microstructure. Inspect failed jobs before explicitly retrying.
8. In 成果与复盘, distinguish findings, interpretations, hypotheses and proposals. Associate exact source quotes, document limitations, save the report, add feedback, revise and export. Quote integrity does not establish semantic support.

Use the [6061 example](../examples/materials-6061/README.md) as planning practice. All 12 hardness rows are synthetic; factor levels are illustrative. No automatic materials statistics are performed on the imported CSV.

Local data persist in data/science. Never publish this folder or private project JSON. JSON is a review archive; full encrypted host backup is required to restore identity, pairing and all modules. Companion links require explicit selection within the same instance. A fresh instance cannot access another instance's data. Keep existing data intact and back up through its normal host before integration.

If research workers are missing, rerun scripts/setup_research.ps1 and its -VerifyOnly check. Scan-only PDFs need a separately obtained text copy. On revision conflicts, reload current records before saving. Model configuration is optional for manual work.

This source release provides text instructions. A recorded video, illustrated Word/PDF guide and public standalone installer are not included.
