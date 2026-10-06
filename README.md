# Sports Event OS Modular Kernel v1.2.0

## v1.2 变化（升级前请阅读）

- **批准只记录在模块状态**：Pricing 和五个规则模块的 rows 不再含 price_version/version/status/approval_ref。已有 v1.1.x 工作目录需运行一次 `migrate-project`，迁移后重新人工批准变化的模块和项目。
- **一次报告全部问题**：每条问题有具体 rule_id，source 指向字段（如 `ticketing.pricing/rows/3/price`）；上游模块有阻断时，下游只记一条 `DEPENDENCY_BLOCKED`。
- **唯一工作副本**：桌面端未完成草稿保存在 `data/modular.sqlite`，命令行看到的是同一份草稿；`discard-draft` 可放弃。打开后被其他程序保存过的工作区会拒绝覆盖（退出码3 / 桌面端 CONFLICT）。
- **命令行**：新增 `status`（列出待批准模块和下一步命令）；退出码 0 成功、1 门禁阻断、2 输入错误、3 冲突；`diff` 支持 `WORKING` 和快照ID。
- **代码结构**：v1.0 代码移到 `src/sports_os_legacy`；桌面前端拆分为 `pages/` 和 `views/`；模块提供展示名称。详见 [架构](docs/ARCHITECTURE.md)。
- **新建项目更简单**：只需名称和活动类型；ID、时区、文件夹和所需模块自动处理，创建后按“开始设置”清单逐步填写（见下文“新建项目”）。启用模块时自动加入它需要的模块。
- 桌面端版本 0.2.0（协议 0.2）。

离线、确定性、完全合成数据的个人赛事工具。**Kernel 不认识票价、座席、退款或旅行包**；业务由可独立安装的 Python 模块提供。核心不依赖 GUI；无 AI、网络平台连接、自动定价或真实库存操作。

可选桌面端见 [Desktop README](apps/desktop/README.md)。**0.1.0 下载包存在签名缺陷，停止使用；0.1.1 为修复签名的未公证 macOS Apple Silicon 测试版，不是免确认的正式发行版。** 详情见 [打包修复报告](DESKTOP_V0_1_1_PACKAGING_REPORT.md)。

桌面操作说明：[受控中英双语使用说明](docs/USER_GUIDE_STE_EN_ZH.md)。以已发布 Desktop 0.1.1 为基线；两栏均使用受控写作规则，中文采用对应项目规则，不宣称正式 ASD-STE100 合规。

## 安装与测试

Python **3.11+**，推荐独立环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[excel]'
python -m unittest discover -s tests -v
python tests/run_v111_acceptance.py
```

Windows 激活用 `.venv\Scripts\activate`。核心仅标准库；`excel` 用于保留的只读 Excel 适配器及其测试。不要跳过包安装：模块来自安装元数据的 `sports_os.modules` entry points；仅设置 PYTHONPATH 不等于完成安装。离线且已有 setuptools≥68/openpyxl 时可 `python -m pip install --no-build-isolation --no-deps -e .`。

v1.1.1 历史基线为 **180 项**，桌面端与打包测试增至 **198 项**，validator polish 补丁及接入边界测试新增 **16 项**，当前 `unittest discover` 共 **214 项**（非 macOS 上 4 项打包测试按设计跳过）。本轮结果与边界见 [VALIDATOR_POLISH_REPORT.md](VALIDATOR_POLISH_REPORT.md)，历史结果见 [V1_1_1_TEST_REPORT.md](V1_1_1_TEST_REPORT.md)。所有输入均为虚构；旧业务测试断言、工作样本和批准快照保留，部分测试文件仅清理未使用 import。

当前完整回归使用 `python -m unittest discover -s tests`；`tests/run_v111_acceptance.py` 是固定 140 项旧测试计数的历史报告生成器，不适用于当前扩展后的全套测试，也不应覆盖冻结的历史证据。

## 立即运行

在项目根目录，选择一个**新的工作目录**（仓库根目录的工作库是保留的 v1.1 历史样本）：

```bash
python -m sports_os modules
python -m sports_os demo --workspace ./outputs/my-v111-event
python -m sports_os validate --workspace ./outputs/my-v111-event
python -m sports_os revenue --workspace ./outputs/my-v111-event
python -m sports_os diff version_a version_b --workspace ./outputs/my-v111-event
python -m sports_os snapshot --workspace ./outputs/my-v111-event
python -m sports_os status --workspace ./outputs/my-v111-event
```

Demo 是 **2027 Global Racket Masters**（16场、4阶段、5票档、8040物理席），使用模拟批准引用。上述命令生成当前schema的 Demo；重复运行不会覆盖已修改工作态。仓库原有v1.1样本需显式迁移，不能直接用新模块静默运行。每条命令均支持 `--workspace /path/to/local-workspace`，所有路径限制在该独立目录内，拒绝 `/Volumes` 与越界符号链接。

不售票项目也可完整运行：

```bash
python -m sports_os demo --profile non-ticketed-event --workspace ./outputs/my-free-event
python -m sports_os validate --workspace ./outputs/my-free-event
python -m sports_os snapshot --workspace ./outputs/my-free-event
```

Profile 仅预填启用清单。没有 `profile == ...` 业务分支，不是限定项目只能有三种模式。已有预设：`ticketed-indoor-event`、`multi-session-tournament`、`non-ticketed-event`。不售票预设没有任何票务数据要求。

## 输入、工作态与输出

|位置|用途|
|---|---|
|project.toml|工作态项目身份和模块启停配置；打开时显式读取|
|data/modular.sqlite|模块工作payload、模块版本、内容hash及不可变快照|
|data/modular_demo/*.json|可复现合成A/B输入样本，不是第二个自动同步数据源|
|data/schemas/modules/*.json|各模块独立schema；无巨型业务根schema|
|outputs/V1_1_QUALITY_GATE.json|质量结果；每条违规含rule_id、severity、message、source（字段路径）、expected、actual、suggested_action，且一次验证报告全部问题|
|outputs/V1_1_finance.revenue.json|精确收入预览、阶段/票档/场次汇总和敏感性|
|outputs/V1_1_DIFF.json|模块增删、元数据、模块自行解释的业务差异|
|outputs/releases/SN11-*/|冻结manifest、模块版本/hash、批准引用、结果和完整性清单|

退出码（v1.2）：0 成功（`validate` 为PASS或WARNING）；1 被质量门禁或发布规则阻断；2 参数或输入错误；3 工作区冲突（打开后被其他程序保存）。结果输出到stdout，错误输出到stderr。任何 BLOCK 禁止 calculation/snapshot/export。WARNING 创建快照需要 `--ack-warnings`。旧预览文件可能来自上一次成功运行；不要把“文件存在”当本次成功。

金额在服务层保留 Decimal。JSON 将 Decimal 输出为**精确十进制字符串**；这是计算结果，不是输入数值替代。只在阅读展示时四舍五入到分，不能将取整显示值回灌。分组显示额相加可能有分币尾差；精确汇总严格闭合。

## 修改、人工批准、启停、替换

所有界面业务写入必须走 ApplicationService；不要直接修改 `Project.states[*].payload` 或手填批准字段。

`update` 替换整个模块payload；`patch` 接受已有字段的结构化path数组，不是字符串路径。增加/删除行或可选字段用整份 `update`。

在新工作目录中创建 `price-patch.json`：

```json
[{"path": ["rows", 0, "price"], "value": 731}]
```

```bash
python -m sports_os patch ticketing.pricing price-patch.json --workspace ./outputs/my-v111-event
python -m sports_os validate --workspace ./outputs/my-v111-event
python -m sports_os snapshot --workspace ./outputs/my-v111-event
# 此时应BLOCK（退出码1）。status会列出待批准模块、实际版本号和按顺序要运行的批准命令：
python -m sports_os status --workspace ./outputs/my-v111-event
python -m sports_os approve-module ticketing.pricing --version '<实际data_version>' --approval-ref '<人工批准引用>' --workspace ./outputs/my-v111-event
python -m sports_os approve-project --version '<实际project version>' --approval-ref '<人工批准引用>' --workspace ./outputs/my-v111-event
python -m sports_os snapshot --workspace ./outputs/my-v111-event
```

尖括号内容必须替换，不是默认批准。批准接口只记录人工确认；没有auto_approve。canonical内容改变才生成 `原版本-r1/-r2/...`，清除模块和项目批准；完全相同payload不变。批准只记录在模块状态（ModuleState），不写入业务rows；批准不会产生业务diff。先批准变化模块，再批准项目，最后snapshot；旧snapshot不变。

`export-data` 可导出工作JSON；`load` 和 `--data` 是外部导入入口，统一按DRAFT处理，不继承输入声称的批准。`--data snapshot` 因未批准而BLOCK，应先load再明确批准。`save_project` 验证完整工作态后落盘；可以在内存中多次编辑修正跨模块约束，再统一保存。API返回副本，不会修改传入对象。

`diff` 的两个参数可以是 `WORKING`（当前工作副本）、快照ID（`SN11-...`）、`version_a`/`version_b`（Demo输入）或JSON文件，例如 `diff SN11-xxxx WORKING`。桌面端留下的未完成草稿也是命令行的工作副本；`discard-draft` 放弃草稿并回到上次保存的状态。`status --json` 输出机器可读结果。

所有命令都可指定 `--workspace`；例如 `disable product.travel`、`enable product.travel`、`calculate ticketing.rights`。

禁用保留payload以便重新启用，但不运行其schema/validator/calculation/diff/export，快照只包含启用模块的payload。未安装且禁用的模块也不会阻塞。启用新模块用 `--payload path/to/payload.json`；缺依赖、能力冲突或依赖环立即BLOCK，不静默补默认值。

替换 Demand 示例：`replace demand.multiplicative demand.direct --payload data/direct-demand.json`。数据结构见字典。更换插件实现可通过 `Registry.register(replacement, replace=True)` 显式注入；插件升级必须提供并执行 `migrate_module()`，旧payload不默认为兼容。

CLI启停/替换会把项目设为DRAFT，需要重新批准。独立产品、权益、收入、库存均可启停，但依赖和跨模块约束不会被绕过：**禁用Rights后库存仍含付费权益分配时，必须人工处理或禁用库存，系统不替你改池**。

## 新建项目

桌面端：点“新建项目”，填项目名称、选活动类型，再选保存位置即可。项目 ID 由名称生成，时区用本机时区，都可在“更多设置”里改；所选类型需要的模块会自动加上；选普通文件夹（如“文稿”）时会在里面为项目新建一个文件夹。创建后概览页的“开始设置”按顺序列出要填写的模块，未完成的部分自动存为草稿。

命令行只需名称和类型：

```bash
python -m sports_os create --name "Summer Cup 2027" --template ticketed-indoor-event --workspace ./outputs
```

类型：`non-ticketed-event`（免费 / 不售票活动）、`ticketed-indoor-event`（售票赛事）、`multi-session-tournament`（多场次锦标赛含通票）、`custom`（配合 `--modules a,b` 自选；所需依赖自动加入）。`--id`、`--timezone` 可选。命令会打印设置进度和下一步：用 `get` 导出某模块数据、编辑后 `update` 保存；项目未完成时修改保存为草稿，`status` 随时显示进度。程序不会编造业务数据，也不会自动批准；批准仍须通过 `approve-module` / `approve-project` 明确输入版本与非空批准引用。

## v1.1 → v1.1.1 显式迁移

先备份工作目录，再运行：

```bash
python -m sports_os migrate-project --workspace /path/to/existing-v11-workspace
python -m sports_os export-data --workspace /path/to/existing-v11-workspace
```

`migrate-project` 调用各启用模块的migration，全部验证通过才保存；失败不落盘。Schedule、Rights、五个Rule模块升级到schema 2；Revenue输出语义升级、schema仍为1。旧Rights显式映射REDEEMED、旧Rule映射ALL，保留原经济含义；不会静默猜测ALLOCATED。

迁移产生DRAFT、新revision，需逐一人工批准变化模块及项目。`migrate-module` 用于单模块升级；多个模块一起升级用 `migrate-project`，避免中间版本阻断保存。禁用模块可留旧状态，重新启用前按需显式迁移。

旧SN11快照只读且hash仍可核验，不用新模块重算旧版本发布件。原v1.0迁移与旧CLI保留如下。

## v1.0迁移与兼容

```bash
python -m sports_os migrate-v10 data/demo/version_a.json
# 旧版原始工作流（显式兼容入口）：
python -m sports_os --legacy validate
```

如果已经编辑当前模块工作库，先导出备份，迁移会显式替换工作态。迁移只接受v1.0工作数据（snapshot_id=null）。旧SN-*快照仍为1.0，不伪装为SN11-*；旧SQLite `data/event.sqlite` 不改。详见 [迁移说明](V1_1_MIGRATION.md)。

保留 v1.0 类型/schema/SQL视图、Excel只读检查和发布能力作为兼容适配器；它们不是新Kernel实现。v1.0 CLI同样经 ApplicationService 转交兼容应用服务。新增模块不需要修改旧schema/gate。

## 第三方模块

独立本地可信 Python 包声明：

```toml
[project.entry-points."sports_os.modules"]
"custom.checklist" = "custom_package:Checklist"
```

继承 `sports_os.kernel.Module`，实现 `module_id`、`schema()`；按需实现validate、cross_validate、calculate、diff、export、release_requirements、migrate并声明依赖。不要把批准或版本字段放进payload；支持requires_capabilities及optional_capabilities。calculate/export可不实现。可设置 `display_name`、`category`、`description`，桌面端直接显示这些名称，无需修改前端。验证用 `self.checks(gate)` 收集问题（见[架构](docs/ARCHITECTURE.md)）。安装后`modules`即能发现，不需修改Kernel注册表；导入失败的插件会被跳过并在 `health.plugin_problems` 中报告。完整示例见 [架构](V1_1_ARCHITECTURE.md)。插件是可信Python代码，不是沙箱。

## 边界

- 原型适合继续做**只读/轻编辑桌面原型**，不等于生产票务系统已验收。
- 规则支持ALL及SESSION集合；共同场次和有效期同时重叠BLOCK。未实现产品/渠道优先级或继承。
- 收入是容量/需求情景，不是实际销量结算；旅行/通票营业额不叠加到已覆盖的座席收入。
- 只有两个内置Demand Provider；历史模型可扩展，但本次不实现AI或真实历史数据接入。
- 同名不同内容、人工批准状态和hash可以校验；审批真伪、证据真实性及插件代码可信度仍由人核实。
- 单用户SQLite；不支持并发编辑协调、分布式权限、插件安全沙箱或真实现场安全判断。

文档：[本轮加固](V1_1_1_HARDENING.md) · [架构](docs/ARCHITECTURE.md) · [迁移](V1_1_MIGRATION.md) · [数据字典](docs/DATA_DICTIONARY.md) · [业务规则](docs/BUSINESS_RULES.md) · [测试](V1_1_1_TEST_REPORT.md)


## Desktop v0.1（macOS / 合成数据）

桌面入口、构建与测试命令见 [apps/desktop/README.md](apps/desktop/README.md)。流程见 [DESKTOP_USER_FLOW.md](DESKTOP_USER_FLOW.md)，实际验收结果见 [DESKTOP_V0_1_TEST_REPORT.md](DESKTOP_V0_1_TEST_REPORT.md)。Kernel v1.1.1 保持冻结。
