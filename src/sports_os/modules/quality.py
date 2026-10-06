"""Optional declaration checks. Only supplied contracts are checked, never inferred."""
from collections import defaultdict
import re
from .common import *

class QualityDeclarations(Module):
    display_name='质量声明'
    category='Core'
    description='人工声明的合计、单位、文档和指标，供质量检查核对'
    module_id='quality.declarations'
    requires_capabilities=('schedule',)
    optional_dependencies=('finance.revenue',)
    def schema(self):
        return obj(dict(
          cells=arr(obj(dict(source=S,value={'type':['string','number','null']}))),
          totals=arr(obj(dict(source=S,components=arr({'type':'number'}),declared={'type':'number'}))),
          summaries=arr(obj(dict(source=S,metric=S,value={'type':'number'},mode={'enum':['FORMULA','HARDCODED']}))),
          percentages=arr(obj(dict(source=S,values=arr(RATE),expected=RATE))),
          metrics=arr(obj(dict(metric_id=S,unit=S,source=S))),
          documents=arr(obj(dict(source=S,text={'type':'string'},critical=BOOL))),
          named_models=arr(obj(dict(name=S,content={'type':'string'},source=S))),
          output_refs=arr(obj(dict(source=S,snapshot_id=S)))))
    def validate(self,c,g):
        p=c.payload(self.module_id);schedule=c.provider('schedule')
        from zoneinfo import ZoneInfo
        years={moment(s['start_time']).astimezone(ZoneInfo(c.project.manifest['project']['timezone'])).year for s in schedule['sessions'].values()}
        for r in p['cells']:
            v=r['value']
            if isinstance(v,str) and re.search(r'#REF!|#DIV/0!|#VALUE!|#NAME\?|#N/A|#NUM!|#NULL!',v):g.add('Q002',r['source'],'无公式错误',v)
            if v is None or isinstance(v,str) and not v.strip():g.add('Q003',r['source'],'必填引用非空',v)
        for r in p['totals']:
            total=sum((D(x) for x in r['components']),ZERO)
            if total!=D(r['declared']):g.add('Q005',r['source'],str(total),r['declared'])
        for r in p['percentages']:
            total=sum((D(x) for x in r['values']),ZERO)
            if total!=D(r['expected']):g.add('Q006',r['source'],r['expected'],str(total))
        units=defaultdict(set);named=defaultdict(set)
        for r in p['metrics']:units[r['metric_id']].add(r['unit'])
        for k,v in units.items():
            if len(v)>1:g.add('Q007',k,'同指标同单位',sorted(v),'订单/票张/份/人数不能混用',severity='WARNING')
        for r in p['documents']:
            found={int(x) for x in re.findall(r'(?<!\d)(20\d{2})(?=年|\b)',r['text'])}
            if found-years:g.add('Q011',r['source'],sorted(years),sorted(found-years),'非本届年度',severity='BLOCK' if r['critical'] else 'WARNING')
            if re.search(r'最终|正式|\bFINAL\b',r['text'],re.I) and c.project.manifest['project']['status']=='DRAFT':g.add('Q017',r['source'],'人工批准','DRAFT')
        for r in p['named_models']:named[r['name']].add(r['content'])
        for k,v in named.items():
            if len(v)>1:g.add('Q018',k,'同名模型一致或明确版本',len(v))
        # Working-state declarations cannot claim a release snapshot. Frozen artifacts derive IDs themselves.
        for r in p['output_refs']:g.add('Q020',r['source'],'快照引用由冻结输出生成，工作态不可手填',r['snapshot_id'])
    def cross_validate(self,c,g):
        for r in c.payload(self.module_id)['summaries']:
            try:
                result=c.calculate('finance.revenue')
                for key in r['metric'].split('.'):result=result[key]
                expected=D(result)
            except (ValueError,KeyError,TypeError,ArithmeticError):
                g.add('Q003',r['source'],'有效且启用的派生指标',r['metric']);continue
            if expected!=D(r['value']):g.add('Q004',r['source'],str(expected),r['value'])
            elif r['mode']=='HARDCODED':g.add('Q004',r['source'],'公式输出',r['value'],'硬编码虽然目前一致仍需审核',severity='WARNING')
    def diff(self,a,b):return changes(a,b)
