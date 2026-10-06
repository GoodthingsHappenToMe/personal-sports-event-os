from pathlib import Path
from hashlib import sha256
import json
import os
import tempfile
import shutil
from ..revenue import calculate
from ..versioning.snapshot import verify_snapshot,require_gate,ReleaseBlocked

def render_gate(result):
    lines=[f'# Quality Gate: {result.status}','',
           '|rule_id|severity|message|source|expected|actual|suggested_action|',
           '|---|---|---|---|---|---|---|']
    for f in result.to_dict()['findings']:
        values=[str(v).replace('|','／').replace('\n',' ') for v in f.values()]
        lines.append('|'+ '|'.join(values)+'|')
    return '\n'.join(lines)+'\n'

def render_revenue(result,formal=False):
    lines=['# Revenue Model — '+('APPROVED SYNTHETIC SNAPSHOT' if formal else 'PREVIEW / NOT RELEASED'),'',
           '> 完全虚构数据。DEMO_CURRENCY为演示金额单位，不是实际票款、结算或利润。','',
           f"snapshot_id: {result['snapshot_id']}",f"data_version: {result['data_version']}",
           f"price_version: {result['price_version']}",f"rules_version: {result['rules_version']}",'',
           '|范围|满售容量收入|高情景|中情景|低情景|中情景平均票价|可售率|',
           '|---|---:|---:|---:|---:|---:|---:|']
    def row(name,r):
        rate=f"{float(r['sellable_rate'])*100:.2f}%" if r['sellable_rate'] is not None else 'N/A'
        return f"|{name}|{r['full_revenue']}|{r['high']['revenue']}|{r['mid']['revenue']}|{r['low']['revenue']}|{r['mid']['average_price']}|{rate}|"
    lines.append(row('TOTAL',result['totals']))
    for group in ('by_stage','by_tier'):
        for key,r in result[group].items():lines.append(row(group+'/'+key,r))
    lines+=['','## 敏感性（不等于需求预测）','']
    for key,s in result['sensitivity'].items():lines.append(f"- {key}：中情景 {s['mid_revenue']}；变化 {s['delta']}；{s['assumption']}")
    lines+=['','## 产品占票','', '|产品|类型|每份占票张数|门票面值|产品售价|票外金额／折扣|','|---|---|---:|---:|---:|---:|']
    for p in result['products']:
        lines.append(f"|{p['product_id']}|{p['product_type']}|{p['ticket_quantity']}|{p['ticket_face_value']}|{p['price']}|{p['non_ticket_or_discount']}|")
    lines+=['','## 口径','']+['- '+n for n in result['notes']]
    return '\n'.join(lines)+'\n'

def export_release(record,root):
    verify_snapshot(record)
    gate=require_gate(record['data'],record['warnings_acknowledged'])
    result=calculate(record['data'])
    files={'snapshot.json':json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+'\n',
           'revenue.json':json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',
           'REVENUE.md':render_revenue(result,formal=True),
           'QUALITY_GATE.json':json.dumps(gate.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n'}
    manifest=dict(snapshot_id=record['snapshot_id'],data_version=record['data_version'],
                  rules_version=record['rules_version'],price_version=record['price_version'],
                  files={name:sha256(text.encode()).hexdigest() for name,text in files.items()})
    files['manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    root=Path(root);target=root/record['snapshot_id']
    if target.exists():
        if any(not (target/name).is_file() or (target/name).read_text(encoding='utf-8')!=text for name,text in files.items()):
            raise ReleaseBlocked('BLOCK：已存在发布目录与快照不符；不覆盖')
        return target
    # Validate everything before creating any release artifact.
    root.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.staging-',dir=root))
    try:
        for name,text in files.items():(temp/name).write_text(text,encoding='utf-8')
        os.rename(temp,target)
    finally:
        if temp.exists():shutil.rmtree(temp)
    return target
