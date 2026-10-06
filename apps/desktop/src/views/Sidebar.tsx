import { Dict, moduleName } from "../api";
import { Status } from "../components";

export const PAGE_TITLES: Dict = {
  Overview: "项目概览",
  Modules: "能力模块",
  "Quality Gate": "Quality Gate",
  Versions: "版本比较",
  Snapshots: "批准快照",
};
const NAV_LABELS: Dict = {
  Overview: "概览",
  Modules: "能力模块",
  "Quality Gate": "质量检查",
  Versions: "版本比较",
  Snapshots: "快照",
};
/** Pages that only make sense for the editable working copy. */
const WORKING_ONLY = ["Modules", "Quality Gate"];

export function Sidebar({
  meta,
  enabled,
  page,
  readOnly,
  busy,
  collapsed,
  onToggleCollapsed,
  onNavigate,
}: {
  meta: Dict | undefined;
  enabled: string[];
  page: string;
  readOnly: boolean;
  busy: boolean;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onNavigate: (page: string) => void;
}) {
  const visible = (k: string) => !readOnly || !WORKING_ONLY.includes(k);
  return (
    <aside className="sidebar">
      <button aria-label="收起或展开导航" onClick={onToggleCollapsed}>
        {collapsed ? "展开导航" : "收起导航"}
      </button>
      <div className="project-identity">
        <strong>{meta?.name}</strong>
        <code>{meta?.id}</code>
        <Status value={readOnly ? "READ ONLY" : meta?.status} />
      </div>
      <nav aria-label="项目导航">
        {["Overview", ...enabled].filter(visible).map((p) => (
          <button
            aria-current={page === p ? "page" : undefined}
            key={p}
            onClick={() => onNavigate(p)}
          >
            {NAV_LABELS[p] || moduleName(p)}
          </button>
        ))}
      </nav>
      <nav className="utility-nav" aria-label="版本与质量导航">
        {["Modules", "Quality Gate", "Versions", "Snapshots"]
          .filter(visible)
          .map((p) => (
            <button
              disabled={busy}
              aria-current={page === p ? "page" : undefined}
              key={p}
              onClick={() => onNavigate(p)}
            >
              {NAV_LABELS[p]}
            </button>
          ))}
      </nav>
      <div className="sidebar-footer">本机项目 · 无平台连接</div>
    </aside>
  );
}
