# 超维科研基础：D0接入与D1本机项目闭环

本页保留2026-11-03的D0/D1基础阶段说明；最新工作流、运行方式与边界见[科研工作流v0.2](research-workflow-v02.md)。

2026-11-03，D1源码工程版。超维科研与超维伴学是超维成长下的平行板块；超维项目、超维规划、超维链接为后续独立接入的业务模块。科研内的“研究项目”仅指本模块研究对象。

## 使用

按本工程原方式安装锁定依赖并启动growth_local。完成本机身份后，伴学页面顶部有“超维科研”入口，也可在同一会话打开/research/。研究页面可返回伴学，伴学学科与体验模式保持独立。

1. 建立研究项目，选择适用的方法方向或“尚未确定”。
2. 保存问题卡中的问题、情境、目标与限制；缺项可继续补充。
3. 记录观察、解释、假设、决策、反思或札记，注明来源及本次帮助。
4. 修改追加版本，可打开历史；并发冲突时重新打开项目再保存。
5. 在“联动本人伴学资料”明确选择资料工作区，读取本人本机文字材料列表并建立引用。
6. 打开引用时重新核对源版本。来源已变化时保留原引用记录，要求重新选择，不静默替换。
7. 使用原本机加密恢复包备份，科研登记和逐项目数据库一并保存。

本阶段只提供本人本机研究空间，不自动共享给配对老师/学生。实验设计、模拟运行、检索/解析、AI研究工具与成果编写尚未接入。

## 三层与共享入口

- research/aesthetic：问题条件、方法提示、来源声明及成长判断边界；无数据库、模型与网络导入。
- research/assets：纯内容身份、哈希、版本与引用；不提供权限。
- research/functional：严格契约、项目权限、事务、存储与编排。
- product_runtime：超维成长统一模块分派适配器，沿用原伴学门面并独立路由科研。
- module_links：显式跨模块资料适配，不把资料引入科研视为获得伴学的全部权限。
- product_lock：共享本机跨进程锁；原companion workspace_lock保留兼容导入。

共享设备身份和配置保留原数据位置，不迁移已有伴学记录。科研数据位于research/，伴学学科位于subjects/；科研项目选择不影响伴学学科，反之亦然。

## 契约与存储

统一HTTP能力入口仍为POST /api/local/capabilities/invoke。新增MCP工具invoke_research_capability，均使用research.capability.v1。操作为research.describe、project.create/list/read、problem.save、record.save、asset.resolve/history、companion.sources/link。

完整能力名均带research.前缀。身份不得由请求体自报；项目修改带expected_revision。相同request_id与相同输入重试返回同一回执；同编号不同输入拒绝。请求与结果Schema位于docs/contracts/research.capability.v1.*.schema.json；具体输入模型位于functional/contracts.py。

项目登记为research/registry.sqlite3，每个项目独立research/projects/rp-<id>/research.sqlite3；记录追加版本并绑定SHA256。加密恢复前校验项目登记、设备身份、数据库完整性和内容哈希。

本地拥有者拥有自己的项目，所谓跨项目隔离指引用/修改不能借错误项目范围访问另一项目记录，不是伪造同一设备上已有多用户账号。多人协作需另行实现项目授权。

## 检查

~~~powershell
$env:PYTHONPATH = "$PWD/src"
.venv-local/Scripts/python.exe -m pytest tests/test_research_foundation.py tests/test_local_runtime.py tests/test_workspaces.py tests/test_companion_architecture.py tests/test_experience.py tests/test_base.py tests/test_base_teaching.py -q
.venv-local/Scripts/python.exe scripts/check.py
.venv-local/Scripts/python.exe scripts/verify_research.py
node --test tests/experience.test.cjs tests/student-state.test.cjs tests/student-navigation.test.cjs tests/navigation.test.cjs
~~~

verify_research.py仅创建合成本机测试设备，实际通过HTTP、独立stdio MCP和HTTP MCP调用能力；--serve可启动独立合成浏览器验证空间，默认不启动配对网络。测试环境和正常用户数据分开。

源码通过不代表官网安装包、模型研究质量、真实实验/模拟、专业方法或真人效果通过。当前未构建或发布安装包。更完整的设计和阶段计划见科研开发文档包。
