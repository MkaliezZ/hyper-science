# 公开源码核验 / Public-source validation

核验日期：2026-11-12。范围是本次公开目录的源码与锁定环境，不继承旧安装包的验收结论。

| 检查 / Check | 结果 / Result |
|---|---|
| Windows PowerShell安装入口 | 从独立目录创建Python3.11主环境和Python3.12.7科研环境；79项主依赖、10项科研依赖安装完成，完整安装命令和VerifyOnly均成功 |
| Python回归 | 226个独立用例最终通过：首轮225通过，1项因导出时遗漏configure.py失败；补齐原样配置工具后，该用例单独复验通过 |
| 前端状态与导航 | 32通过，0失败 |
| 基本管线 | 创建、提交、反馈、重启读取通过；仅合成数据 |
| 真实基础三入口 | HTTP、独立stdio MCP、HTTP MCP六组检查通过，含幂等、版本、跨项目拒绝、只读伴学联动、网页资源与模块状态 |
| 真实科研工作流 | 七组检查通过，含方向底稿、PDF解析、项目内检索、真实DOE、真实SimPy、简报/修订/导出和两种MCP调用 |
| Skill固定文件 | manifest中的29份文件与原哈希一致 |
| 包内容 | wheel构建与CRC通过，29份固定上游文件及worker/科研网页完整；wheel不是独立运行安装包 |
| 发布边界与文档 | 原样复制文件哈希、作者文档的本地链接与禁止文件范围检查通过 |
| 密钥扫描 | Gitleaks8.30.1对待发布文件及初始提交历史检查无泄漏发现；本地安装依赖与运行目录不属于发布范围 |

首轮Python全量测试使用既有Python3.11锁定依赖读取本公开目录源码；遗漏工具复验、实际HTTP/MCP及完整安装检查使用新建环境。科研worker使用本目录新建的独立Python3.12环境。所有运行数据和原始日志保存在忽略目录或本机发布工作目录，没有加入Git。

公开副本修复了安装脚本在Windows PowerShell原生参数传递中的引号问题；原私有工程没有被修改。发行元数据补齐Skill文档、许可和worker的包内数据。docs/source-snapshot.json区分原样复制文件与改编安装脚本的原始哈希。

未在本次发布执行：浏览器人工交互验收、视频录制、真实模型服务调用、外部文献实时检索、专业方法审定、真实材料试验/模型校准、真人效果评价、其他操作系统及独立安装包发布。本次没有复制或公开原本机截图、原始工程证据、身份密钥或个人项目。

English: 226 unique Python cases ultimately passed (225 initially, one rechecked after restoring an omitted original configuration helper), plus 32 front-end checks, the basic pipeline, six foundation transport checks and seven workflow checks. Fresh Windows environments installed successfully. Pinned helper integrity, wheel content/CRC, local authored-document links, publication boundaries and Gitleaks scans passed. Engineering checks do not validate scientific conclusions, real models, human use or a public standalone installer. No private source data or credentials are published.
