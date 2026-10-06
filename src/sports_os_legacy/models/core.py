import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .schema import SCHEMA, HOLD_FIELDS

class ModelError(ValueError):
    pass

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def load_json(path):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result:
                raise ModelError(f"重复JSON键: {k}")
            result[k] = v
        return result
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=pairs,
                         parse_constant=lambda s: (_ for _ in ()).throw(ModelError(f"非有限数字: {s}")))

def _shape(value, spec, path):
    types = {"object":dict,"array":list,"string":str,"boolean":bool,
             "number":(int,float),"integer":int,"null":type(None)}
    ts = spec.get("type")
    if ts:
        ts = ts if isinstance(ts,list) else [ts]
        valid = any(isinstance(value, types[t]) and not (t in ("number","integer") and isinstance(value,bool)) for t in ts)
        if not valid:
            raise ModelError(f"{path}: 类型应为 {ts}")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if not math.isfinite(value):
            raise ModelError(f"{path}: 数值必须有限")
        if value < spec.get("minimum",-math.inf) or value > spec.get("maximum",math.inf):
            raise ModelError(f"{path}: 超出取值范围")
    if "const" in spec and (type(value) is not type(spec["const"]) or value != spec["const"]):
        raise ModelError(f"{path}: 应为 {spec['const']!r}")
    if "enum" in spec and value not in spec["enum"]:
        raise ModelError(f"{path}: 未知枚举 {value!r}")
    if isinstance(value,str) and len(value.strip()) < spec.get("minLength",0):
        raise ModelError(f"{path}: 必填字符串为空")
    if isinstance(value,dict):
        for key in spec.get("required",[]):
            if key not in value:
                raise ModelError(f"{path}/{key}: 缺少必填字段")
        for key, item in value.items():
            child = spec.get("properties",{}).get(key, spec.get("additionalProperties",{}))
            if child is False:
                raise ModelError(f"{path}/{key}: 未知字段（不接受个人数据或重复派生字段）")
            if isinstance(child,dict):
                _shape(item,child,f"{path}/{key}")
    if isinstance(value,list) and "items" in spec:
        for i,item in enumerate(value):
            _shape(item,spec["items"],f"{path}/{i}")

def moment(value):
    try:
        d = datetime.fromisoformat(value.replace("Z","+00:00"))
    except (ValueError,AttributeError) as e:
        raise ModelError(f"无效ISO时间: {value!r}") from e
    if d.tzinfo is None:
        raise ModelError(f"时间必须包含UTC偏移: {value}")
    return d

def sellable(row):
    return row["physical_capacity"] - sum(row[k] for k in HOLD_FIELDS)

def seating_key(row):
    return (row["session_id"], row["zone_id"], row["tier"])

def occupancy(product, units=1):
    if not isinstance(units,int) or isinstance(units,bool) or units < 0:
        raise ModelError("产品份数必须为非负整数")
    return {seating_key(c):c["ticket_quantity"]*units for c in product["included_sessions"]}

def price_key(row):
    return (row['session_id'], row.get('price_class_id', row['tier']))

def assert_model(data):
    _shape(data,SCHEMA,"$")
    try:
        ZoneInfo(data["event"]["timezone"])
    except (ZoneInfoNotFoundError,ValueError) as e:
        raise ModelError("未知赛事时区") from e
    keys = {
        "sessions":lambda r:r["session_id"], "seating":seating_key,
        "prices":price_key,
        "inventory":lambda r:r["inventory_id"], "products":lambda r:r["product_id"],
        "rules":lambda r:r["rule_id"], "tasks":lambda r:r["task_id"],
        "decisions":lambda r:r["decision_id"],
    }
    for group,key in keys.items():
        ids = [key(r) for r in data[group]]
        if len(set(ids)) != len(ids):
            raise ModelError(f"{group}: 重复主键")
    for group in ("sessions","seating","prices","rules"):
        if not data[group]:
            raise ModelError(f"{group}: 不能为空")
    sessions = {r["session_id"] for r in data["sessions"]}
    seats = {seating_key(r) for r in data["seating"]}
    prices = {price_key(r) for r in data["prices"]}
    for s in data["sessions"]:
        if s["event_id"] != data["event"]["event_id"]:
            raise ModelError("session.event_id 外键不存在")
        moment(s["start_time"]); moment(s["end_time"])
    for s in data["seating"]:
        if s["session_id"] not in sessions or price_key(s) not in prices:
            raise ModelError("seating: 场次或票价外键不存在")
    for p in data["prices"]:
        if p["session_id"] not in sessions:
            raise ModelError("price: 场次外键不存在")
        moment(p["valid_from"])
    for inv in data["inventory"]:
        if seating_key(inv) not in seats:
            raise ModelError("inventory: 座区外键不存在")
        moment(inv["as_of"])
    for p in data["products"]:
        if not p["included_sessions"]:
            raise ModelError("产品必须包含至少一个占票映射")
        parts = [seating_key(c) for c in p["included_sessions"]]
        if len(set(parts)) != len(parts) or not set(parts) <= seats:
            raise ModelError("产品占票映射重复或引用不存在的座区")
        if any(c["ticket_quantity"] <= 0 for c in p["included_sessions"]):
            raise ModelError("产品占票量必须为正整数")
        if p["product_type"] == "SINGLE" and (len(parts)!=1 or sum(occupancy(p).values())!=1):
            raise ModelError("单场票必须占用一张门票")
        if p["product_type"] == "TRAVEL" and "travel" not in p:
            raise ModelError("旅行包缺成本结构")
    for rule in data["rules"]:
        moment(rule["valid_from"]); moment(rule["valid_to"])
    tasks = {t["task_id"] for t in data["tasks"]}
    graph = {t["task_id"]:t["depends_on"] for t in data["tasks"]}
    def visit(key, stack):
        if key in stack:
            raise ModelError("任务依赖形成循环")
        for dep in graph[key]:
            if dep not in tasks:
                raise ModelError("任务依赖外键不存在")
            visit(dep,stack|{key})
    for t in data["tasks"]:
        moment(t["due_at"]); visit(t["task_id"],set())
    for d in data["decisions"]:
        moment(d["effective_at"])
    tiers = {s["tier"] for s in data["seating"]}
    for name,sc in data["scenarios"].items():
        if set(sc["session_rates"]) != sessions or set(sc["tier_rates"]) != tiers:
            raise ModelError(f"scenarios/{name}: 场次和票档售罄率必须完整且无多余键")
    return data
