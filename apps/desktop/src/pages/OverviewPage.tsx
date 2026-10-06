import { Dict, moduleName } from "../api";
import { Empty, Status } from "../components";

const SETUP_LABELS: Dict = {
  DONE: "完成",
  TODO: "待填写",
  FIX: "有问题",
  WAITING: "等待前置模块",
  AUTO: "自动计算",
};

/** Ordered "fill these in" list shown until every module is complete. */
export function SetupChecklist({
  setup,
  onOpenModule,
}: {
  setup: Dict;
  onOpenModule: (id: string) => void;
}) {
  return (
    <section className="setup-checklist" aria-label="开始设置">
      <div className="section-line">
        <h2>开始设置</h2>
        <span>
          已完成 {setup.done} / {setup.total}
        </span>
      </div>
      <p className="muted">
        按顺序填写即可：每一步只依赖前面已完成的内容。未完成的项目会自动保存为草稿，随时可以继续。
      </p>
      <ol>
        {setup.modules.map((m: Dict) => {
          const next = m.module_id === setup.next;
          return (
            <li key={m.module_id} className={next ? "next" : ""}>
              <span className={`setup-state ${m.status.toLowerCase()}`}>
                {SETUP_LABELS[m.status] || m.status}
              </span>
              <span className="setup-name">
                <strong>{m.display_name}</strong>
                <small>
                  {m.status === "WAITING"
                    ? "先完成：" + m.waiting_for.map(moduleName).join("、")
                    : m.status === "FIX"
                      ? `${m.blocks} 个问题需要修正，可在“质量检查”中定位`
                      : m.description}
                </small>
              </span>
              {m.status !== "AUTO" && m.status !== "WAITING" && (
                <button
                  className={next ? "primary" : ""}
                  onClick={() => onOpenModule(m.module_id)}
                >
                  {next ? "去填写" : m.status === "DONE" ? "查看" : "填写"}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Project identity and the approval state of every enabled module. */
export function OverviewPage({
  meta,
  workspace,
  enabled,
  modules,
  setup,
  onOpenModule,
}: {
  meta: Dict | undefined;
  workspace: string;
  enabled: string[];
  modules: Record<string, Dict> | undefined;
  setup?: Dict;
  onOpenModule: (id: string) => void;
}) {
  return (
    <>
      {setup && !setup.complete && setup.total > 0 && (
        <SetupChecklist setup={setup} onOpenModule={onOpenModule} />
      )}
      <section className="overview-meta">
        <h2>{meta?.name}</h2>
        <dl>
          <dt>项目 ID</dt>
          <dd>
            <code>{meta?.id}</code>
          </dd>
          <dt>版本</dt>
          <dd>
            <code>{meta?.version}</code>
          </dd>
          <dt>状态</dt>
          <dd>
            <Status value={meta?.status} />
          </dd>
          <dt>时区</dt>
          <dd>{meta?.timezone}</dd>
          <dt>项目目录</dt>
          <dd>{workspace}</dd>
        </dl>
      </section>
      <div className="section-line">
        <h2>项目能力</h2>
        <span>{enabled.length} 个启用模块</span>
      </div>
      <table>
        <caption className="sr-only">启用模块状态</caption>
        <thead>
          <tr>
            <th>模块</th>
            <th>工作版本</th>
            <th>批准状态</th>
            <th>批准引用</th>
          </tr>
        </thead>
        <tbody>
          {enabled.map((id) => (
            <tr key={id}>
              <td>
                <button className="text-button" onClick={() => onOpenModule(id)}>
                  {moduleName(id)}
                </button>
                <small>{id}</small>
              </td>
              <td>
                <code>{modules?.[id]?.data_version}</code>
              </td>
              <td>
                <Status value={modules?.[id]?.status || "DRAFT"} />
              </td>
              <td>{modules?.[id]?.approval_ref || "尚未批准"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!enabled.length && (
        <Empty title="尚未选择能力模块">
          前往“能力模块”启用所需功能，不需要票务能力的赛事也可独立运行。
        </Empty>
      )}
    </>
  );
}
