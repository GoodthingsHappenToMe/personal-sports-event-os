from datetime import timedelta
from .common import *
from .rule_base import RuleModule

class RightsReturn(RuleModule):
    display_name='权益回流规则'
    category='Rules'
    description='未使用权益在开赛前回流公开池的时点'
    module_id='ticketing.rights_return'
    content_schema=obj(dict(hours_before=I))
    def applicability(self,r,c,ck,at):
        schedule=self.scoped_schedule(r,c);rows=schedule['sessions'].values()
        deadlines=[moment(s['start_time'])-timedelta(hours=r['content']['hours_before']) for s in rows]
        if not ck(bool(deadlines),'RIGHTS_RETURN_NO_SESSIONS',at('scope'),'权益回流需要Scope内场次'):return
        if not ck(schedule['sales_start'] is not None,'RIGHTS_RETURN_NEEDS_SALES_START','core.schedule/sales_start','权益回流需要Schedule销售开始时间'):return
        ck(schedule['sales_start']<=min(deadlines),'RIGHTS_RETURN_DEADLINE_BEFORE_SALES',at('content','hours_before'),
           '登记开始不能晚于回流节点',f">= {schedule['sales_start'].isoformat()}",min(deadlines).isoformat())
        self.cover(r,schedule['sales_start'],max(deadlines),ck,at)
        ck(max(deadlines)<moment(r['valid_to']),'RIGHTS_RETURN_AFTER_VALIDITY',at('valid_to'),'回流节点必须落在半开有效区间内',
           f'> {max(deadlines).isoformat()}',r['valid_to'])
