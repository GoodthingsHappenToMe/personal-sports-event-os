import { Dict } from "../api";
import { Empty, Status } from "../components";

/** Project list shown when no project is open. */
export function HomePage({
  busy,
  recent,
  onOpen,
  onNew,
  onDemo,
}: {
  busy: boolean;
  recent: Dict[];
  onOpen: (path?: string) => void;
  onNew: () => void;
  onDemo: () => void;
}) {
  return (
    <main className="home">
      <div className="page-heading">
        <div>
          <h1>项目 Projects</h1>
          <p className="muted">
            一个项目，一个文件夹。业务事实、批准与历史版本留在本机。
          </p>
        </div>
        <div className="actions">
          <button disabled={busy} onClick={() => onOpen()}>
            打开项目
          </button>
          <button className="primary" disabled={busy} onClick={onNew}>
            新建项目
          </button>
        </div>
      </div>
      <div className="section-line">
        <h2>最近项目</h2>
        <button disabled={busy} onClick={onDemo}>
          在空目录创建演示项目
        </button>
      </div>
      {!recent.length ? (
        <Empty title="开始第一个赛事项目">
          新建空项目、选择模块组合，或创建完全虚构的 2027 演示项目。
        </Empty>
      ) : (
        <div
          className="table-scroll"
          tabIndex={0}
          role="region"
          aria-label="可横向滚动的数据表"
        >
          <table>
            <caption className="sr-only">最近项目列表</caption>
            <thead>
              <tr>
                <th>项目 / ID</th>
                <th>状态</th>
                <th>版本</th>
                <th>最后修改</th>
                <th>质量</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((p) => (
                <tr key={p.path}>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => onOpen(p.path)}
                    >
                      {p.name}
                    </button>
                    <small>
                      {p.id} · {p.path}
                    </small>
                  </td>
                  <td>
                    <Status value={p.status} />
                  </td>
                  <td>
                    <code>{p.version}</code>
                  </td>
                  <td>{new Date(p.modified).toLocaleString()}</td>
                  <td>
                    <Status value={p.quality} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
