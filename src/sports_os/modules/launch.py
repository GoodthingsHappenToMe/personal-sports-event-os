from .common import *
from .rule_base import RuleModule

class Launch(RuleModule):
    display_name='开票规则'
    category='Rules'
    description='分轮开票时间与各轮比例'
    module_id='ticketing.launch'
    content_schema=obj(dict(denominator={'const':'PUBLIC_POOL'},rounds=arr(obj(dict(at=S,fraction=RATE)))))
    def applicability(self,r,c,ck,at):
        rounds=r['content']['rounds'];s=self.scoped_schedule(r,c)
        times=[ck.time(x['at'],at('content','rounds',j,'at')) for j,x in enumerate(rounds)]
        if not ck(bool(rounds),'LAUNCH_NO_ROUNDS',at('content','rounds'),'开票规则至少需要一轮'):return
        total=sum((D(x['fraction']) for x in rounds),ZERO)
        ck(total==1,'LAUNCH_FRACTIONS_NOT_ONE',at('content','rounds'),'各轮比例必须合计为1',1,str(total))
        for j,x in enumerate(rounds):
            ck(D(x['fraction'])>0,'LAUNCH_ZERO_ROUND',at('content','rounds',j,'fraction'),'每轮开票比例必须大于0；不开票的轮次请删除','> 0',x['fraction'])
        if None in times:return
        ck(times==sorted(set(times)),'LAUNCH_ROUNDS_NOT_INCREASING',at('content','rounds'),'开票轮次时间必须严格递增','严格递增',[x['at'] for x in rounds])
        if not ck(s['sales_start'] is not None and s['sales_end'] is not None and s['start'] is not None,'LAUNCH_NEEDS_SALES_PERIOD',
                  'core.schedule/sales_start','开票需要Schedule销售期及Scope内场次'):return
        for j,t in enumerate(times):
            ck(s['sales_start']<=t<s['sales_end'] and t<s['start'],'LAUNCH_ROUND_OUT_OF_RANGE',at('content','rounds',j,'at'),
               '开票时点超出销售期或晚于首场',f"[{s['sales_start'].isoformat()}, min(sales_end, 首场))",rounds[j]['at'])
        self.cover(r,min(times),max(times),ck,at)
        ck(max(times)<moment(r['valid_to']),'LAUNCH_AFTER_VALIDITY',at('valid_to'),'开票时点必须在规则半开有效区间内',
           f'> {max(times).isoformat()}',r['valid_to'])
