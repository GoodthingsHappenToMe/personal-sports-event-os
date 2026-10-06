# 架构入口

当前版本采用真正的模块内核。完整架构与插件协议见 [V1_1_ARCHITECTURE.md](../V1_1_ARCHITECTURE.md)。

- kernel/：通用身份、注册、依赖、结构、版本、证据、快照、存储、模块级Diff。
- modules/：独立业务schema、validator、calculate、diff、export。
- application/：稳定服务与显式v1.0迁移/兼容适配器。
- cli.py：调用应用服务，无深层业务实现导入。
- validators/legacy_checks/：仅v1.0兼容域检查。

旧架构已保存在 [v1_0/ARCHITECTURE.md](v1_0/ARCHITECTURE.md)，只说明旧数据格式，不代表当前Kernel。

## v1.1.1 增量（当前契约）

[原架构](../V1_1_ARCHITECTURE.md)是v1.1基线；本节和[加固报告](../V1_1_1_HARDENING.md)记录当前差异，主分层不变。

- Registry增加通用optional_capabilities，存在则进入拓扑排序，不存在不强制启用；冲突仍BLOCK。
- 批准与数据版本只存在于ModuleState，payload只含业务事实（v1.2起Pricing/Rule不再嵌入行级批准字段）。Module.prepare_revision保留为兼容钩子，默认复制输入；内置模块不再覆盖它。ApplicationService决定何时失效/批准。Kernel不含票价或规则字段名。
- 新写接口：get_module_data、update_module_data、apply_changeset、approve_module、approve_project、import_project、migrate_project。既有create/open/list/enable/disable/replace/validate/calculate/compare/snapshot/list_snapshots/export继续使用。
- 写操作和迁移先返回独立Project，save_project验证后持久化；patch只替换已有typed path，失败不改输入。单用户工作版本递增-rN，非多写者乐观锁。
- 新JSON导入统一DRAFT。外部TOML变化被识别为工作配置变化，不接受其批准声明。GUI不直接改Project内部对象；这是一条应用工程边界，不是恶意插件/管理员安全边界。
- 原快照及数据格式format_version=1.1、SN11前缀保持；插件/schema升级只显式迁移工作态。旧发布件不重写，不用新模块重算旧快照。

### 当前Provider依赖（运行时Registry导出）

|模块|必需能力|可选能力|提供能力|具体模块依赖/可选|
|---|---|---|---|---|
|core.schedule|—|venues|schedule|— / —|
|core.venue|—|—|venues|— / —|
|demand.direct|capacity|—|demand|— / —|
|demand.multiplicative|capacity|—|demand|— / —|
|finance.revenue|capacity, demand, prices, schedule|rights|—|— / —|
|product.pass|capacity, prices|—|—|— / —|
|product.travel|capacity, prices|—|—|— / —|
|project.decisions|—|—|—|— / —|
|project.tasks|—|schedule|—|— / —|
|quality.declarations|schedule|—|—|— / finance.revenue|
|ticketing.identity|schedule|—|—|— / —|
|ticketing.inventory|capacity|rights|—|— / —|
|ticketing.launch|schedule|—|—|— / —|
|ticketing.pricing|schedule|—|prices|— / —|
|ticketing.refund|schedule|—|—|— / —|
|ticketing.rights|capacity, prices|—|rights|— / —|
|ticketing.rights_return|schedule|—|—|— / —|
|ticketing.seating|schedule, prices|—|capacity|— / —|
|ticketing.transfer|schedule|—|—|— / —|

quality.declarations的可选finance.revenue依赖保留：该模块summary明确使用该输出结构，不是通用金额能力。其他本轮审查模块已按能力消费。

## v1.2 验证结果（Findings）

- 模块validate/cross_validate不再在第一处错误抛异常，而是通过 `modules.common.Checks` 收集全部问题。每条Finding有具体rule_id（如 `PRICE_PRECISION`、`INVENTORY_POOL_TOTAL`），source为编辑器字段路径 `模块ID/rows/行号/字段`，桌面端可直接定位到字段。
- 内核按依赖图验证：某模块存在BLOCK时，依赖它的模块不再运行验证，只记录一条 `DEPENDENCY_BLOCKED`（actual为阻断的上游模块），避免重复报错或在坏输入上崩溃。
- `M_INPUT`/`M_CROSS` 仍保留为兜底：只在插件代码抛出未预期异常时出现，表示插件需要修正，而不是正常的输入错误。
- 第三方插件建议：`ck=self.checks(gate)`（RowsModule）或 `Checks(gate, module_id)`，用 `ck(条件, rule_id, source, message, expected, actual, severity)` 记录问题；`require()` 只用于计算阶段的不变式。

## v1.2 代码布局

|位置|内容|
|---|---|
|`src/sports_os/kernel/`|业务无关内核：Project/Module契约、Registry、Gate、Store（唯一工作库）、Snapshot、Diff|
|`src/sports_os/modules/`|内置业务模块；每个模块提供schema、验证、计算及展示元数据（display_name/category/description）|
|`src/sports_os/application/`|ApplicationService（CLI与桌面端共用）、manifest、schema文件与数据字典生成|
|`src/sports_os/desktop/`|桌面端sidecar（JSON Lines协议）|
|`src/sports_os/cli.py`|命令行|
|`src/sports_os_legacy/`|冻结的v1.0代码：单文档模型、旧门禁、收入引擎、版本、导出、旧CLI（`--legacy`）及v1.0→模块化适配器|
|`apps/desktop/src/`|桌面前端：`App.tsx`为会话外壳，`pages/`为各页面，`views/`为侧栏、向导、错误与批准对话框，`Editor.tsx`为schema驱动编辑器|

内核、业务模块和sidecar在导入时不加载 `sports_os_legacy`（有测试保证）。`sports_os.application` 只在三处按需使用：`--legacy`、`migrate-v10` 和生成Demo（Demo由v1.0示例经适配器生成，两种格式描述同一虚构赛事）。
