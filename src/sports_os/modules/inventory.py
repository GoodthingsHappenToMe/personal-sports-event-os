from collections import defaultdict
from .common import *

class Inventory(RowsModule):
    display_name='库存 Inventory'
    category='Ticketing'
    description='各容量池按状态和渠道划分的库存数量'
    module_id='ticketing.inventory'
    requires_capabilities=('capacity',)
    optional_capabilities=('rights',)
    identity=('inventory_id',)
    row_schema=obj(dict(inventory_id=S,session_id=S,zone_id=S,tier=S,channel=S,
        status={'enum':['AVAILABLE','SOLD','LOCKED','PAID_RESERVED']},
        allocation_type={'enum':['PUBLIC','PAID_RIGHTS']},quantity=I,as_of=S,source_ref=S))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        for i,r in enumerate(self.rows(c)):
            at=ck.row(i);ck.time(r['as_of'],at('as_of'))
            ck(r['status']!='PAID_RESERVED' or r['allocation_type']=='PAID_RIGHTS','INVENTORY_RESERVED_NOT_RIGHTS',at('allocation_type'),
               'PAID_RESERVED只能用于PAID_RIGHTS分配','PAID_RIGHTS',r['allocation_type'])

    def cross_validate(self,c,g):
        ck=self.checks(g);pools=c.provider('capacity');rights=c.provider('rights',required=False) or {};groups=defaultdict(list)
        for i,r in enumerate(self.rows(c)):
            if ck(pool_key(r) in pools,'INVENTORY_UNKNOWN_POOL',ck.row(i)('zone_id'),'库存引用不存在的座区池','已有容量池',list(pool_key(r))):
                groups[pool_key(r)].append((i,r))
        for key,pool in pools.items():
            rows=groups[key];label='/'.join(key)
            source=ck.row(rows[0][0])('quantity') if rows else ck.where('rows')
            total=sum(r['quantity'] for _,r in rows)
            ck(total==pool['sellable_capacity'],'INVENTORY_POOL_TOTAL',source,f'库存池{label}各状态合计不等于可售容量',
               pool['sellable_capacity'],total)
            ck(len({r['as_of'] for _,r in rows})<=1,'INVENTORY_AS_OF_MIXED',ck.row(rows[0][0])('as_of') if rows else source,
               f'库存池{label}的as_of必须一致',1,sorted({r['as_of'] for _,r in rows}))
            paid=sum(r['quantity'] for _,r in rows if r['allocation_type']=='PAID_RIGHTS');expected=rights.get(key,{}).get('quantity',0)
            ck(paid==expected,'INVENTORY_RIGHTS_MISMATCH',source,f'库存池{label}的PAID_RIGHTS数量与Rights不一致；禁用Rights不会自动转移库存',
               expected,paid)
