# Sports Event OS — User Guide / 使用说明

| Document control / 文档控制 | Value / 内容 |
|---|---|
| Document ID / 文档编号 | SEOS-UG-001 |
| Document revision / 文档修订 | 1.0 — 2026-10-05 |
| Product / 适用产品 | Sports Event OS Desktop 0.1.1; Kernel 1.1.1 |
| Software baseline / 软件基线 | `abb76a49ce19ca2f0390ee8e69ff5f07db1f6769` |
| Platform / 平台 | macOS; Apple Silicon |
| Language / 语言 | Controlled English and controlled Chinese / 受控英语与受控中文 |
| Status / 状态 | Draft for STE review / 待 STE 审查草稿 |

## 1. About this guide / 关于本说明

| English | 中文 |
|---|---|
| Use this guide with the desktop application. | 本说明适用于桌面应用。 |
| This guide does not describe software development or CLI operation. | 本说明不涵盖软件开发或 CLI 操作。 |
| Both language columns use short instructions and consistent technical terms. | 中英两栏均使用简短指令和一致的技术术语。 |
| ASD-STE100 is an English language standard, not a document template. | ASD-STE100 是英语语言规范，不是文档排版模板。 |
| Full compliance with its dictionary and writing rules is not verified. | 尚未完成全部词典及写作规则的合规核验。 |
| The Chinese text uses corresponding controls for clear instructions. | 中文采用对应的受控写作规则。 |
| ASD-STE100 has no Chinese approved-word dictionary. | ASD-STE100 不提供中文批准词典。 |
| These Chinese controls are project rules, not formal ASD-STE100 requirements. | 中文约束属于项目规则，不是 ASD-STE100 正式条款。 |
| Text in bold identifies a control or an important instruction. | 粗体表示界面控件或重要指令。 |
| Chinese control names are the exact application labels. | 中文控件名称与应用界面标签一致。 |
| Code text identifies a field, a file, a status, or a technical term. | 代码样式表示字段、文件、状态或技术术语。 |
| The validator changes in PR #1 are outside this software baseline. | PR #1 中的校验器变更不属于本说明的软件基线。 |

### 1A. Controls for both languages / 双语写作约束

| Control / 约束 | English | 中文 |
|---|---|---|
| Sentence length / 句长 | Use no more than 20 words in an English instruction sentence. | 中文指令每句不超过 40 个汉字。 |
| Counting / 计数 | Use STE counting rules for English. Keep exact control names and identifiers. | 汉字计数不含标点、代码及拉丁字母标识。界面名称保持原样。 |
| Scope / 适用范围 | The Chinese character limit is a project rule, not an ASD-STE100 rule. | 中文字数上限属于项目规则，不是 ASD-STE100 条款。 |
| Meaning / 句意 | Give one main idea in each sentence. | 每句只表达一个主要意思。 |
| Action / 动作 | Give one main action in each numbered step. | 每个编号步骤只包含一个主要动作。 |
| Command / 指令 | Start an instruction with a command. | 指令直接说明动作，例如“选择”“输入”“检查”。 |
| Condition / 条件 | Put the condition before the action. | 先说明条件，再说明动作。 |
| Terms / 术语 | Use the same term for the same item. | 同一对象始终使用同一术语。 |
| Results / 结果 | State the result that the reader must check. | 明确说明读者必须检查的结果。 |
| Equivalence / 对齐 | Keep actions, conditions, limits, and results equivalent in both columns. | 两栏的动作、条件、限制和结果必须对应。 |
| Precautions / 注意事项 | Give the instruction before the possible damage. | 先给出操作要求，再说明可能造成的损害。 |

## 2. Limits and precautions / 使用边界与注意事项

| English | 中文 |
|---|---|
| Use synthetic data only. | 仅使用合成数据。 |
| Do not enter real company names, contract prices, or personal data. | 不要录入真实公司名称、合同价格或个人数据。 |
| Do not use a USB source drive as the project folder. | 不要将存放原始文件的 U 盘用作项目目录。 |
| Use only one application instance to change a project folder. | 同一项目目录仅允许一个应用实例进行修改。 |
| The application does not sell tickets or change external inventory. | 应用不售票，也不修改外部库存。 |
| The application does not approve prices or assess seat safety. | 应用不批准票价，也不评估座席安全。 |
| A local release does not publish information to a ticket platform. | 本地发布件不会向票务平台发布信息。 |
| **CAUTION: Do not change database files or snapshot files by hand. You can damage project records.** | **注意：不要手工修改数据库或快照文件。这会造成项目记录损坏。** |
| **CAUTION: Submit table changes before you quit the application. You can lose changes that you did not submit.** | **注意：退出应用前先提交表格更改。未提交的更改可能丢失。** |

## 3. Technical terms / 技术术语

| Term / 术语 | English meaning | 中文含义 |
|---|---|---|
| Project folder | The local folder that contains project data and output files. | 保存项目数据和输出文件的本地目录。 |
| Module | A software component for one business function. | 承担一项业务功能的软件组件。 |
| Profile | A preset list of modules. | 预设的模块组合。 |
| Table draft | Table changes that you did not submit. | 尚未提交的表格更改。 |
| Working copy | The current project data that the application can change. | 应用当前可以修改的项目数据。 |
| Quality Gate | The checks that identify data and release problems. | 识别数据问题和发布问题的检查机制。 |
| Finding | One problem that the Quality Gate reports. | Quality Gate 报告的一项问题。 |
| Approval reference | A reference to a manual approval outside the application. | 软件外部人工批准的引用凭据。 |
| Snapshot | A fixed copy of approved project data. | 已批准项目数据的冻结副本。 |
| Release files | Local output files for one snapshot. | 某一快照对应的本地输出文件。 |
| Sidecar | The local process that performs data checks and calculations. | 执行数据检查和计算的本地进程。 |
| Gatekeeper | The macOS function that checks applications before they run. | macOS 在应用运行前执行检查的安全功能。 |

## 4. Get the application / 获取应用

### Before you start / 开始前

| English | 中文 |
|---|---|
| Use a Mac with Apple Silicon. | 使用搭载 Apple Silicon 的 Mac。 |
| Intel Macs, Windows, and Linux are not verified for this desktop release. | 此桌面版本未验证 Intel Mac、Windows 或 Linux。 |
| The application includes its Python runtime. | 应用已包含 Python 运行环境。 |
| You do not need a separate Python installation to use the application. | 使用应用不需要单独安装 Python。 |
| Version 0.1.1 is an ad-hoc signed test release. | 0.1.1 是使用 ad-hoc 签名的测试版。 |
| Apple has not notarized this release. | 此版本尚未经过 Apple 公证。 |
| Do not use the withdrawn 0.1.0 download. | 不要使用已停用的 0.1.0 下载包。 |

### Procedure 4A — Check the download / 步骤 4A：核对下载文件

| Step | English | 中文 |
|---|---|---|
| 1 | Open the [Desktop 0.1.1 release page](https://github.com/GoodthingsHappenToMe/personal-sports-event-os/releases/tag/desktop-v0.1.1). | 打开 [Desktop 0.1.1 发布页面](https://github.com/GoodthingsHappenToMe/personal-sports-event-os/releases/tag/desktop-v0.1.1)。 |
| 2 | Download `Sports-Event-OS-Desktop-0.1.1-macos-arm64.zip`. | 下载 `Sports-Event-OS-Desktop-0.1.1-macos-arm64.zip`。 |
| 3 | Download `SHA256SUMS.txt` to the same folder. | 将 `SHA256SUMS.txt` 下载到同一目录。 |
| 4 | Open Terminal in that folder. | 在该目录打开终端。 |
| 5 | Enter `shasum -a 256 -c SHA256SUMS.txt`. | 输入 `shasum -a 256 -c SHA256SUMS.txt`。 |
| 6 | Make sure that the result ends with `OK`. | 确认结果以 `OK` 结尾。 |
| 7 | If the check fails, stop. | 如果校验失败，停止操作。 |
| 8 | If the check passes, extract the ZIP file into a separate folder. | 如果校验通过，将 ZIP 解压到独立目录。 |

| English | 中文 |
|---|---|
| The checksum checks file integrity. It does not replace Apple notarization. | 校验和用于检查文件完整性，不能代替 Apple 公证。 |
| The GitHub source ZIP is not the desktop application package. | GitHub 源码 ZIP 不是桌面应用安装包。 |

### Procedure 4B — Open the application / 步骤 4B：打开应用

| Step | English | 中文 |
|---|---|---|
| 1 | If an older application instance is open, close it. | 如果旧版应用仍在运行，先关闭它。 |
| 2 | Open **Sports Event OS.app**. | 打开 **Sports Event OS.app**。 |
| 3 | If macOS reports a damaged application or malware, stop. | 如果 macOS 提示应用已损坏或含有恶意软件，停止操作。 |
| 4 | If macOS cannot verify the developer, read the [Apple instructions](https://support.apple.com/en-us/102445). | 如果 macOS 无法验证开发者，阅读 [Apple 官方说明](https://support.apple.com/en-us/102445)。 |
| 5 | Permit this application only if you trust its source and accept the test-release limits. | 仅在确认来源可信并接受测试版限制时，才允许此应用运行。 |
| 6 | Make sure that the **项目 Projects** page appears. | 确认出现 **项目 Projects** 页面。 |

| English | 中文 |
|---|---|
| Do not disable Gatekeeper or remove quarantine attributes. | 不要关闭 Gatekeeper，也不要移除隔离属性。 |
| Standard browser-download approval is not verified for this release. | 此版本尚未完成标准安全环境下的浏览器下载首开验收。 |

## 5. Create or open a project / 创建或打开项目

### Procedure 5A — Create the demo / 步骤 5A：创建演示项目

| Step | English | 中文 |
|---|---|---|
| 1 | Select **在空目录创建演示项目**. | 选择 **在空目录创建演示项目**。 |
| 2 | Select an empty local folder. | 选择空白的本地目录。 |
| 3 | Make sure that **项目概览** shows the synthetic event. | 确认 **项目概览** 显示虚构赛事。 |
| 4 | Record the project folder path. | 记录项目目录路径。 |

| English | 中文 |
|---|---|
| The demo event is `2027 Global Racket Masters`. | 演示赛事为 `2027 Global Racket Masters`。 |
| Demo approval references are test values, not real approvals. | 演示项目的批准引用是测试值，不代表真实批准。 |

### Procedure 5B — Create an empty project / 步骤 5B：创建空项目

| Step | English | 中文 |
|---|---|---|
| 1 | Select **新建项目**. | 选择 **新建项目**。 |
| 2 | Enter a synthetic name in **项目名称**. | 在 **项目名称** 中输入虚构名称。 |
| 3 | Enter a unique value in **项目 ID**. | 在 **项目 ID** 中输入唯一标识。 |
| 4 | Enter a time zone in **时区 Timezone**, for example, `Asia/Singapore`. | 在 **时区 Timezone** 中输入时区，例如 `Asia/Singapore`。 |
| 5 | Select **下一步**. | 选择 **下一步**。 |
| 6 | Select a profile. | 选择模块预设。 |
| 7 | Select **下一步**. | 选择 **下一步**。 |
| 8 | Select the necessary modules. | 选择所需模块。 |
| 9 | Select **选择文件夹并创建**. | 选择 **选择文件夹并创建**。 |
| 10 | Select an empty local folder. | 选择空白的本地目录。 |

| English | 中文 |
|---|---|
| A profile selects modules. It does not supply complete business data. | 预设用于选择模块，不会提供完整业务数据。 |
| An incomplete project can remain a draft. It cannot produce a snapshot. | 不完整项目可以保留为草稿，但不能生成快照。 |
| To open an existing project, select **打开项目** and its project folder. | 打开已有项目时，选择 **打开项目**，再选择项目目录。 |

## 6. Change project data / 修改项目数据

| English | 中文 |
|---|---|
| **CAUTION: Do not use “保存项目” as a substitute for “提交工作数据”. Table changes can remain unsubmitted.** | **注意：不要用“保存项目”代替“提交工作数据”。表格更改可能尚未提交。** |

### Procedure 6A — Change a table / 步骤 6A：修改表格

| Step | English | 中文 |
|---|---|---|
| 1 | If `READ ONLY` appears, select **返回工作副本**. | 如果出现 `READ ONLY`，选择 **返回工作副本**。 |
| 2 | Select a module in the navigation panel. | 在导航栏选择模块。 |
| 3 | Change the necessary field. | 修改所需字段。 |
| 4 | If necessary, expand the nested data section. | 如有需要，展开嵌套数据区域。 |
| 5 | Check all changed values. | 核对所有已更改的值。 |
| 6 | Select **提交工作数据**. | 选择 **提交工作数据**。 |
| 7 | Make sure that the application accepts the change. | 确认应用接受更改。 |
| 8 | Check the new `data_version` and approval status. | 核对新的 `data_version` 和批准状态。 |

| English | 中文 |
|---|---|
| A changed payload makes the module and project approvals invalid. | 数据内容变化会使相关模块及项目批准失效。 |
| The changed module and project return to `DRAFT`. | 已更改模块和项目回到 `DRAFT` 状态。 |
| Old snapshots do not change. | 历史快照不变。 |
| Use **撤销未提交更改** to discard the table draft. | 使用 **撤销未提交更改** 丢弃尚未提交的表格更改。 |
| Use **保存项目** to save the current working copy. | 使用 **保存项目** 保存后端当前工作副本。 |
| Use a complete date-time value, for example, `2027-06-01T10:00:00+08:00`. | 日期时间使用完整格式，例如 `2027-06-01T10:00:00+08:00`。 |

### Procedure 6B — Change the module list / 步骤 6B：修改模块清单

| Step | English | 中文 |
|---|---|---|
| 1 | Select **能力模块**. | 选择 **能力模块**。 |
| 2 | Change the selection for the applicable module. | 更改目标模块的启用状态。 |
| 3 | If a dependency error appears, read the error details. | 如果出现依赖错误，阅读错误详情。 |
| 4 | Correct the module selection before you continue. | 继续操作前，修正模块组合。 |

| English | 中文 |
|---|---|
| A disabled module keeps its data. | 禁用模块后，其数据仍会保留。 |
| Do not disable a required check only to remove a `BLOCK` result. | 不要为了消除 `BLOCK` 而禁用必要检查。 |

## 7. Check the data / 检查数据

### Procedure 7A — Use the Quality Gate / 步骤 7A：执行质量检查

| Step | English | 中文 |
|---|---|---|
| 1 | Submit all table changes. | 提交所有表格更改。 |
| 2 | Select **检查**. | 选择 **检查**。 |
| 3 | Read each finding on the **质量检查** page. | 阅读 **质量检查** 页面中的每项问题。 |
| 4 | Use `source` to identify the related module or field. | 使用 `source` 确定相关模块或字段。 |
| 5 | Compare `expected` with `actual`. | 对照 `expected` 与 `actual`。 |
| 6 | Correct the data in the working copy. | 在工作副本中修正数据。 |
| 7 | Submit the corrections. | 提交修正。 |
| 8 | Select **检查** again. | 再次选择 **检查**。 |

| Status | English meaning | 中文含义 |
|---|---|---|
| `PASS` | The checks found no problem in the supplied data. | 检查未在已提供数据中发现问题。 |
| `WARNING` | Read the findings. Confirm accepted warnings before you create a snapshot. | 阅读问题详情；生成快照前，确认可以接受的警告。 |
| `BLOCK` | Correct the blocking problem. Do not create release files. | 修正阻断问题；不要生成发布件。 |

| English | 中文 |
|---|---|
| A data-check `PASS` is not a manual approval or a release-check `PASS`. | 数据检查 `PASS` 不等于人工批准，也不等于发布检查 `PASS`。 |
| Missing approvals can block a snapshot when data checks pass. | 即使数据检查通过，缺少批准仍会阻止生成快照。 |
| A `PASS` does not verify facts that you did not supply. | `PASS` 不会验证未提供的事实。 |

## 8. Read revenue results / 查看收入结果

### Procedure 8A — Review the calculation / 步骤 8A：核对计算结果

| Step | English | 中文 |
|---|---|---|
| 1 | Make sure that `finance.revenue` and its required modules are enabled. | 确认已启用 `finance.revenue` 及其依赖模块。 |
| 2 | Correct all `BLOCK` findings. | 修正所有 `BLOCK` 问题。 |
| 3 | Open the `finance.revenue` page. | 打开 `finance.revenue` 页面。 |
| 4 | Check **满售容量收入 Full Revenue**. | 核对 **满售容量收入 Full Revenue**。 |
| 5 | Compare the demand scenarios. | 比较不同需求情景。 |
| 6 | Select a group in **分组查看**. | 在 **分组查看** 中选择分组方式。 |
| 7 | Read **敏感性与口径说明**. | 阅读 **敏感性与口径说明**。 |

| English | 中文 |
|---|---|
| `Public Revenue` is revenue from the public ticket pool. | `Public Revenue` 为公开售票池收入。 |
| `Rights Revenue` is paid-rights revenue under the selected billing basis. | `Rights Revenue` 为按指定计费口径计算的付费权益收入。 |
| `Rights Allocated` is the allocated ticket quantity. | `Rights Allocated` 为已分配权益票张数。 |
| `Rights Expected Fulfilled` is the expected fulfilled ticket quantity. | `Rights Expected Fulfilled` 为预计履约权益票张数。 |
| `ALLOCATED` uses allocated tickets for paid-rights revenue. | `ALLOCATED` 按分配票张数计算付费权益收入。 |
| `REDEEMED` uses expected fulfilled tickets for scenario revenue. | `REDEEMED` 在情景模型中按预计履约票张数计算收入。 |
| Do not treat orders, tickets, product units, and people as the same quantity. | 不要将订单数、票张数、产品份数和人数视为同一数量。 |
| Check each product's `included_sessions` and `ticket_quantity`. | 核对每个产品的 `included_sessions` 和 `ticket_quantity`。 |
| Snapshot calculations use snapshot data, not the current working copy. | 快照计算使用快照数据，而非当前工作副本。 |
| Do not enter calculated totals by hand. Change the source data. | 不要手工输入计算总计；应修改源数据。 |

## 9. Record manual approvals / 记录人工批准

| English | 中文 |
|---|---|
| Complete the applicable approval outside the application first. | 先在软件之外完成相应批准。 |
| The application records an approval reference. It does not make the business decision. | 应用只记录批准引用，不替你作出业务决定。 |
| Use clearly identified test references for synthetic exercises. | 合成演练中使用明确标为测试的批准引用。 |

### Procedure 9A — Record a module approval / 步骤 9A：记录模块批准

| Step | English | 中文 |
|---|---|---|
| 1 | Open the module page. | 打开模块页面。 |
| 2 | Select **记录模块批准**. | 选择 **记录模块批准**。 |
| 3 | Compare the displayed version with the approval reference. | 核对显示版本是否与批准凭据对应。 |
| 4 | Enter the reference in **批准引用 Approval Reference**. | 在 **批准引用 Approval Reference** 中输入凭据引用。 |
| 5 | Select **记录人工批准**. | 选择 **记录人工批准**。 |
| 6 | Make sure that the module status is `APPROVED`. | 确认模块状态为 `APPROVED`。 |

### Procedure 9B — Record the project approval / 步骤 9B：记录项目批准

| Step | English | 中文 |
|---|---|---|
| 1 | Record the required approvals for all enabled modules. | 记录所有已启用模块所需的批准。 |
| 2 | Select **记录项目批准**. | 选择 **记录项目批准**。 |
| 3 | Compare the displayed project version with the approval reference. | 核对显示的项目版本是否与批准凭据对应。 |
| 4 | Enter the reference in **批准引用 Approval Reference**. | 在 **批准引用 Approval Reference** 中输入凭据引用。 |
| 5 | Select **记录人工批准**. | 选择 **记录人工批准**。 |
| 6 | Make sure that the project status is `APPROVED`. | 确认项目状态为 `APPROVED`。 |

## 10. Create and read a snapshot / 创建与查看快照

### Procedure 10A — Create local release files / 步骤 10A：生成本地发布件

| Step | English | 中文 |
|---|---|---|
| 1 | Select **快照**. | 选择 **快照**。 |
| 2 | Check the release status beside **冻结当前工作版本**. | 检查 **冻结当前工作版本** 旁的发布状态。 |
| 3 | If the status is `BLOCK`, correct the data or approval problem. | 如果状态为 `BLOCK`，修正数据或批准问题。 |
| 4 | If the status is `WARNING`, read all applicable findings. | 如果状态为 `WARNING`，阅读全部相关问题。 |
| 5 | If you accept the warnings, select **已阅读并确认警告**. | 如果确认可以接受这些警告，勾选 **已阅读并确认警告**。 |
| 6 | Select **冻结 Snapshot**. | 选择 **冻结 Snapshot**。 |
| 7 | Make sure that the snapshot appears in the list. | 确认快照出现在列表中。 |
| 8 | Record its `snapshot_id`. | 记录其 `snapshot_id`。 |

| English | 中文 |
|---|---|
| The release folder is `outputs/releases/<snapshot_id>/` inside the project folder. | 发布目录位于项目目录下的 `outputs/releases/<snapshot_id>/`。 |
| It contains `snapshot.json`, `artifacts.json`, and `manifest.json`. | 目录包含 `snapshot.json`、`artifacts.json` 和 `manifest.json`。 |
| Keep these files together. Do not combine files from different snapshots. | 保留整套文件，不要混用不同快照的文件。 |

### Procedure 10B — Read an old snapshot / 步骤 10B：查看历史快照

| Step | English | 中文 |
|---|---|---|
| 1 | Select its `snapshot_id` in the snapshot list. | 在快照列表中选择对应的 `snapshot_id`。 |
| 2 | Make sure that `READ ONLY` appears. | 确认出现 `READ ONLY`。 |
| 3 | Read the necessary module data. | 查看所需模块数据。 |
| 4 | To change current data, select **返回工作副本**. | 如需修改当前数据，选择 **返回工作副本**。 |

## 11. Compare versions / 比较版本

### Procedure 11A — Examine changes / 步骤 11A：查看变更

| Step | English | 中文 |
|---|---|---|
| 1 | Select **版本比较**. | 选择 **版本比较**。 |
| 2 | Select an old snapshot in **旧版本**. | 在 **旧版本** 中选择历史快照。 |
| 3 | Select a snapshot or **当前工作副本** in **新版本**. | 在 **新版本** 中选择快照或 **当前工作副本**。 |
| 4 | Select **比较版本**. | 选择 **比较版本**。 |
| 5 | Read the changes for each module. | 阅读各模块的变化。 |
| 6 | Check the evidence classification for each stated reason. | 核对每项原因的证据分类。 |

| English | 中文 |
|---|---|
| A numerical change does not prove its cause. | 数值变化不能证明变化原因。 |
| Do not treat an unconfirmed reason as a confirmed fact. | 不要将未确认原因当作已确认事实。 |
| If there is no direct evidence, leave the cause unconfirmed. | 如果没有直接证据，保留原因未确认的状态。 |

## 12. Close, reopen, and recover / 关闭、重开与恢复

### Procedure 12A — Close and reopen / 步骤 12A：关闭并重新打开

| Step | English | 中文 |
|---|---|---|
| 1 | Submit table changes that you want to keep. | 提交需要保留的表格更改。 |
| 2 | Select **保存项目**. | 选择 **保存项目**。 |
| 3 | Wait for the save confirmation. | 等待保存确认。 |
| 4 | Quit the application. | 退出应用。 |
| 5 | Open the application again. | 重新打开应用。 |
| 6 | Select the project from the recent-project list. | 从最近项目列表选择项目。 |
| 7 | Check the working version and snapshot list. | 核对工作版本和快照列表。 |

| English | 中文 |
|---|---|
| For a backup, copy the complete project folder after you close the application. | 备份时，先关闭应用，再复制整个项目目录。 |
| Keep the original folder until you verify the backup. | 在确认备份可用之前，保留原目录。 |

### Fault isolation / 故障处理

| Condition / 情况 | English instruction | 中文指令 |
|---|---|---|
| Damaged application / 应用已损坏 | Stop. Record the message and download version. Do not remove security controls. | 停止操作；记录提示和下载版本；不要移除安全限制。 |
| Missing module / 模块未显示 | Open **能力模块**. Check the module selection and its dependencies. | 打开 **能力模块**，检查模块选择及依赖关系。 |
| No revenue result / 无收入结果 | Check the required modules and `BLOCK` findings. | 检查依赖模块及 `BLOCK` 问题。 |
| Disabled snapshot button / 快照按钮禁用 | Check unsubmitted changes, approvals, release findings, and warning acknowledgement. | 检查未提交更改、批准状态、发布问题及警告确认。 |
| `READ ONLY` | Select **返回工作副本** before you change data. | 修改数据前选择 **返回工作副本**。 |
| Sidecar failure / 后端断连 | Select **重新连接后端** when available. Open the project again. Check saved data before you repeat an action. | 按钮可用时选择 **重新连接后端**，重新打开项目；重复操作前先核对已保存数据。 |
| Approval version mismatch / 批准版本不一致 | Check the current version. Obtain the applicable approval before you record it. | 核对当前版本，取得对应批准后再记录。 |

## 13. References and review status / 依据与审查状态

- [ASD-STE100 official website / ASD-STE100 官方网站](https://www.asd-ste100.org/): Issue 9, 2025-01-15.
- [About STE / STE 简介](https://www.asd-ste100.org/about_STE.html): English writing rules and controlled vocabulary / 英语写作规则与受控词汇。
- [Apple: Safely open apps on your Mac / Apple：安全打开 Mac 应用](https://support.apple.com/en-us/102445).
- Software references / 软件依据：`DESKTOP_USER_FLOW.md`, `apps/desktop/README.md`, `App.tsx`, `Editor.tsx`, `components.tsx`, `ApplicationService`.

| English | 中文 |
|---|---|
| The control names and file paths were checked against the software baseline. | 控件名称和文件路径已与软件基线核对。 |
| Full dictionary review by an STE reviewer remains necessary. | 仍需 STE 审查人员完成全量词典核验。 |
| This guide does not certify the software or approve real event operations. | 本说明不认证软件，也不批准真实赛事运营。 |
