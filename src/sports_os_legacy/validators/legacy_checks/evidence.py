from collections import defaultdict
from decimal import Decimal, InvalidOperation
import re
from ...models import ModelError
from ...revenue import calculate
from ..gate import approved

def check(data,g,start,end,releasing,sessions,seatmap,year):
    evidence=data['quality_evidence']
    for cell in evidence['cells']:
        v=cell['value']
        if isinstance(v,str) and re.search(r'#REF!|#DIV/0!|#VALUE!|#NAME\?|#N/A|#NUM!|#NULL!',v):
            g.add('Q002','BLOCK',cell['source'],'无Excel错误',v)
        if v is None or (isinstance(v,str) and not v.strip()):g.add('Q003','BLOCK',cell['source'],'所声明必填引用非空',v)
    for check in evidence['totals']:
        expected=sum(Decimal(str(v)) for v in check['components'])
        if expected!=Decimal(str(check['declared'])):g.add('Q005','BLOCK',check['source'],str(expected),check['declared'])
    for check in evidence['percentages']:
        total=sum(Decimal(str(v)) for v in check['values'])
        if total!=Decimal(str(check['expected'])):g.add('Q006','BLOCK',check['source'],check['expected'],str(total))
    units=defaultdict(set)
    for m in evidence['metrics']:units[m['metric_id']].add(m['unit'])
    for m in evidence['metrics']:
        if len(units[m['metric_id']])>1:g.add('Q007','WARNING',m['source'],'同一metric_id只有一种单位',sorted(units[m['metric_id']]),'订单／票张／份／人数不能互换')
    for doc in evidence['documents']:
        years=set(re.findall(r'(?<!\d)(20\d{2})(?=年|\b)',doc['text']))
        old=sorted(y for y in years if int(y)!=year)
        if old:g.add('Q011','BLOCK' if doc['critical'] else 'WARNING',doc['source'],year,old,'发现非本届年度；历史比较文本可标非关键但仍需审核')
        if re.search(r'最终|正式|\bFINAL\b',doc['text'],re.I) and not approved(data):
            g.add('Q017','BLOCK',doc['source'],'正式/最终标签需要批准',data['status'])
    named=defaultdict(set)
    for n in evidence['named_models']:named[n['name']].add(n['content'])
    for n in evidence['named_models']:
        if len(named[n['name']])>1:g.add('Q018','BLOCK',n['source'],'同名指向相同内容或有明确版本ID',n['name'])
    for ref in evidence['output_refs']:
        if ref['snapshot_id']!=data['snapshot_id'] or data['snapshot_id'] is None:
            g.add('Q020','BLOCK',ref['source'],data['snapshot_id'],ref['snapshot_id'])
    if evidence['summaries']:
        try:
            result=calculate(data)
            for c in evidence['summaries']:
                v=result
                try:
                    for key in c['metric'].split('.'):v=v[key]
                    expected=Decimal(str(v))
                except (KeyError,TypeError,ValueError,InvalidOperation):
                    g.add('Q003','BLOCK',c['source'],'可解析的派生指标路径',c['metric']);continue
                if expected!=Decimal(str(c['value'])):g.add('Q004','BLOCK',c['source'],str(expected),c['value'])
                elif c['mode']=='HARDCODED':g.add('Q004','WARNING',c['source'],'用派生值输出而非手抄',c['value'],'当前数值相符，但硬编码摘要会失去联动')
        except ModelError as e:g.add('Q004','BLOCK','quality_evidence/summaries','可计算模型',str(e))
