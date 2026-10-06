# DATA_DICTIONARY v1.1.1

## Project Manifest (project.toml)

`[project]`: id、name、timezone（IANA）、version、synthetic（必须true）、status（DRAFT/APPROVED/PUBLISHED）、approval_ref（DRAFT可空）。Kernel不强制year/venue/session/ticket字段。

`[modules]`: module_id → true/false。没有启用任何业务模块也合法。批准的裸Kernel项目可snapshot。

## ModuleState（SQLite / working-project.json）

`module_version` 是插件实现版本；`schema_version` 是payload格式版本；`data_version` 是业务输入批准版本。三者不能混用。

`payload`仅按该模块schema验证；`status`和`approval_ref`标识该模块工作态。内容hash包含这些字段，不仅包含payload。

JSON文件用 `format_version=1.1`、manifest、modules字典、evidence数组。每个modules条目包含上述状态字段。disabled条目可以保留但不参与活动版本。project.toml没有TOML null，未批准approval_ref用空字符串。

## 业务键与单位

- Schedule：session_id；时间包含UTC偏移。可选sales_start/sales_end必须成对；venue_id可省略/null，否则引用venues Provider键。
- Seating：session_id + zone_id + tier；price_class_id关联价格。容量按票张（跨场次汇总为座席机会，不是物理场馆独立座位）。
- Pricing：session_id + price_class_id；价格单元为DEMO_CURRENCY/张，最多2位小数。
- Inventory：inventory_id；quantity为票张；每容量池互斥状态合计等于sellable_capacity，as_of一致。渠道只能分配，不能重复计同一批票。
- Rights：session_id + zone_id + tier；quantity为分配票张；billing_basis必填ALLOCATED/REDEEMED；strategy/value定义有效价；expected_fulfillment按scenario给[0,1]比例。免费权益仍在Seating扣减，付费权益由本模块输出。
- Product：product_id；included_sessions内按容量键唯一；ticket_quantity为每份产品在该场次座区消耗的票张，不是订单/份/人数。
- Travel：guests为人；room_quantity/expected_rooms为房；nights为每房夜数；room_cost为每房每晚成本；service_per_guest按人；other_cost按份；quoted_non_ticket为每份非票报价。
- Rules：rule_id；各模块独立数据版本；scope为ALL或SESSION（后者session_ids非空唯一）；时间为半开有效期，每模块定义自己的业务覆盖期。
- Task：task_id；depends_on按task_id，不能循环；owner_role不用实名。
- Decision：decision_id；明确changed_paths与来源、批准角色，不自动推测变化动机。
- Demand：scenario名称不限于low/mid/high。multiplicative使用session_rates/tier_rates；direct使用逐池session_id/zone_id/tier/rate行。

数值输入是JSON有限数字，计数非负整数，不接受bool冒充数字。官方模块非负金额/计数上限1e12，用于限制原型计算范围。运行输出Decimal转为精确十进制字符串；金额仅在展示时舍入，不能回灌显示结果。

Provider使用元组业务键；应用JSON序列化时编码成JSON数组形式的字符串键，例如 `["S01","MAIN","VIP"]`，避免分隔符歧义；service内保持元组。

## Evidence / Provenance

每条必须有非空source_ref。明确变化原因可以提供module_id、changed_paths（模块diff内的精确路径）、reason、confirmed、approved_by_role。

confirmed=true且角色明确才显示“已确认原因（输入证据）”；否则显示“推测原因（输入提供，未确认）”。无精确匹配证据就写“无直接证据”。不代表系统认证了来源内容。

## Snapshot

format_version、snapshot_id（SN11-）、created_at、content_hash、record_hash、warnings_acknowledged、quality_gate、完整project和module_index。module_index记录每个启用模块module_version/schema_version/content_hash；project保留模块data_version/approval_ref。历史快照不靠后来工作配置重建。

## v1.1.1 新增口径

- working revision：原版本-r1、-r2；no-op不递增。
- venues标准结果：venue_id → 场馆row。schedule.sessions各row可有venue_id。
- rights标准结果新增billing_basis，不能缺省。旧工作态显式迁移默认REDEEMED以保留原语义。
- Revenue每行每情景：public_expected_tickets、rights_allocated、rights_expected_fulfilled、rights_revenue_tickets、revenue_tickets、fulfilled_tickets、revenue_basis、public_revenue、rights_revenue、revenue。
- revenue_basis行级为ALLOCATED/REDEEMED或无权益时null；汇总为basis → 分配票张的字典。两种票张不相加冒充人数；fulfilled_tickets是预计票张，不是去重观众。
- 汇总average_price_per_revenue_ticket = revenue/revenue_tickets；average_revenue_per_fulfilled_ticket = revenue/fulfilled_tickets；分母0则null。删除旧歧义tickets/expected_tickets/average_price字段，调用方显式选择口径。
- Schedule、Rights及五个Rule模块：module_version=1.1.1/schema_version=2。Revenue：module_version=1.1.1/schema_version=1（输出语义变化）。未升级模块保留1.1.0/1。应用包版本1.1.1不要求所有插件同步版本号。

## v1.2 口径

- 批准只存在于ModuleState（status、approval_ref、data_version）。Pricing和五个Rule模块的rows不再含price_version/version/status/approval_ref；批准不改变payload或content hash之外的业务内容，diff只报告业务字段。
- Pricing：module_version=1.2.0/schema_version=2。五个Rule模块：module_version=1.2.0/schema_version=3。`migrate-project` 从1.1.x显式迁移并删除行级生命周期字段；迁移后模块为DRAFT，需重新人工批准。
- v1.0输入的行级批准声明由适配器提升到ModuleState；行间不一致或版本不符时保留“已批准”声明但不带引用，内核K002会BLOCK，不会静默批准。

## 各模块payload字段（运行时schema生成）

机器定义在data/schemas/modules/。表内“必填”相对于父对象；scope的条件约束另由模块validate检查。

<!-- generated: module payload tables (sports_os.application.schemas) -->

### core.schedule

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].session_id|string|是|
|rows[].event_id|string|是|
|rows[].stage|string|是|
|rows[].start_time|string|是|
|rows[].end_time|string|是|
|rows[].venue_id|['string', 'null']|否|
|sales_start|string|否|
|sales_end|string|否|

### core.venue

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].venue_id|string|是|
|rows[].name|string|是|
|rows[].timezone|string|是|

### demand.direct

|字段|类型/枚举|父对象内必填|
|---|---|---|
|scenarios|object|是|
|scenarios.{key}[].session_id|string|是|
|scenarios.{key}[].zone_id|string|是|
|scenarios.{key}[].tier|string|是|
|scenarios.{key}[].rate|number|是|

### demand.multiplicative

|字段|类型/枚举|父对象内必填|
|---|---|---|
|scenarios|object|是|
|scenarios.{key}.session_rates|object|是|
|scenarios.{key}.tier_rates|object|是|

### finance.revenue

|字段|类型/枚举|父对象内必填|
|---|---|---|
|（空payload）|object|—|

### product.pass

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].product_id|string|是|
|rows[].product_type|['SINGLE', 'PASS', 'TRAVEL']|是|
|rows[].included_sessions|array|是|
|rows[].included_sessions[].session_id|string|是|
|rows[].included_sessions[].zone_id|string|是|
|rows[].included_sessions[].tier|string|是|
|rows[].included_sessions[].ticket_quantity|integer|是|
|rows[].price|['number', 'null']|是|
|rows[].price_claim|['INDEPENDENT', 'SUM_FACE_PRICES']|是|

### product.travel

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].product_id|string|是|
|rows[].product_type|['SINGLE', 'PASS', 'TRAVEL']|是|
|rows[].included_sessions|array|是|
|rows[].included_sessions[].session_id|string|是|
|rows[].included_sessions[].zone_id|string|是|
|rows[].included_sessions[].tier|string|是|
|rows[].included_sessions[].ticket_quantity|integer|是|
|rows[].price|['number', 'null']|是|
|rows[].price_claim|['INDEPENDENT', 'SUM_FACE_PRICES']|是|
|rows[].travel|object|是|
|rows[].travel.guests|integer|是|
|rows[].travel.expected_rooms|integer|是|
|rows[].travel.room_quantity|integer|是|
|rows[].travel.nights|integer|是|
|rows[].travel.room_cost|number|是|
|rows[].travel.service_per_guest|number|是|
|rows[].travel.other_cost|number|是|
|rows[].travel.pricing_method|['markup', 'margin']|是|
|rows[].travel.actual_method|['markup', 'margin']|是|
|rows[].travel.rate|number|是|
|rows[].travel.quoted_non_ticket|number|是|

### project.decisions

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].decision_id|string|是|
|rows[].issue|string|是|
|rows[].options|array|是|
|rows[].decision|string|是|
|rows[].reason|string|是|
|rows[].approved_by_role|string|是|
|rows[].effective_at|string|是|
|rows[].source_ref|string|是|
|rows[].confirmed|boolean|是|
|rows[].changed_paths|array|是|

### project.tasks

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].task_id|string|是|
|rows[].title|string|是|
|rows[].owner_role|string|是|
|rows[].due_at|string|是|
|rows[].depends_on|array|是|
|rows[].status|['TODO', 'DOING', 'DONE']|是|
|rows[].acceptance|string|是|
|rows[].proof|['string', 'null']|是|
|rows[].phase|['PRE_EVENT', 'DURING_EVENT', 'POST_EVENT']|是|

### quality.declarations

|字段|类型/枚举|父对象内必填|
|---|---|---|
|cells|array|是|
|cells[].source|string|是|
|cells[].value|['string', 'number', 'null']|是|
|totals|array|是|
|totals[].source|string|是|
|totals[].components|array|是|
|totals[].declared|number|是|
|summaries|array|是|
|summaries[].source|string|是|
|summaries[].metric|string|是|
|summaries[].value|number|是|
|summaries[].mode|['FORMULA', 'HARDCODED']|是|
|percentages|array|是|
|percentages[].source|string|是|
|percentages[].values|array|是|
|percentages[].expected|number|是|
|metrics|array|是|
|metrics[].metric_id|string|是|
|metrics[].unit|string|是|
|metrics[].source|string|是|
|documents|array|是|
|documents[].source|string|是|
|documents[].text|string|是|
|documents[].critical|boolean|是|
|named_models|array|是|
|named_models[].name|string|是|
|named_models[].content|string|是|
|named_models[].source|string|是|
|output_refs|array|是|
|output_refs[].source|string|是|
|output_refs[].snapshot_id|string|是|

### ticketing.identity

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].rule_id|string|是|
|rows[].scope|object|是|
|rows[].scope.type|['ALL', 'SESSION']|是|
|rows[].scope.session_ids|array|否|
|rows[].content|object|是|
|rows[].content.mode|string|是|
|rows[].valid_from|string|是|
|rows[].valid_to|string|是|

### ticketing.inventory

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].inventory_id|string|是|
|rows[].session_id|string|是|
|rows[].zone_id|string|是|
|rows[].tier|string|是|
|rows[].channel|string|是|
|rows[].status|['AVAILABLE', 'SOLD', 'LOCKED', 'PAID_RESERVED']|是|
|rows[].allocation_type|['PUBLIC', 'PAID_RIGHTS']|是|
|rows[].quantity|integer|是|
|rows[].as_of|string|是|
|rows[].source_ref|string|是|

### ticketing.launch

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].rule_id|string|是|
|rows[].scope|object|是|
|rows[].scope.type|['ALL', 'SESSION']|是|
|rows[].scope.session_ids|array|否|
|rows[].content|object|是|
|rows[].content.denominator|PUBLIC_POOL|是|
|rows[].content.rounds|array|是|
|rows[].content.rounds[].at|string|是|
|rows[].content.rounds[].fraction|number|是|
|rows[].valid_from|string|是|
|rows[].valid_to|string|是|

### ticketing.pricing

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].session_id|string|是|
|rows[].price_class_id|string|是|
|rows[].price|number|是|
|rows[].valid_from|string|是|

### ticketing.refund

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].rule_id|string|是|
|rows[].scope|object|是|
|rows[].scope.type|['ALL', 'SESSION']|是|
|rows[].scope.session_ids|array|否|
|rows[].content|object|是|
|rows[].content.coverage_start|string|是|
|rows[].content.coverage_end|string|是|
|rows[].content.windows|array|是|
|rows[].content.windows[].start|string|是|
|rows[].content.windows[].end|string|是|
|rows[].content.windows[].fee_rate|number|是|
|rows[].valid_from|string|是|
|rows[].valid_to|string|是|

### ticketing.rights

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].session_id|string|是|
|rows[].zone_id|string|是|
|rows[].tier|string|是|
|rows[].quantity|integer|是|
|rows[].billing_basis|['ALLOCATED', 'REDEEMED']|是|
|rows[].strategy|['FACE_VALUE', 'FIXED_PRICE', 'DISCOUNT_RATE']|是|
|rows[].value|number|是|
|rows[].expected_fulfillment|object|是|

### ticketing.rights_return

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].rule_id|string|是|
|rows[].scope|object|是|
|rows[].scope.type|['ALL', 'SESSION']|是|
|rows[].scope.session_ids|array|否|
|rows[].content|object|是|
|rows[].content.hours_before|integer|是|
|rows[].valid_from|string|是|
|rows[].valid_to|string|是|

### ticketing.seating

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].session_id|string|是|
|rows[].zone_id|string|是|
|rows[].tier|string|是|
|rows[].price_class_id|string|是|
|rows[].physical_capacity|integer|是|
|rows[].visibility|['CLEAR', 'RESTRICTED']|是|
|rows[].functional_hold|integer|是|
|rows[].broadcast_hold|integer|是|
|rows[].free_rights|integer|是|
|rows[].other_hold|integer|是|
|rows[].deduction_refs|object|是|
|rows[].deduction_refs.functional_hold|array|是|
|rows[].deduction_refs.broadcast_hold|array|是|
|rows[].deduction_refs.free_rights|array|是|
|rows[].deduction_refs.other_hold|array|是|

### ticketing.transfer

|字段|类型/枚举|父对象内必填|
|---|---|---|
|rows|array|是|
|rows[].rule_id|string|是|
|rows[].scope|object|是|
|rows[].scope.type|['ALL', 'SESSION']|是|
|rows[].scope.session_ids|array|否|
|rows[].content|object|是|
|rows[].content.allowed|boolean|是|
|rows[].valid_from|string|是|
|rows[].valid_to|string|是|
