from .common import *

LIFECYCLE=('price_version','status','approval_ref')


class Pricing(RowsModule):
    display_name='票价 Pricing'
    category='Ticketing'
    description='每个场次和价格类别的票价'
    module_id='ticketing.pricing'
    module_version='1.2.0'
    schema_version='2'
    requires_capabilities=('schedule',)
    provides=('prices',)
    identity=('session_id','price_class_id')
    # Approval and data_version live only in ModuleState; rows carry business facts only.
    row_schema=obj(dict(session_id=S,price_class_id=S,price=N,valid_from=S))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g);sessions=c.provider('schedule')['sessions']
        for i,r in enumerate(self.rows(c)):
            at=ck.row(i)
            ck(D(r['price'])==D(money(D(r['price']))),'PRICE_PRECISION',at('price'),'票价最多两位小数','最多2位小数',r['price'])
            start=ck.time(r['valid_from'],at('valid_from'))
            if not ck(r['session_id'] in sessions,'PRICE_UNKNOWN_SESSION',at('session_id'),'价格场次外键不存在',sorted(sessions),r['session_id']):continue
            if start:
                session_start=sessions[r['session_id']]['start_time']
                ck(start<=moment(session_start),'PRICE_STARTS_AFTER_SESSION',at('valid_from'),'价格开始晚于场次',f'<= {session_start}',r['valid_from'])

    def calculate(self,c):return {price_key(r):D(r['price']) for r in self.rows(c)}

    def migrate(self,old_version,old_schema,payload):
        require((old_version,old_schema)==('1.1.0','1'),'不支持的Pricing迁移')
        return strip_lifecycle(payload,LIFECYCLE)
