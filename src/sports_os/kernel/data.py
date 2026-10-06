import json
import math
from datetime import datetime
from pathlib import Path

class KernelError(ValueError):
    pass

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def load_json(path):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result:
                raise KernelError(f"重复JSON键: {k}")
            result[k] = v
        return result
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=pairs,
                         parse_constant=lambda s: (_ for _ in ()).throw(KernelError(f"非有限数字: {s}")))

def _shape(value, spec, path):
    types = {"object":dict,"array":list,"string":str,"boolean":bool,
             "number":(int,float),"integer":int,"null":type(None)}
    ts = spec.get("type")
    if ts:
        ts = ts if isinstance(ts,list) else [ts]
        valid = any(isinstance(value, types[t]) and not (t in ("number","integer") and isinstance(value,bool)) for t in ts)
        if not valid:
            raise KernelError(f"{path}: 类型应为 {ts}")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if not math.isfinite(value):
            raise KernelError(f"{path}: 数值必须有限")
        if value < spec.get("minimum",-math.inf) or value > spec.get("maximum",math.inf):
            raise KernelError(f"{path}: 超出取值范围")
    if "const" in spec and (type(value) is not type(spec["const"]) or value != spec["const"]):
        raise KernelError(f"{path}: 应为 {spec['const']!r}")
    if "enum" in spec and value not in spec["enum"]:
        raise KernelError(f"{path}: 未知枚举 {value!r}")
    if isinstance(value,str) and len(value.strip()) < spec.get("minLength",0):
        raise KernelError(f"{path}: 必填字符串为空")
    if isinstance(value,dict):
        for key in spec.get("required",[]):
            if key not in value:
                raise KernelError(f"{path}/{key}: 缺少必填字段")
        for key, item in value.items():
            child = spec.get("properties",{}).get(key, spec.get("additionalProperties",{}))
            if child is False:
                raise KernelError(f"{path}/{key}: 未知字段（不接受个人数据或重复派生字段）")
            if isinstance(child,dict):
                _shape(item,child,f"{path}/{key}")
    if isinstance(value,list) and "items" in spec:
        for i,item in enumerate(value):
            _shape(item,spec["items"],f"{path}/{i}")

def moment(value):
    try:
        d = datetime.fromisoformat(value.replace("Z","+00:00"))
    except (ValueError,AttributeError) as e:
        raise KernelError(f"无效ISO时间: {value!r}") from e
    if d.tzinfo is None:
        raise KernelError(f"时间必须包含UTC偏移: {value}")
    return d


def digest(value):
    from hashlib import sha256
    return sha256(canonical(value).encode()).hexdigest()
