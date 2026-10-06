import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";
let child: ChildProcessWithoutNullStreams, workspace: string, seq: number;
let call: (method: string, params?: any) => Promise<any>;
test.beforeEach(async ({ page }) => {
  workspace = mkdtempSync(join(tmpdir(), "sports-desktop-e2e-"));
  seq = 0;
  child = spawn(
    resolve(
      process.env.SPORTS_SIDECAR ??
        "src-tauri/binaries/sports-os-sidecar-aarch64-apple-darwin",
    ),
    [],
    { env: { PATH: "/usr/bin:/bin", HOME: process.env.HOME! } },
  );
  const requests = new Map<string, (v: any) => void>();
  createInterface({ input: child.stdout }).on("line", (line) => {
    const r = JSON.parse(line);
    requests.get(r.id)?.(r);
    requests.delete(r.id);
  });
  child.stderr.on("data", () => {});
  call = (method, params = {}) =>
    new Promise((resolve) => {
      const id = String(++seq);
      requests.set(id, resolve);
      child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    });
  await page.exposeFunction("testInvoke", async (command: string, args: any) =>
    command === "sports_call"
      ? call(args.method, args.params)
      : command === "plugin:dialog|open"
        ? workspace
        : undefined,
  );
  await page.addInitScript(() => {
    (window as any).__TAURI_INTERNALS__ = {
      invoke: (command: string, args: any) =>
        (window as any).testInvoke(command, args),
    };
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "项目 Projects" }),
  ).toBeVisible();
});
test.afterEach(() => {
  child?.kill();
  if (workspace) rmSync(workspace, { recursive: true, force: true });
});
const nav = (page: any, name: string) =>
  page.locator(".sidebar").getByRole("button", { name, exact: true });
async function demo(page: any) {
  await page.getByRole("button", { name: "在空目录创建演示项目" }).click();
  await expect(
    page.getByRole("heading", { name: "项目概览", exact: true }),
  ).toBeVisible();
}
async function axe(page: any) {
  if (await page.getByRole("dialog").count())
    await expect(page.getByRole("dialog")).toHaveCSS("opacity", "1");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
}
test("one-screen wizard, setup checklist, auto-added dependencies, keyboard dialog", async ({
  page,
}) => {
  await axe(page);
  await page.getByRole("button", { name: "新建项目" }).click();
  await page.getByLabel("项目名称", { exact: true }).fill("Synthetic Desktop");
  await page.getByRole("radio", { name: /自定义/ }).check();
  await axe(page);
  await page.getByRole("button", { name: "选择保存位置并创建" }).click();
  await expect(
    page.getByRole("heading", { name: "项目概览", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("SYNTHETIC-DESKTOP").first()).toBeVisible();
  await expect(nav(page, "收入 Revenue")).toHaveCount(0);
  await expect(nav(page, "旅行包 Travel")).toHaveCount(0);
  await nav(page, "能力模块").click();
  // Enabling Revenue enables everything it needs instead of failing with a dependency error.
  await page.getByLabel("启用 finance.revenue", { exact: true }).click();
  await expect(page.getByRole("status").last()).toContainText("已自动加入所需模块");
  await expect(nav(page, "收入 Revenue")).toBeVisible();
  await expect(nav(page, "赛程 Schedule")).toBeVisible();
  await expect(nav(page, "票价 Pricing")).toBeVisible();
  await page.getByRole("button", { name: "概览", exact: true }).click();
  const checklist = page.getByRole("region", { name: "开始设置" });
  await expect(checklist).toContainText("已完成 0 / 5");
  // The empty project was saved before modules were added, so there is a version to fall back to.
  await expect(page.getByRole("button", { name: "放弃草稿" })).toBeVisible();
  await checklist.getByRole("button", { name: "去填写" }).click();
  await expect(
    page.getByRole("heading", { name: "赛程 Schedule", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("还没有数据行")).toBeVisible();
  await page.getByRole("button", { name: "新增行" }).click();
  await page.getByRole("button", { name: "概览", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "尚未提交的编辑" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("complete approved draft gate revenue snapshot diff reopen flow with a11y", async ({
  page,
}) => {
  await demo(page);
  await expect(nav(page, "旅行包 Travel")).toBeVisible();
  await expect(nav(page, "收入 Revenue")).toBeVisible();
  await axe(page);
  await nav(page, "快照").click();
  await page.getByRole("button", { name: "冻结 Snapshot" }).click();
  await expect(page.getByRole("button", { name: /^SN11-/ })).toHaveCount(1);
  await nav(page, "票价 Pricing").click();
  const price = page.getByLabel("ticketing.pricing/rows/0/price", {
    exact: true,
  });
  await price.fill("731");
  await page.getByRole("button", { name: "提交工作数据" }).click();
  await expect(page.locator(".project-identity")).toContainText("DRAFT");
  await nav(page, "快照").click();
  await expect(
    page.getByRole("button", { name: "冻结 Snapshot" }),
  ).toBeDisabled();
  await nav(page, "质量检查").click();
  await expect(page.getByLabel("质量检查结果")).toContainText("PASS");
  await axe(page);
  await nav(page, "收入 Revenue").click();
  await expect(page.getByText("满售容量收入 Full Revenue")).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Rights Revenue", exact: true }),
  ).toBeVisible();
  await axe(page);
  await nav(page, "票价 Pricing").click();
  await page.getByRole("button", { name: "记录模块批准" }).click();
  await page
    .getByLabel("批准引用 Approval Reference")
    .fill("SYNTHETIC-TEST-MODULE");
  await axe(page);
  await page.getByRole("button", { name: "记录人工批准" }).click();
  await page.getByRole("button", { name: "记录项目批准", exact: true }).click();
  await page
    .getByLabel("批准引用 Approval Reference")
    .fill("SYNTHETIC-TEST-PROJECT");
  await page.getByRole("button", { name: "记录人工批准" }).click();
  await expect(page.locator(".project-identity")).toContainText("APPROVED");
  await nav(page, "快照").click();
  await page.getByRole("button", { name: "冻结 Snapshot" }).click();
  await expect(page.getByRole("button", { name: /^SN11-/ })).toHaveCount(2);
  await page
    .getByRole("button", { name: /^SN11-/ })
    .first()
    .click();
  await expect(page.locator(".readonly-banner")).toBeVisible();
  await nav(page, "票价 Pricing").click();
  await expect(page.getByRole("button", { name: "提交工作数据" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await axe(page);
  await nav(page, "收入 Revenue").click();
  await expect(page.getByText("满售容量收入 Full Revenue")).toBeVisible();
  await page.getByRole("button", { name: "返回工作副本" }).click();
  await nav(page, "版本比较").click();
  await page.getByRole("button", { name: "比较版本", exact: true }).click();
  await expect(
    page.getByText("完整后端差异记录（含模块启停与元数据）"),
  ).toBeVisible();
  const snapshots = (await call("list_snapshots")).result;
  await page
    .getByRole("combobox", { name: /^新版本/ })
    .selectOption(snapshots[1].snapshot_id);
  await page.getByRole("button", { name: "比较版本", exact: true }).click();
  await expect(
    page.getByText("完整后端差异记录（含模块启停与元数据）"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Sports Event OS", exact: true })
    .click();
  await page.getByRole("button", { name: "打开项目", exact: true }).click();
  await expect(page.locator(".project-identity")).toContainText("APPROVED");
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1280, height: 800 },
    { width: 1040, height: 700 },
  ]) {
    await page.setViewportSize(size);
    await expect(
      page.getByRole("heading", { name: "项目概览", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({ path: `test-results/overview-${size.width}.png` });
  }
});
test("backend unavailable and reconnect affordance", async ({ page }) => {
  await page.evaluate(() => {
    const original = (window as any).__TAURI_INTERNALS__.invoke;
    (window as any).__TAURI_INTERNALS__.invoke = (
      command: string,
      args: any,
    ) =>
      command === "sports_call"
        ? Promise.reject(new Error("Synthetic disconnect"))
        : original(command, args);
  });
  await page.getByRole("button", { name: "在空目录创建演示项目" }).click();
  await expect(page.getByRole("heading", { name: "后端不可用" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "重新连接后端" }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toBeVisible();
});
