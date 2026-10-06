import { useCallback, useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "@tauri-apps/api/core";
import {
  sportsOS,
  BackendError,
  Dict,
  Workspace,
  moduleName,
  setModuleCatalog,
} from "./api";
import { Modal, GateView } from "./components";
import { HomePage } from "./pages/HomePage";
import { OverviewPage } from "./pages/OverviewPage";
import { ModulesPage } from "./pages/ModulesPage";
import { ModulePage, ModuleView } from "./pages/ModulePage";
import { RevenuePage } from "./pages/RevenuePage";
import { SnapshotsPage } from "./pages/SnapshotsPage";
import { VersionsPage } from "./pages/VersionsPage";
import { Sidebar, PAGE_TITLES } from "./views/Sidebar";
import { Wizard } from "./views/Wizard";
import { ErrorNotice, ErrorPanel } from "./views/Errors";
import { ApprovalDialog } from "./views/ApprovalDialog";

/**
 * Application shell: owns the session state (open workspace, current page, snapshot being viewed,
 * busy/error/notice) and talks to the sidecar. Pages under ./pages are presentational and receive
 * data and callbacks as props.
 */
export default function App() {
  const [health, setHealth] = useState<Dict | null>(null),
    [state, setState] = useState<Workspace | null>(null),
    [page, setPage] = useState("Overview"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<BackendError | null>(null),
    [notice, setNotice] = useState(""),
    [wizard, setWizard] = useState(false),
    [approval, setApproval] = useState<string | null>(null),
    [dirty, setDirty] = useState(false),
    [pending, setPending] = useState<(() => void) | null>(null),
    [collapsed, setCollapsed] = useState(false),
    [snapshot, setSnapshot] = useState<Dict | null>(null),
    [snapshots, setSnapshots] = useState<Dict[]>([]),
    [moduleView, setModuleView] = useState<ModuleView | null>(null),
    [result, setResult] = useState<Dict | null>(null),
    [locateSource, setLocateSource] = useState("");
  // Focus the field a quality finding points at once its module editor has rendered.
  useEffect(() => {
    if (!moduleView || !locateSource) return;
    const field = document.querySelector<HTMLElement>(
      `[aria-label="${CSS.escape(locateSource)}"]`,
    );
    if (field) {
      let ancestor = field.parentElement;
      while (ancestor) {
        if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
        ancestor = ancestor.parentElement;
      }
      field.scrollIntoView({ block: "center" });
      field.focus();
    }
    setLocateSource("");
  }, [moduleView, locateSource]);
  const [recent, setRecent] = useState<Dict[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("sports-os.recents") || "[]");
    } catch {
      return [];
    }
  });
  const run = useCallback(async (fn: () => Promise<any>) => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      const err =
        e instanceof BackendError
          ? e
          : new BackendError("UNEXPECTED", String(e));
      setError(err);
      if (err.code === "SIDECAR") setHealth(null);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  // Workspace to reopen after the sidecar restarts (everything is persisted, so nothing is lost).
  const lastWorkspace = useRef<string | null>(null);
  useEffect(() => {
    lastWorkspace.current = state?.workspace ?? null;
  }, [state?.workspace]);
  const connect = useCallback(
    () =>
      run(async () => {
        const h = await sportsOS.call("health");
        setModuleCatalog(h.modules);
        setHealth(h);
        setDirty(false);
        setSnapshot(null);
        setModuleView(null);
        const reopen = lastWorkspace.current;
        if (!reopen) {
          setState(null);
          return;
        }
        try {
          setState(
            await sportsOS.call<Workspace>("open_project", {
              workspace: reopen,
            }),
          );
          setNotice("后端已重新连接，项目已从磁盘重新打开。");
        } catch {
          setState(null);
        }
      }),
    [run],
  );
  useEffect(() => {
    void connect();
  }, [connect]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Tab") document.documentElement.dataset.input = "keyboard";
    };
    const pointer = () => {
      document.documentElement.dataset.input = "pointer";
    };
    window.addEventListener("keydown", key);
    window.addEventListener("pointerdown", pointer);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("pointerdown", pointer);
    };
  }, []);
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  useEffect(() => {
    if (!isTauri()) return;
    let disposed = false;
    let off: (() => void) | undefined;
    void getCurrentWindow()
      .onCloseRequested((e) => {
        if (dirty) {
          e.preventDefault();
          setPending(() => () => void getCurrentWindow().destroy());
        }
      })
      .then((unlisten) => {
        if (disposed) unlisten();
        else off = unlisten;
      });
    return () => {
      disposed = true;
      off?.();
    };
  }, [dirty]);
  const remember = (s: Workspace) => {
    const item = {
      ...s.project.manifest.project,
      path: s.workspace,
      modified: s.modified_at,
      quality: s.quality.status,
    };
    const list = [item, ...recent.filter((x) => x.path !== s.workspace)].slice(
      0,
      12,
    );
    setRecent(list);
    localStorage.setItem("sports-os.recents", JSON.stringify(list));
  };
  const adopt = (s: Workspace) => {
    setModuleCatalog(s.modules);
    setState(s);
    remember(s);
    setSnapshot(null);
    setDirty(false);
    setPage("Overview");
    setModuleView(null);
    setNotice("项目已打开 · SYNTHETIC");
  };
  const navigate = (next: () => void) => {
    if (dirty) setPending(() => next);
    else next();
  };
  const loadPage = (p: string) => {
    setPage(p);
    setModuleView(null);
    setResult(null);
    if (p === "Snapshots" || p === "Versions")
      void run(async () => setSnapshots(await sportsOS.call("list_snapshots")));
    else if (p === "finance.revenue")
      void run(async () =>
        setResult(
          await sportsOS.call("calculate_module", {
            module_id: p,
            ...(snapshot ? { snapshot_id: snapshot.snapshot_id } : {}),
          }),
        ),
      );
    else if (p.includes("."))
      void run(async () => {
        const schema = await sportsOS.call("get_module_schema", {
          module_id: p,
        });
        const data = snapshot
          ? snapshot.project.modules[p].payload
          : await sportsOS.call("get_module_data", { module_id: p });
        setModuleView({ id: p, schema, data });
      });
  };
  const mutate = async (method: string, params: Dict = {}) => {
    const s = await sportsOS.call<Workspace>(method, params);
    setState(s);
    remember(s);
    if (moduleView && s.project.modules[moduleView.id])
      setModuleView({
        ...moduleView,
        data: s.project.modules[moduleView.id].payload,
      });
    const added = Object.keys(s.added_modules || {});
    setNotice(
      (added.length
        ? "已自动加入所需模块：" + added.map(moduleName).join("、") + "。"
        : "") +
        (s.draft
          ? "已保存为未完成草稿，可按概览中的“开始设置”继续填写。"
          : "已保存为工作态。"),
    );
    return s;
  };
  const current = snapshot ? snapshot.project : state?.project;
  const meta = current?.manifest.project;
  const enabled = Object.keys(current?.manifest.modules || {}).filter(
    (k) => current?.manifest.modules[k],
  );
  const selectFolder = async () => {
    const path = await open({
      directory: true,
      multiple: false,
      title: "选择独立项目文件夹",
    });
    return typeof path === "string" ? path : null;
  };
  const openProject = (path?: string) =>
    void run(async () => {
      const chosen = path || (await selectFolder());
      if (chosen)
        adopt(await sportsOS.call("open_project", { workspace: chosen }));
    });
  const locate = (source: string) => {
    // Sources are "module_id" or "module_id/rows/3/field"; match whole IDs only
    // ("ticketing.rights_return/..." must not resolve to "ticketing.rights").
    const id = enabled.find((k) => source === k || source.startsWith(k + "/"));
    if (!id) {
      setNotice("此 Finding 没有可可靠定位的字段，请依据 Source 检查。");
      return;
    }
    setLocateSource(source);
    setNotice(
      "已定位模块：" +
        id +
        "。Source：" +
        source +
        "；仅精确 schema 路径可聚焦字段。",
    );
    navigate(() => loadPage(id));
  };
  const approvalVersion =
    approval === "PROJECT"
      ? state?.project.manifest.project.version
      : state?.project.modules[approval || ""]?.data_version;
  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <header className="app-bar">
        <button
          className="brand"
          onClick={() =>
            navigate(() => {
              setState(null);
              setSnapshot(null);
              setModuleView(null);
            })
          }
        >
          Sports Event OS
        </button>
        <span className="environment">SYNTHETIC / LOCAL</span>
        <span className="app-version">
          Desktop {health?.desktop_version ?? ""}
        </span>
      </header>
      {!health ? (
        <main className="startup">
          <h1>{busy ? "正在启动本地后端" : "后端不可用"}</h1>
          <p>计算、批准与数据写入仅由本地 Python Sidecar 执行。</p>
          {!busy && <button onClick={connect}>重新连接后端</button>}
        </main>
      ) : !state ? (
        <HomePage
          busy={busy}
          recent={recent}
          onOpen={openProject}
          onNew={() => setWizard(true)}
          onDemo={() =>
            void run(async () => {
              const path = await selectFolder();
              if (path)
                adopt(await sportsOS.call("create_demo", { workspace: path }));
            })
          }
        />
      ) : (
        <>
          <Sidebar
            meta={meta}
            enabled={enabled}
            page={page}
            readOnly={!!snapshot}
            busy={busy}
            collapsed={collapsed}
            onToggleCollapsed={() => setCollapsed(!collapsed)}
            onNavigate={(p) => navigate(() => loadPage(p))}
          />
          <main className="workspace">
            <div className="workspace-bar">
              <div>
                <h1>{PAGE_TITLES[page] || moduleName(page)}</h1>
                <span className="muted">
                  {snapshot
                    ? "READ ONLY · " + snapshot.snapshot_id
                    : state.draft
                      ? "Working Copy · 未完成草稿"
                      : "Working Copy"}{" "}
                  · <code>{meta?.version}</code>
                </span>
                {!snapshot && state.draft && state.can_discard && (
                  <p className="draft-banner" role="note">
                    当前工作副本是未完成草稿：命令行和桌面端看到的是同一份草稿，修正全部阻断后会自动保存为正式工作态。
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "放弃草稿中的全部修改，回到上次保存的工作态？此操作不可撤销。",
                          )
                        )
                          void run(() => mutate("discard_draft"));
                      }}
                    >
                      放弃草稿
                    </button>
                  </p>
                )}
              </div>
              <div className="actions">
                {snapshot ? (
                  <button
                    onClick={() => {
                      setSnapshot(null);
                      setPage("Overview");
                      setModuleView(null);
                    }}
                  >
                    返回工作副本
                  </button>
                ) : (
                  <>
                    <button
                      disabled={busy || dirty}
                      onClick={() => void run(() => mutate("save_project"))}
                    >
                      保存项目
                    </button>
                    <button
                      disabled={busy || dirty}
                      onClick={() =>
                        void run(async () => {
                          setState({
                            ...state,
                            quality: await sportsOS.call("validate_project"),
                          });
                          loadPage("Quality Gate");
                        })
                      }
                    >
                      检查
                    </button>
                    <button
                      disabled={busy || dirty}
                      onClick={() => setApproval("PROJECT")}
                    >
                      记录项目批准
                    </button>
                  </>
                )}
              </div>
            </div>
            {snapshot && (
              <div className="readonly-banner">
                READ ONLY · 冻结快照。任何工作态编辑都不会更改此版本。
              </div>
            )}
            {dirty && (
              <div className="draft-banner">
                存在尚未提交的编辑。提交将使相关模块及项目原批准失效。
              </div>
            )}
            {busy && (
              <div role="status" className="loading-line">
                正在处理，请稍候…
              </div>
            )}
            <div className="content">
              {page === "Overview" && (
                <OverviewPage
                  meta={meta}
                  workspace={state.workspace}
                  enabled={enabled}
                  modules={current?.modules}
                  setup={snapshot ? undefined : state.setup}
                  onOpenModule={loadPage}
                />
              )}
              {page === "Modules" && (
                <ModulesPage
                  modules={state.modules}
                  enabled={enabled}
                  busy={busy}
                  onToggle={(id) =>
                    void run(() =>
                      mutate(
                        enabled.includes(id) ? "disable_module" : "enable_module",
                        { module_id: id },
                      ),
                    )
                  }
                />
              )}
              {moduleView && page === moduleView.id && (
                <ModulePage
                  view={moduleView}
                  state={current?.modules[page]}
                  snapshotId={snapshot?.snapshot_id ?? null}
                  busy={busy}
                  dirty={dirty}
                  onApprove={() => setApproval(page)}
                  onDirty={setDirty}
                  onSubmit={async (payload) => {
                    const s = await run(() =>
                      mutate("update_module_data", {
                        module_id: page,
                        payload,
                      }),
                    );
                    if (s) {
                      setModuleView({
                        ...moduleView,
                        data: s.project.modules[page].payload,
                      });
                      setDirty(false);
                    }
                  }}
                />
              )}
              {page === "Quality Gate" && (
                <GateView gate={state.quality} onLocate={locate} />
              )}
              {page === "finance.revenue" && <RevenuePage result={result} />}
              {page === "Snapshots" && (
                <SnapshotsPage
                  snapshots={snapshots}
                  releaseStatus={state.release_quality.status}
                  readOnly={!!snapshot}
                  busy={busy}
                  dirty={dirty}
                  onCreate={(ack) =>
                    void run(async () => {
                      await sportsOS.call("create_snapshot", {
                        ack_warnings: ack,
                      });
                      setSnapshots(await sportsOS.call("list_snapshots"));
                      setNotice("快照及发布件已生成，历史数据只读。");
                    })
                  }
                  onOpen={(snapshotId) =>
                    void run(async () => {
                      setSnapshot(
                        await sportsOS.call("get_snapshot", {
                          snapshot_id: snapshotId,
                        }),
                      );
                      setPage("Overview");
                    })
                  }
                />
              )}
              {page === "Versions" && (
                <VersionsPage
                  snapshots={snapshots}
                  busy={busy}
                  onCompare={(oldRef, newRef) =>
                    run(() =>
                      sportsOS.call("compare_versions", {
                        old: oldRef,
                        new: newRef,
                      }),
                    )
                  }
                />
              )}
            </div>
          </main>
        </>
      )}
      <footer className="statusbar">
        <span role="status">
          {notice || "离线 / 合成数据"}
          {busy ? " · 正在处理" : ""}
        </span>
      </footer>
      {error && !wizard && !approval && (
        <ErrorPanel
          error={error}
          onClose={() => setError(null)}
          onReopen={
            state
              ? () => {
                  const path = state.workspace;
                  setError(null);
                  openProject(path);
                }
              : undefined
          }
        />
      )}
      <Modal title="新建项目" open={wizard} onClose={() => setWizard(false)}>
        {error && <ErrorNotice error={error} onClose={() => setError(null)} />}
        {health && (
          <Wizard
            modules={health.modules}
            templates={health.templates || []}
            defaultTimezone={health.default_timezone}
            busy={busy}
            onCreate={async (values) => {
              const s = await run(async () => {
                const path = await selectFolder();
                if (!path) return;
                return sportsOS.call<Workspace>("create_project", {
                  workspace: path,
                  ...values,
                });
              });
              if (s) {
                adopt(s);
                setWizard(false);
                setNotice("项目已创建：" + s.workspace + "。按“开始设置”的顺序填写即可。");
              }
            }}
          />
        )}
      </Modal>
      <ApprovalDialog
        key={approval ?? "closed"}
        target={approval}
        version={approvalVersion}
        busy={busy}
        error={error}
        onClearError={() => setError(null)}
        onClose={() => setApproval(null)}
        onSubmit={(approvalRef) =>
          void run(async () => {
            await mutate(
              approval === "PROJECT" ? "approve_project" : "approve_module",
              approval === "PROJECT"
                ? { approval_ref: approvalRef, version: approvalVersion }
                : {
                    module_id: approval,
                    approval_ref: approvalRef,
                    data_version: approvalVersion,
                  },
            );
            setApproval(null);
          })
        }
      />
      <Modal
        title="尚未提交的编辑"
        open={!!pending}
        onClose={() => setPending(null)}
      >
        <p>离开将丢弃当前界面草稿。已经提交给后端的数据不受影响。</p>
        <button onClick={() => setPending(null)}>继续编辑</button>
        <button
          onClick={() => {
            setDirty(false);
            const action = pending;
            setPending(null);
            action?.();
          }}
        >
          丢弃界面草稿并离开
        </button>
      </Modal>
    </div>
  );
}
