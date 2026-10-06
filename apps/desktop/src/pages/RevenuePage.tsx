import { useState } from "react";
import { Dict, display } from "../api";
import { Empty } from "../components";

/** finance.revenue has no input data; this page shows its calculated preview. */
export function RevenuePage({ result }: { result: Dict | null }) {
  if (!result)
    return (
      <Empty title="收入结果暂不可用">
        请先处理 Quality Gate 中的阻断项；界面不会使用旧数据伪装本次结果。
      </Empty>
    );
  return <Revenue result={result} />;
}

function Revenue({ result }: { result: Dict }) {
  const [group, setGroup] = useState("by_stage");
  const totals = result.totals;
  return (
    <section>
      <div className="revenue-total">
        <span>满售容量收入 Full Revenue</span>
        <strong>{display(totals.full_revenue)}</strong>
        <small>{result.unit} · 后端精确值 · READ ONLY</small>
      </div>
      <table>
        <caption>需求情景 / 票张与计费口径</caption>
        <thead>
          <tr>
            <th>情景</th>
            <th>收入</th>
            <th>Public Revenue</th>
            <th>Rights Revenue</th>
            <th>Public Expected Tickets</th>
            <th>Rights Allocated</th>
            <th>Rights Expected Fulfilled</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(totals.scenarios).map(([name, s]: [string, any]) => (
            <tr key={name}>
              <th>{name}</th>
              {[
                "revenue",
                "public_revenue",
                "rights_revenue",
                "public_expected_tickets",
                "rights_allocated",
                "rights_expected_fulfilled",
              ].map((k) => (
                <td className="number" key={k}>
                  {display(s[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="section-line">
        <label>
          分组查看
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="by_stage">阶段 By Stage</option>
            <option value="by_tier">票档 By Tier</option>
            <option value="by_session">场次 By Session</option>
          </select>
        </label>
      </div>
      <table>
        <caption>分组收入</caption>
        <thead>
          <tr>
            <th>分组</th>
            <th>满售收入</th>
            {Object.keys(totals.scenarios).map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(result[group]).map(([k, r]: [string, any]) => (
            <tr key={k}>
              <th>{k}</th>
              <td className="number">{display(r.full_revenue)}</td>
              {Object.keys(totals.scenarios).map((n) => (
                <td className="number" key={n}>
                  {display(r.scenarios[n].revenue)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <details>
        <summary>敏感性与口径说明</summary>
        <pre>{JSON.stringify(result.sensitivity, null, 2)}</pre>
        {result.notes.map((n: string) => (
          <p key={n}>{n}</p>
        ))}
      </details>
    </section>
  );
}
