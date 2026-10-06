# Validator polish 补丁接入 / 2026-10-05

基线：`abb76a49ce19ca2f0390ee8e69ff5f07db1f6769`。分支：`polish/validators-hygiene`。

## 接入与审查

用户提供的 `sports-os-polish.diff` 实际是 `git format-patch` 邮件格式，可直接 `git am`，无需改扩展名。原补丁单独提交并保留作者；接入修正作为后续提交。不直接合并 main、不发布或替换已有 App Release。

已接入：Rights 金额精度 / FACE_VALUE 契约、Launch 正比例、Refund 费率递减 WARNING、产品低于面值 WARNING、health 0.1.1、客户端 traceback 显示开关、Ruff import 清理与配置、Linux Python / frontend CI、E2E sidecar 路径覆盖。

审查纠正：
- `SPORTS_OS_DEBUG` 必须精确等于 `1` 才在协议响应中返回 traceback；`0` 和未设置均不返回。stderr 仍保留诊断堆栈，不能把这项改动说成完全停止记录 traceback。
- Travel 原有“票面金额＋非票报价＝总价”和非负报价约束保留。低于门票面值会同时产生 PRODUCT_BELOW_FACE WARNING 与 M_CROSS BLOCK；**本补丁没有让旅行包折扣仅警告后即可发布**，这种产品需另行审定明确的折扣数据模型。
- CI 的 pnpm 对齐本地已验证的 11.19.0，Ruff 固定为实测 0.16.10；workflow 只授予 contents: read。
- 原补丁 9 个测试之外新增 7 个边界测试，并加强“金额一致”“恰好等于/高于面值”的断言；不能以测试名称替代实际覆盖。

## 实际验证

|项目|实际结果|
|---|---|
|原补丁原样应用后的 Python suite|207 tests，11.873s，全部通过（macOS，无跳过）|
|接入修正后的 Python suite|214 tests，12.303s，全部通过（macOS，无跳过）|
|Ruff 0.16.10|`ruff check src tests`，All checks passed|
|前端 TypeScript / ESLint|通过|
|前端 unit|10 tests PASS|
|Vite production build|通过|
|PyInstaller sidecar|从本分支代码重新冻结，成功；不是复用旧发布二进制|
|Playwright real-sidecar E2E|3 tests PASS，11.7s；使用 SPORTS_SIDECAR 显式指定新二进制，包含原有 axe / 业务闭环检查|
|Tauri release build|真实 macOS arm64 构建通过；app / main / sidecar 完整 ad-hoc 签名|
|打包门禁|严格 codesign、PATH=/nonexistent 的 11 项 sidecar 闭环、ZIP 解压签名复查全部通过|

新增覆盖：退款费率按实际时间而非输入顺序比较；Pass / Refund 警告在人工批准后仍须 ack 才能创建快照且不确认时无快照；Travel 折扣不得绕过对账；health 与 Desktop config 版本一致；DEBUG=0 / DEBUG=1 正反路径。

E2E 首次启动因为默认浏览器缓存路径缺少所需 Chromium 而失败，没有执行测试；改用已安装的项目缓存后完整重跑通过。没有跳过断言或使用旧业务二进制。新增边界测试开发中曾因按数组首项而非 product_id 取票面金额产生测试失败，已改为按 PASS-DEMO 键取值后重跑全套。上述失败未记为 PASS。

本地打包仅验收，不分发：未进行公证，也未重做标准 Gatekeeper 下载首开验收，已有发行限制不变。GitHub CI 的远端状态以 PR checks 为准，CI 不包含 Tauri/native/E2E。

## 保持不变 / 后续事项

- 不运行全库格式化，不替换 star imports；common.py 的 F401 豁免保留，避免破坏显式依赖于再导出的模块。
- 不重构收集所有行错误的 validator 协议；现有 fail-fast / M_INPUT / M_CROSS 行为仍在。
- Rust debug sidecar 路径仍限定 arm64 macOS；E2E 环境变量不等于 Rust 已支持跨平台。
- 不删除 SQLite、日志、历史验收报告、快照，不扩大到真实数据。
- 历史 `run_v111_acceptance.py` 固定测试计数，不能用它重写当前验收；当前回归入口为 unittest discover。

## 复现

```bash
python -m pip install -e '.[excel]' ruff==0.16.10
python -m ruff check src tests
python -m unittest discover -s tests
pnpm --dir apps/desktop lint
pnpm --dir apps/desktop test
pnpm --dir apps/desktop build
# macOS build 环境与 PyInstaller 依赖见 apps/desktop/README.md
python apps/desktop/scripts/build_sidecar.py
SPORTS_SIDECAR=/absolute/path/to/new/sidecar pnpm --dir apps/desktop test:e2e
pnpm --dir apps/desktop tauri build
```
