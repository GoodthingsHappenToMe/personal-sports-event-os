from decimal import Decimal
from datetime import timedelta
from ...models import ModelError
from ...models.core import moment,_shape
from ..gate import approved,CONTENT_SCHEMAS

def check(data,g,start,end,releasing,sessions,seatmap,year):
    for r in data['rules']:
        src=f"rules/{r['rule_id']}";c=r['content']
        if r['version']!=data['rules_version']:
            g.add('Q027','BLOCK',src+'/version',data['rules_version'],r['version'])
        if r['status'] in ('APPROVED','PUBLISHED') and not approved(r):
            g.add('Q016','BLOCK',src,'批准凭证非空',r['approval_ref'])
        if (releasing or data['status']=='APPROVED') and not approved(r):
            g.add('Q019','BLOCK',src,'仅引用已批准规则',r['status'])
        if moment(r['valid_to'])<=moment(r['valid_from']):
            g.add('Q012','BLOCK',src,'valid_to > valid_from',[r['valid_from'],r['valid_to']])
        try:
            _shape(c,CONTENT_SCHEMAS[r['rule_type']],src+'/content')
            if r['rule_type']=='refund':
                lo,hi=moment(c['coverage_start']),moment(c['coverage_end'])
                windows=sorted([(moment(w['start']),moment(w['end'])) for w in c['windows']])
                if hi<=lo or not windows:raise ModelError('退款覆盖期必须非空且起点早于终点')
                cursor=lo
                for a,b in windows:
                    if b<=a:g.add('Q012','BLOCK',src+'/windows','end > start',[a.isoformat(),b.isoformat()])
                    if a<cursor:g.add('Q014','BLOCK',src+'/windows',cursor.isoformat(),a.isoformat(),'退款窗口重叠或超出覆盖起点')
                    if a>cursor:g.add('Q015','BLOCK',src+'/windows',cursor.isoformat(),a.isoformat(),'退款窗口存在空档')
                    if b>hi:g.add('Q014','BLOCK',src+'/windows',hi.isoformat(),b.isoformat(),'窗口超出声明覆盖终点')
                    cursor=max(cursor,b)
                if cursor<hi:g.add('Q015','BLOCK',src+'/windows',hi.isoformat(),cursor.isoformat(),'覆盖终点前存在空档')
                if lo<moment(r['valid_from']) or hi>moment(r['valid_to']):
                    g.add('Q012','BLOCK',src,'退款覆盖期位于规则有效期内',[c['coverage_start'],c['coverage_end']])
            sales_start=min(moment(p['valid_from']) for p in data['prices'])
            coverage={
                'identity':(sales_start,end), 'transfer':(sales_start,end),
                'rights_return':(sales_start,max(moment(s['start_time'])-timedelta(hours=c.get('hours_before',0)) for s in sessions.values())),
            }
            if r['rule_type'] in coverage:
                lo,hi=coverage[r['rule_type']]
                if moment(r['valid_from'])>lo or moment(r['valid_to'])<hi:
                    g.add('Q012','BLOCK',src,'规则覆盖实际业务期间',[lo.isoformat(),hi.isoformat()])
            if r['rule_type']=='launch':
                total=sum(Decimal(str(x['fraction'])) for x in c['rounds'])
                if total != Decimal(1):g.add('Q006','BLOCK',src+'/rounds',1,str(total),'各轮使用同一公开池分母，比例之和必须为1')
                times=[moment(x['at']) for x in c['rounds']]
                if times!=sorted(set(times)) or any(t>=start or t<sales_start or t<moment(r['valid_from']) or t>=moment(r['valid_to']) for t in times):
                    g.add('Q012','BLOCK',src+'/rounds','时点严格递增，且早于赛事开始',[x['at'] for x in c['rounds']])
        except (ModelError,KeyError,TypeError,ValueError) as e:
            g.add('Q029','BLOCK',src,'该规则类型的完整结构和有效时间',str(e))
