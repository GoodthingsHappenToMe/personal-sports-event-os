from .common import *

class Schedule(RowsModule):
    display_name='赛程 Schedule'
    category='Core'
    description='场次、阶段、起止时间与可选销售期'
    module_id='core.schedule'
    module_version='1.1.1'
    schema_version='2'
    optional_capabilities=('venues',)
    provides=('schedule',)
    identity=('session_id',)
    row_schema=obj(dict(session_id=S,event_id=S,stage=S,start_time=S,end_time=S,venue_id=NULL_S),optional=('venue_id',))

    def schema(self):
        return obj(dict(rows=arr(self.row_schema),sales_start=S,sales_end=S),optional=('sales_start','sales_end'))

    def validate(self,c,g):
        ck=self.checks(g);rows=self.rows(c);ck.unique(rows,self.key)
        project_id=c.project.manifest['project']['id'];ends=[]
        for i,s in enumerate(rows):
            at=ck.row(i)
            ck(s['event_id']==project_id,'SCHEDULE_EVENT_ID',at('event_id'),'场次event_id不属于项目',project_id,s['event_id'])
            start,end=ck.time(s['start_time'],at('start_time')),ck.time(s['end_time'],at('end_time'))
            if start and end:
                ck(end>start,'SCHEDULE_END_BEFORE_START',at('end_time'),'结束早于开始',f'> {s["start_time"]}',s['end_time'])
            if end:ends.append(end)
        p=c.payload(self.module_id)
        if not ck(('sales_start' in p)==('sales_end' in p),'SCHEDULE_SALES_INCOMPLETE',ck.where('sales_start'),'销售期需要完整起止',
                  'sales_start与sales_end同时存在或同时缺省',sorted(k for k in ('sales_start','sales_end') if k in p)):return
        if 'sales_start' not in p:return
        lo,hi=ck.time(p['sales_start'],ck.where('sales_start')),ck.time(p['sales_end'],ck.where('sales_end'))
        if lo and hi:
            ck(lo<hi,'SCHEDULE_SALES_EMPTY',ck.where('sales_end'),'销售期须非空',f'> {p["sales_start"]}',p['sales_end'])
            ck(bool(rows),'SCHEDULE_SALES_WITHOUT_SESSIONS',ck.where('rows'),'有销售期时必须至少有一个场次')
            if ends:ck(hi<=max(ends),'SCHEDULE_SALES_AFTER_LAST_SESSION',ck.where('sales_end'),'销售期不晚于末场结束',
                       max(ends).isoformat(),p['sales_end'])

    def calculate(self,c):
        p=c.payload(self.module_id);rows=unique(p['rows'],lambda s:s['session_id'])
        return dict(sessions=rows,start=min((moment(s['start_time']) for s in rows.values()),default=None),
                    end=max((moment(s['end_time']) for s in rows.values()),default=None),
                    sales_start=moment(p['sales_start']) if 'sales_start' in p else None,
                    sales_end=moment(p['sales_end']) if 'sales_end' in p else None)

    def cross_validate(self,c,g):
        ck=self.checks(g);venues=c.provider('venues',required=False)
        for i,row in enumerate(self.rows(c)):
            if row.get('venue_id') is not None:
                ck(venues is not None and row['venue_id'] in venues,'SCHEDULE_UNKNOWN_VENUE',ck.row(i)('venue_id'),
                   '场次引用不存在的venue；须启用有效venues提供者',sorted(venues or {}),row['venue_id'])

    def migrate(self,old_version,old_schema,payload):
        require((old_version,old_schema)==('1.1.0','1'),'不支持的Schedule迁移')
        return payload
