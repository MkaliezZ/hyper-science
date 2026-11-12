# 开发续接 / Development handoff

本仓库从2026-11-12核对的私有工程工作区导出。原HEAD不含全部科研变更，因此使用工作树文件哈希固定快照；没有导入私库Git历史。PUBLICATION.json记载范围，docs/source-snapshot.json记录原样复制文件的SHA256。复制后的发行元数据、入口与公开文档独立维护。

## 实现位置

- src/base/app/research：科研三层实现，功能层vendor保存固定Skill子集。
- src/base/app/product_runtime.py、module_links.py、product_lock.py：模块分派、只读联动与产品锁。
- src/growth_local：共享本机网页、MCP与科研前端；保留必要伴学代码以确保运行与兼容。
- docs/contracts：research.capability.v1/v2及共享宿主契约快照。
- requirements-local.lock / requirements-research.lock：主程序与独立执行器的锁文件。
- tests/test_research_foundation.py / test_research_workflow.py：隔离、负例、来源、任务及真实工具测试。

## 验证命令

```powershell
$env:PYTHONPATH = Join-Path $PWD 'src'
.venv-local/Scripts/python.exe scripts/check_public_source.py
.venv-local/Scripts/python.exe scripts/check.py
.venv-local/Scripts/python.exe -m pytest tests -q
$scienceTests = @(Get-ChildItem tests -Filter *.test.cjs | ForEach-Object FullName)
node --test @scienceTests
.venv-local/Scripts/python.exe scripts/verify_research.py
.venv-local/Scripts/python.exe scripts/verify_research_workflow.py --tag public-source
```

最后两个脚本实际启动本机HTTP与stdio/HTTP-MCP，写入忽略的data/verify和artifacts目录；数据为合成。默认不发外部文献请求；--external需要主动选择。密钥扫描另用Gitleaks扫描工作树及提交历史。固定上游文件由check_public_source.py核对，不能静默改写后重算哈希。

## D0—D6与下一步

现有基线覆盖D0接入核对、D1独立项目、D2资料与检索、D3方向与计划、D4实验/模拟与成果、D5方法工程案例及D6本机验收。历史通过结论不自动适用于新修改；本公开快照的实跑结果见VALIDATION.md。

下一阶段按具体问题选择：领域人员审阅方法与反例；接入材料等专用模型并做现实校准；真实模型服务与使用者验收；父级五模块统一入口和权限契约。不得把后三个预留模块说成已实现，也不得把固定排队模型描述成通用科研模拟引擎。

开发时保持契约与层间边界；修改可追溯资产需要版本化。公开文档仅列本次可公开的源码范围，原本机私有运行证据、历史快照与分发包不复制进来。

English: This source snapshot exports reviewed working-tree bytes rather than private Git history. Preserve the three-layer research boundaries, shared Runtime contracts and explicit companion linkage. Run existing tests and real local HTTP/MCP verification after runtime changes. Publication checks do not substitute for domain review, model calibration or real-user acceptance.
