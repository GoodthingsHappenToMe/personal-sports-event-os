from .common import *

HOLDS=('functional_hold','broadcast_hold','free_rights','other_hold')
def sellable(row):return row['physical_capacity']-sum(row[k] for k in HOLDS)

class Seating(RowsModule):
    display_name='座席 Seating'
    category='Ticketing'
    description='各场次座区物理容量、扣减与可售容量'
    module_id='ticketing.seating'
    requires_capabilities=('schedule','prices')
    provides=('capacity',)
    identity=('session_id','zone_id','tier')
    row_schema=obj(dict(session_id=S,zone_id=S,tier=S,price_class_id=S,physical_capacity=I,
        visibility={'enum':['CLEAR','RESTRICTED']},**{k:I for k in HOLDS},deduction_refs=obj({k:arr(S) for k in HOLDS})))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        sessions=c.provider('schedule')['sessions'];prices=c.provider('prices')
        for i,r in enumerate(self.rows(c)):
            at=ck.row(i)
            if ck(r['session_id'] in sessions,'SEAT_UNKNOWN_SESSION',at('session_id'),'座席引用不存在的场次',sorted(sessions),r['session_id']):
                ck(price_key(r) in prices,'SEAT_UNKNOWN_PRICE_CLASS',at('price_class_id'),'该场次没有此price_class的票价',
                   sorted(k[1] for k in prices if k[0]==r['session_id']),r['price_class_id'])
            holds=sum(r[k] for k in HOLDS)
            ck(holds<=r['physical_capacity'],'SEAT_HOLDS_EXCEED_CAPACITY',at('physical_capacity'),'扣减合计超过物理容量，可售为负',
               f'>= {holds}',r['physical_capacity'])
            refs=[x for v in r['deduction_refs'].values() for x in v]
            ck(len(refs)==len(set(refs)),'SEAT_DUPLICATE_DEDUCTION_REF',at('deduction_refs'),'同一扣减来源被重复引用',
               '每个来源只引用一次',sorted({x for x in refs if refs.count(x)>1}))
            for k in HOLDS:
                ck(not r[k] or r['deduction_refs'][k],'SEAT_HOLD_WITHOUT_SOURCE',at('deduction_refs',k),f'{k}为正数但缺少扣减来源',
                   '至少一个来源引用',r[k])

    def calculate(self,c):
        return {pool_key(r):dict(r,sellable_capacity=sellable(r)) for r in self.rows(c)}

    def canonical_row(self,row):return dict(row,sellable_capacity=sellable(row))
