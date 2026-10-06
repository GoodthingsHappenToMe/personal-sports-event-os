from difflib import SequenceMatcher
import json
from ..models import assert_model, sellable
from ..models.core import price_key

MISSING='[不存在]'
LABELS={'price':'价格变化','seating':'座席变化','inventory':'库存规则／数量',
        'time':'时间变化','product':'产品变化','rule':'规则变化','text':'文字变化','metadata':'版本／其他字段'}

def _leaves(value,path):
    if isinstance(value,dict):
        out={}
        for key,v in sorted(value.items()):out.update(_leaves(v,path+'/'+key))
        return out
    if isinstance(value,list) and path.endswith(('/rounds','/windows')):
        out={}
        for i,v in enumerate(value):out.update(_leaves(v,path+'/'+str(i)))
        return out
    if isinstance(value,list) and path.endswith('/included_sessions'):
        value=sorted(value,key=lambda c:(c['session_id'],c['zone_id'],c['tier']))
    # Mappings use stable business identity, not array position.
    return {path:value}

def _reason(path,data):
    reasons=[]
    for decision in data.get('decisions',[]):
        if path not in decision['changed_paths']:continue
        confirmed=decision['confirmed'] and bool(decision['source_ref'].strip()) and bool(decision['approved_by_role'].strip())
        reasons.append(dict(kind='已确认原因（输入决定记录）' if confirmed else '推测原因（输入提供，未确认）',
                            reason=decision['reason'],source_ref=decision['source_ref'],decision_id=decision['decision_id']))
    return reasons or [dict(kind='无直接证据',reason='原因无法由输入直接确认',source_ref=None,decision_id=None)]

def compare(a,b,label_a=None,label_b=None):
    structured=isinstance(a,dict) and isinstance(b,dict)
    if not structured and not (isinstance(a,str) and isinstance(b,str)):
        raise ValueError('两端必须同为Event Master结构化数据，或同为文本')
    result=dict(version_a=label_a or (a['data_version'] if structured else 'TEXT A'),
                version_b=label_b or (b['data_version'] if structured else 'TEXT B'),changes=[],
                limitations=['本地确定性比较；不调用LLM、不推断动机。',
                             '已确认原因仅表示输入提供带来源的确认记录，不替代对批准真伪的人工核验。',
                             '文字替换可定位，但语义含义仍需人工确认；文本相同不证明图形或签章相同。'])
    def change(category,path,old,new):
        if old==new:return
        numeric=all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in (old,new))
        result['changes'].append(dict(category=category,path=path,old=old,new=new,
            fact_kind='数值变化' if numeric else '文件事实',
            reasons=_reason(path,b) if structured else [dict(kind='无直接证据',reason='原因无法由文本直接确认',source_ref=None,decision_id=None)]))
    if not structured:
        aa=a.splitlines();bb=b.splitlines()
        for tag,i,j,k,l in SequenceMatcher(None,aa,bb,autojunk=False).get_opcodes():
            span_a=f'行{i+1}-{j}' if i<j else f'空@插入点{i+1}'
            span_b=f'行{k+1}-{l}' if k<l else f'空@插入点{k+1}'
            if tag!='equal':change('text',f'{tag}:A{span_a}/B{span_b}',aa[i:j],bb[k:l])
        return result
    assert_model(a);assert_model(b)
    keys={
        'prices':lambda x:"/".join(price_key(x)),
        'seating':lambda x:f"{x['session_id']}/{x['zone_id']}/{x['tier']}",
        'inventory':lambda x:x['inventory_id'],'products':lambda x:x['product_id'],
        'rules':lambda x:x['rule_id'],'sessions':lambda x:x['session_id'],
        'tasks':lambda x:x['task_id'],
    }
    categories=dict(prices='price',seating='seating',inventory='inventory',products='product',rules='rule',sessions='time',tasks='time')
    for group,key in keys.items():
        def flat(data):
            out={}
            for r in data[group]:
                row=dict(r)
                if group=='prices' and row['price_version']==data['price_version']:row.pop('price_version')
                if group=='rules' and row['version']==data['rules_version']:row.pop('version')
                if group=='seating':row['sellable_capacity']=sellable(r)
                out.update(_leaves(row,group+'/'+key(r)))
            return out
        fa,fb=flat(a),flat(b)
        for path in sorted(set(fa)|set(fb)):
            category=categories[group]
            if path.endswith(('/price_version','/version','/approval_ref','/status')):category='metadata'
            if '/rounds' in path:category='time' if path.endswith('/at') else 'inventory'
            change(category,path,fa.get(path,MISSING),fb.get(path,MISSING))
    for key in ('event','data_version','rules_version','price_version','status','approval_ref','scenarios'):
        fa,fb=_leaves(a[key],key),_leaves(b[key],key)
        for path in sorted(set(fa)|set(fb)):
            change('metadata',path,fa.get(path,MISSING),fb.get(path,MISSING))
    # Text documents are matched by source rather than list position.
    docs_a={d['source']:d['text'] for d in a['quality_evidence']['documents']}
    docs_b={d['source']:d['text'] for d in b['quality_evidence']['documents']}
    for key in sorted(set(docs_a)|set(docs_b)):
        old,new=docs_a.get(key,''),docs_b.get(key,'')
        for c in compare(old,new)['changes']:
            change('text','documents/'+key+'/'+c['path'],c['old'],c['new'])
    return result

def render_diff(result):
    def val(v):return json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    lines=[f"# VERSION {result['version_a']} → {result['version_b']}",'']
    for category,label in LABELS.items():
        changes=[c for c in result['changes'] if c['category']==category]
        lines.extend([f'## 【{label}】',''])
        if not changes:lines.extend(['无变化。','']);continue
        for c in changes:
            action='新增' if c['old']==MISSING else '删除' if c['new']==MISSING else '修改'
            lines.append(f"- [{action}／{c['fact_kind']}] `{c['path']}`：{val(c['old'])} → {val(c['new'])}")
            for r in c['reasons']:
                source=f"；依据 {r['source_ref']} / {r['decision_id']}" if r['source_ref'] else ''
                lines.append(f"  - 【原因：{r['kind']}】{r['reason']}{source}")
        lines.append('')
    lines+=['## 证据边界','']+['- '+x for x in result['limitations']]
    return '\n'.join(lines)+'\n'
