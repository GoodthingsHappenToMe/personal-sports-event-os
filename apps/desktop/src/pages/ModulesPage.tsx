import { Dict, moduleCategory, moduleDescription, moduleName } from "../api";

/** Module catalog with dependency information; also used by the new-project wizard. */
export function ModuleList({
  modules,
  selected,
  onToggle,
  busy,
}: {
  modules: Dict[];
  selected: string[];
  onToggle: (id: string) => void;
  busy: boolean;
}) {
  return (
    <table>
      <caption className="sr-only">模块选择及依赖</caption>
      <thead>
        <tr>
          <th>启用</th>
          <th>模块 / 分类</th>
          <th>Requires</th>
          <th>Provides</th>
        </tr>
      </thead>
      <tbody>
        {modules.map((m) => (
          <tr key={m.module_id}>
            <td>
              <input
                type="checkbox"
                aria-label={`启用 ${m.module_id}`}
                checked={selected.includes(m.module_id)}
                disabled={busy}
                onChange={() => onToggle(m.module_id)}
              />
            </td>
            <td>
              {moduleName(m.module_id)}
              <small>
                {m.module_id} · {moduleCategory(m.module_id)}
              </small>
              <small>
                {moduleDescription(m.module_id) ||
                  "维护 " + moduleName(m.module_id) + " 数据"}
              </small>
            </td>
            <td>
              {[...m.dependencies, ...m.requires_capabilities].join(", ") ||
                "—"}
            </td>
            <td>{m.provides.join(", ") || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ModulesPage({
  modules,
  enabled,
  busy,
  onToggle,
}: {
  modules: Dict[];
  enabled: string[];
  busy: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <>
      <p className="muted">
        启用一个模块时，它需要的其他模块会自动一起启用；禁用会保留数据，不会修改历史快照。
      </p>
      <ModuleList
        modules={modules}
        selected={enabled}
        busy={busy}
        onToggle={onToggle}
      />
    </>
  );
}
