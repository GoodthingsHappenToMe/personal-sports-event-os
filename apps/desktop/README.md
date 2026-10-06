# Sports Event OS Desktop 0.1.1

macOS Apple Silicon，Tauri 2 + React + persistent frozen Python sidecar。中文 UI / 原名技术字段。仅合成数据。

操作说明：[受控中英双语使用说明](../../docs/USER_GUIDE_STE_EN_ZH.md)。

## 从仓库构建

开发机需 macOS、Xcode Command Line Tools、Rust/Cargo、Node ≥22、pnpm 11，以及 Python 3.12。最终用户无需这些环境。

```bash
# repository root
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r apps/desktop/requirements-build.txt
pnpm --dir apps/desktop install --frozen-lockfile
python apps/desktop/scripts/build_sidecar.py
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
pnpm --dir apps/desktop tauri dev
# close dev, then build
pnpm --dir apps/desktop tauri build
```

生成 `apps/desktop/src-tauri/target/release/bundle/macos/Sports Event OS.app`。0.1.0 存在资源签名未封装缺陷，不再推荐下载。0.1.1 修复完整 bundle / sidecar 签名，但仍只是 **ad-hoc 签名的未公证测试版**，不是免确认安装的正式发行版。未验证 Intel / Windows / Linux。

## 下载与首次打开

只使用本仓库 `desktop-v0.1.1` Release 的 ZIP 和 SHA256SUMS.txt。终端在下载目录执行 `shasum -a 256 -c SHA256SUMS.txt`，必须显示 OK。解压到与旧版不同的目录；退出旧程序后打开新版，不要覆盖项目数据目录。

如果系统提示“无法验证开发者”或“Apple 无法检查是否包含恶意软件”，仅在你确认来源并愿意运行此测试版时，按 [Apple 官方说明](https://support.apple.com/en-us/102445) 到系统设置 → 隐私与安全性 → 仍要打开，手动批准这一应用。不要关闭 Gatekeeper、不要执行 `xattr -cr` 或移除 quarantine。若仍显示“已损坏”或恶意软件警告，停止打开，保留提示供排查，不要强行绕过。

ad-hoc 不验证发布者身份，SHA256 也不能替代 Apple 公证。无提示的标准分发需要 Developer ID Application 签名、Apple 公证及 stapled ticket，当前没有可用证书，发行资格检查仍为 BLOCK。

## 打包门禁

```bash
python apps/desktop/scripts/package_macos.py \
  'apps/desktop/src-tauri/target/release/bundle/macos/Sports Event OS.app' \
  '../desktop-v0.1.1/Sports-Event-OS-Desktop-0.1.1-macos-arm64.zip'
```

必须先通过资源封装与严格签名校验、真实冻结 sidecar smoke，再创建 ZIP；解压后重新校验整个 bundle 和每个 MacOS 二进制，失败不生成发行 ZIP，也不覆盖已有 ZIP。输出 SHA256。该门禁的 PASS **仅代表包完整性和本地运行能力**。

正式分发另需 `syspolicy_check distribution '…/Sports Event OS.app'`、`spctl --assess --type execute --verbose=4 '…/Sports Event OS.app'`，以及启用正常 Gatekeeper 的独立机器浏览器下载测试。`override=security disabled` 不可算验收通过。只读检查系统策略，不自动修改它。

Tauri 使用 `signingIdentity: "-"` 进行完整 ad-hoc 签名。保留 hardened runtime，仅通过 Entitlements.plist 添加 frozen Python 必需的 `com.apple.security.cs.disable-library-validation`：内嵌 ad-hoc dylib 没有 Team ID，默认 library validation 会拒绝加载。Tauri 将该文件应用于 app 与 sidecar；没有添加 JIT、调试或 unsigned executable memory 权限，没有修改系统安全设置。正式证书流水线必须同步签署 PyInstaller 内嵌 dylib，并重新评估是否可以去掉这一例外。

## 回归

```bash
python -m unittest discover -s tests
pnpm --dir apps/desktop lint
pnpm --dir apps/desktop test
pnpm --dir apps/desktop exec playwright install chromium
pnpm --dir apps/desktop test:e2e
python apps/desktop/scripts/smoke_packaged.py \
  'apps/desktop/src-tauri/target/release/bundle/macos/Sports Event OS.app/Contents/MacOS/sports-os-sidecar'
```

E2E 在临时目录启动真实冻结 sidecar，仅适配原生文件选择和 Tauri IPC。测试使用合成事实，并执行 axe、键盘、三个窗口尺寸检查。打包 smoke 的子进程 PATH=/nonexistent，不依赖系统 Python。

开发 sidecar 路径目前面向 arm64；新增插件需重新冻结并重跑 Registry 测试。无运行时联网依赖；pnpm/Cargo/PyInstaller 仅构建时使用。

## 设计与行为依据

仓库根 `PRODUCT.md` / `DESIGN.md`；本目录 `design/` 保存研究、参考与一次集中审查。外部设计工具安装在项目 `.agents/skills`，不作为应用运行依赖打包或提交二进制。具体官方安装命令和 hook 信任步骤见 `design/TOOLCHAIN.md`。

功能说明、协议、边界与实测结果见根目录 `DESKTOP_USER_FLOW.md`、`DESKTOP_PROTOCOL.md`、`DESKTOP_ARCHITECTURE.md`、`DESKTOP_V0_1_TEST_REPORT.md`。
