import { useState } from "react";
import { Dict, moduleName } from "../api";
import { ModuleList } from "../pages/ModulesPage";

const browserTimezone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
};

/**
 * New project in one screen: a name and the kind of event. Everything else has a sensible default
 * (project ID from the name, this computer's time zone, a new folder for the project, and every module
 * the choice needs) and can be changed under "更多设置".
 */
export function Wizard({
  modules,
  templates,
  defaultTimezone,
  busy,
  onCreate,
}: {
  modules: Dict[];
  templates: Dict[];
  defaultTimezone?: string;
  busy: boolean;
  onCreate: (p: Dict) => void;
}) {
  const [name, setName] = useState(""),
    [template, setTemplate] = useState(
      templates.find((t) => t.id === "ticketed-indoor-event")?.id ||
        templates[0]?.id ||
        "custom",
    ),
    [custom, setCustom] = useState<string[]>([]),
    [id, setId] = useState(""),
    [timezone, setTimezone] = useState(
      browserTimezone() || defaultTimezone || "UTC",
    );
  const chosen = templates.find((t) => t.id === template);
  return (
    <div className="wizard">
      <label className="field">
        项目名称
        <input
          autoFocus
          value={name}
          placeholder="例如：2027 夏季公开赛"
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <fieldset className="template-choices">
        <legend>这是什么类型的活动？</legend>
        {templates.map((t) => (
          <label
            key={t.id}
            className={`template-choice ${template === t.id ? "selected" : ""}`}
          >
            <input
              type="radio"
              name="template"
              checked={template === t.id}
              onChange={() => setTemplate(t.id)}
            />
            <span>
              <strong>{t.label}</strong>
              <small>{t.description}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {template === "custom" ? (
        <div className="wizard-modules">
          <p className="muted">
            勾选需要的功能。它们依赖的模块会自动加上，之后也可以在“能力模块”里随时调整。
          </p>
          <ModuleList
            modules={modules}
            selected={custom}
            busy={busy}
            onToggle={(m) =>
              setCustom(
                custom.includes(m)
                  ? custom.filter((k) => k !== m)
                  : [...custom, m],
              )
            }
          />
        </div>
      ) : (
        chosen && (
          <p className="muted template-includes">
            包含：{chosen.modules.map(moduleName).join("、")}
          </p>
        )
      )}
      <details className="more-settings">
        <summary>更多设置（可选）</summary>
        <label className="field">
          项目 ID
          <input
            value={id}
            placeholder="留空则根据名称自动生成"
            onChange={(e) => setId(e.target.value)}
          />
        </label>
        <label className="field">
          时区 Timezone
          <input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
        </label>
      </details>
      <p className="muted">
        仅用于合成项目，不录入真实公司或个人数据。下一步选择保存位置：可以选任意文件夹，会在里面为项目新建一个文件夹。
      </p>
      <div className="dialog-actions">
        <button
          className="primary"
          disabled={busy || !name.trim()}
          onClick={() =>
            onCreate({
              identity: { name: name.trim(), id: id.trim(), timezone },
              template,
              modules: template === "custom" ? custom : [],
            })
          }
        >
          选择保存位置并创建
        </button>
      </div>
    </div>
  );
}
