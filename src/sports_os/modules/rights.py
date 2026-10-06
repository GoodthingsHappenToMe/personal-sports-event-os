from .common import *

class Rights(RowsModule):
    display_name='付费权益 Rights'
    category='Ticketing'
    description='付费权益的数量、结算方式和履约率'
    module_id='ticketing.rights'
    module_version='1.1.1'
    schema_version='2'
    requires_capabilities=('capacity','prices')
    provides=('rights',)
    identity=('session_id','zone_id','tier')
    row_schema=obj(dict(session_id=S,zone_id=S,tier=S,quantity=I,billing_basis={'enum':['ALLOCATED','REDEEMED']},
        strategy={'enum':['FACE_VALUE','FIXED_PRICE','DISCOUNT_RATE']},value=N,
        expected_fulfillment={'type':'object','additionalProperties':RATE}))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g);pools=c.provider('capacity')
        for i,r in enumerate(self.rows(c)):
            at=ck.row(i);key=pool_key(r)
            if ck(key in pools,'RIGHTS_UNKNOWN_POOL',at('zone_id'),'权益引用不存在的座区池','已有容量池',list(key)):
                ck(r['quantity']<=pools[key]['sellable_capacity'],'RIGHTS_EXCEED_SELLABLE',at('quantity'),'权益数量超过可售池',
                   f"<= {pools[key]['sellable_capacity']}",r['quantity'])
            ck(r['strategy']!='DISCOUNT_RATE' or r['value']<=1,'RIGHTS_DISCOUNT_RANGE',at('value'),'DISCOUNT_RATE表示实付比例，必须0到1','0..1',r['value'])
            ck(r['strategy']!='FIXED_PRICE' or D(r['value'])==D(money(D(r['value']))),'RIGHTS_PRICE_PRECISION',at('value'),
               'FIXED_PRICE单价最多两位小数','最多2位小数',r['value'])
            ck(r['strategy']!='FACE_VALUE' or D(r['value'])==1,'RIGHTS_FACE_VALUE',at('value'),
               'FACE_VALUE按面值结算，value必须为1（其他取值会被静默忽略）',1,r['value'])
            ck(bool(r['expected_fulfillment']),'RIGHTS_NO_SCENARIOS',at('expected_fulfillment'),'权益履约情景不可缺失')

    def calculate(self,c):
        pools=c.provider('capacity');prices=c.provider('prices');result={}
        for r in self.rows(c):
            key=pool_key(r);face=prices[price_key(pools[key])]
            if r['strategy']=='FACE_VALUE':effective=face
            elif r['strategy']=='FIXED_PRICE':effective=D(r['value'])
            else:effective=face*D(r['value'])
            result[key]=dict(quantity=r['quantity'],effective_unit_price=effective,billing_basis=r['billing_basis'],
                             expected_fulfillment={k:D(v) for k,v in r['expected_fulfillment'].items()})
        return result

    def migrate(self,old_version,old_schema,payload):
        require((old_version,old_schema)==('1.1.0','1'),'不支持的Rights迁移')
        for row in payload['rows']:row['billing_basis']='REDEEMED'
        return payload
