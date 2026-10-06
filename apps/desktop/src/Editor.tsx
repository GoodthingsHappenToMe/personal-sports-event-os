import { createContext, useContext, useEffect, useState } from "react";
import { Dict, display } from "./api";
import { Empty } from "./components";

const OriginalData = createContext<Dict>({});
export function blank(schema: Dict): any {
  if ("const" in schema) return schema.const;
  if (schema.enum) return schema.enum[0];
  const kind = Array.isArray(schema.type) ? schema.type[0] : schema.type;
  if (Array.isArray(schema.type) && schema.type.includes("null")) return null;
  if (kind === "array") return [];
  if (kind === "object" || !kind)
    return Object.fromEntries(
      Object.entries(schema.properties || {})
        .filter(([k]) => (schema.required || []).includes(k))
        .map(([k, s]) => [k, blank(s as Dict)]),
    );
  if (kind === "boolean") return false;
  if (kind === "number" || kind === "integer") return schema.minimum ?? 0;
  return "";
}
function Scalar({
  schema,
  value,
  onChange,
  path,
  readOnly,
}: {
  schema: Dict;
  value: any;
  onChange: (v: any) => void;
  path: string;
  readOnly: boolean;
}) {
  const baseline = useContext(OriginalData);
  const baseValue = path
    .split("/")
    .slice(1)
    .reduce((v, k) => v?.[k], baseline);
  const changed = JSON.stringify(baseValue) !== JSON.stringify(value);
  const [original, setOriginal] = useState(value);
  const types = Array.isArray(schema.type) ? schema.type : [schema.type];
  const nullable = types.includes("null");
  const numeric = types.includes("number") || types.includes("integer");
  const invalid =
    numeric &&
    (typeof value !== "number" || !Number.isFinite(value)) &&
    value !== null;
  const keys = {
    onFocus: () => setOriginal(value),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onChange(original);
        e.stopPropagation();
      }
      if (e.key === "Enter" && e.currentTarget instanceof HTMLInputElement)
        e.currentTarget.select();
    },
  };
  if (readOnly)
    return <span className={numeric ? "number" : ""}>{display(value)}</span>;
  const control = schema.enum ? (
    <select
      aria-label={path}
      value={value ?? ""}
      onChange={(e) =>
        onChange(schema.enum.find((v: any) => String(v) === e.target.value))
      }
      {...keys}
    >
      {schema.enum.map((v: any) => (
        <option key={String(v)} value={String(v)}>
          {String(v)}
        </option>
      ))}
    </select>
  ) : types.includes("boolean") ? (
    <input
      type="checkbox"
      aria-label={path}
      checked={!!value}
      onChange={(e) => onChange(e.target.checked)}
      {...keys}
    />
  ) : (
    <input
      aria-label={path}
      aria-invalid={invalid}
      className={numeric ? "number" : ""}
      value={value ?? ""}
      disabled={value === null}
      inputMode={numeric ? "decimal" : undefined}
      placeholder={
        schema.format === "date-time" ? "2027-01-01T09:00:00+08:00" : undefined
      }
      onChange={(e) => {
        const v = e.target.value;
        onChange(
          numeric && v.trim() !== "" && Number.isFinite(Number(v))
            ? Number(v)
            : v,
        );
      }}
      {...keys}
    />
  );
  return (
    <div
      className={`scalar ${changed ? "cell-dirty" : ""}`}
      data-dirty={changed || undefined}
    >
      {control}
      {changed && <small className="dirty-label">未提交</small>}
      {nullable && (
        <label className="null-toggle">
          <input
            type="checkbox"
            checked={value === null}
            onChange={(e) =>
              onChange(
                e.target.checked
                  ? null
                  : blank({
                      ...schema,
                      type: types.filter((t) => t !== "null"),
                    }),
              )
            }
          />
          空值
        </label>
      )}
      {invalid && <small className="field-error">请输入有效数字</small>}
    </div>
  );
}
export function SchemaField({
  schema,
  value,
  onChange,
  path,
  readOnly = false,
}: {
  schema: Dict;
  value: any;
  onChange: (v: any) => void;
  path: string;
  readOnly?: boolean;
}) {
  const type = Array.isArray(schema.type)
    ? schema.type.find((t: string) => t !== "null")
    : schema.type;
  if (schema.enum || schema.const !== undefined)
    return (
      <Scalar
        {...{
          schema,
          value,
          onChange,
          path,
          readOnly: readOnly || schema.const !== undefined,
        }}
      />
    );
  if (type === "array") {
    const rows = Array.isArray(value) ? value : [];
    const item = schema.items || {};
    if (item.type === "object") {
      const columns = Object.entries(item.properties || {});
      return (
        <div className="array-editor">
          <div className="table-meta">
            <span>
              {path} · {rows.length} 行
            </span>
            {!readOnly && (
              <button onClick={() => onChange([...rows, blank(item)])}>
                新增行
              </button>
            )}
          </div>
          {!rows.length ? (
            <Empty title="还没有数据行">
              使用“新增行”录入合成数据；必填项和业务关系会交由后端检查。
            </Empty>
          ) : (
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="可横向滚动的数据表"
            >
              <table>
                <caption className="sr-only">{path} 数据表</caption>
                <thead>
                  <tr>
                    <th scope="col">行</th>
                    {columns.map(([k]) => (
                      <th scope="col" key={k}>
                        {k}
                      </th>
                    ))}
                    {!readOnly && <th scope="col">操作</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any, i: number) => (
                    <tr key={i}>
                      <th scope="row">{i + 1}</th>
                      {columns.map(([k, s]) => {
                        const optional = !(item.required || []).includes(k);
                        return (
                          <td
                            key={k}
                            data-field={`${path}/${i}/${k}`}
                          >
                            {optional && !(k in row) ? (
                              <button
                                disabled={readOnly}
                                onClick={() =>
                                  onChange(
                                    rows.map((x: any, j: number) =>
                                      j === i
                                        ? { ...x, [k]: blank(s as Dict) }
                                        : x,
                                    ),
                                  )
                                }
                              >
                                添加 {k}
                              </button>
                            ) : (
                              <SchemaField
                                schema={s as Dict}
                                value={row[k]}
                                path={`${path}/${i}/${k}`}
                                readOnly={readOnly}
                                onChange={(v) =>
                                  onChange(
                                    rows.map((x: any, j: number) =>
                                      j === i ? { ...x, [k]: v } : x,
                                    ),
                                  )
                                }
                              />
                            )}
                          </td>
                        );
                      })}
                      {!readOnly && (
                        <td>
                          <button
                            aria-label={`删除 ${path} 第 ${i + 1} 行`}
                            onClick={() =>
                              onChange(
                                rows.filter((_: any, j: number) => j !== i),
                              )
                            }
                          >
                            删除
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      );
    }
    return (
      <div className="array-values">
        {rows.map((v: any, i: number) => (
          <div className="section-line" key={i}>
            <SchemaField
              schema={item}
              value={v}
              onChange={(x) =>
                onChange(rows.map((r: any, j: number) => (j === i ? x : r)))
              }
              path={`${path}/${i}`}
              readOnly={readOnly}
            />
            {!readOnly && (
              <button
                aria-label={`删除 ${path} ${i}`}
                onClick={() =>
                  onChange(rows.filter((_: any, j: number) => i !== j))
                }
              >
                删除
              </button>
            )}
          </div>
        ))}
        {!readOnly && (
          <button onClick={() => onChange([...rows, blank(item)])}>
            添加条目
          </button>
        )}
      </div>
    );
  }
  if (type === "object" || schema.properties || schema.additionalProperties) {
    const obj = value || {};
    const properties = schema.properties || {};
    const entries = Object.entries({
      ...Object.fromEntries(
        Object.keys(obj).map((k) => [k, schema.additionalProperties || {}]),
      ),
      ...properties,
    });
    return (
      <details className="object-fields" open={!path.includes("/")}>
        <summary>
          {path.split("/").at(-1)} · {Object.keys(obj).length} 字段
        </summary>
        <div className="field-stack">
          {entries.map(([k, s]) => (
            <div className="field" key={k}>
              <span className="field-label">
                {k}
                {(schema.required || []).includes(k) ? " *" : ""}
              </span>
              {!(k in obj) && !(schema.required || []).includes(k) ? (
                <button
                  disabled={readOnly}
                  onClick={() => onChange({ ...obj, [k]: blank(s as Dict) })}
                >
                  添加可选字段
                </button>
              ) : (
                <SchemaField
                  schema={s as Dict}
                  value={obj[k]}
                  path={`${path}/${k}`}
                  readOnly={readOnly}
                  onChange={(v) => onChange({ ...obj, [k]: v })}
                />
              )}
            </div>
          ))}
          {schema.additionalProperties &&
            typeof schema.additionalProperties === "object" &&
            !readOnly && (
              <MapAdd
                onAdd={(k) => {
                  if (!(k in obj))
                    onChange({
                      ...obj,
                      [k]: blank(schema.additionalProperties),
                    });
                }}
              />
            )}
        </div>
      </details>
    );
  }
  return <Scalar {...{ schema, value, onChange, path, readOnly }} />;
}
function MapAdd({ onAdd }: { onAdd: (key: string) => void }) {
  const [key, setKey] = useState("");
  return (
    <div className="section-line">
      <input
        aria-label="新字段键"
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <button
        disabled={!key.trim()}
        onClick={() => {
          onAdd(key.trim());
          setKey("");
        }}
      >
        添加字段键
      </button>
    </div>
  );
}
export function ModuleEditor({
  id,
  schema,
  data,
  readOnly,
  onSubmit,
  onDirty,
}: {
  id: string;
  schema: Dict;
  data: Dict;
  readOnly: boolean;
  onSubmit: (v: Dict) => Promise<void>;
  onDirty: (v: boolean) => void;
}) {
  const [draft, setDraft] = useState(data);
  const [saving, setSaving] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(data);
  useEffect(() => {
    setDraft(data);
  }, [data, id]);
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  return (
    <section aria-label="模块编辑器">
      <div className="editor-actions">
        <span role="status">
          {readOnly
            ? "READ ONLY · 冻结数据"
            : dirty
              ? "已修改 · 提交将使原批准失效"
              : "与后端工作态一致"}
        </span>
        {!readOnly && (
          <>
            <button disabled={!dirty || saving} onClick={() => setDraft(data)}>
              撤销未提交更改
            </button>
            <button
              className="primary"
              disabled={!dirty || saving}
              onClick={async () => {
                setSaving(true);
                try {
                  await onSubmit(draft);
                } finally {
                  setSaving(false);
                }
              }}
            >
              {saving ? "正在提交…" : "提交工作数据"}
            </button>
          </>
        )}
      </div>
      <OriginalData.Provider value={data}>
        <SchemaField
          schema={schema}
          value={draft}
          path={id}
          readOnly={readOnly}
          onChange={setDraft}
        />
      </OriginalData.Provider>
    </section>
  );
}
