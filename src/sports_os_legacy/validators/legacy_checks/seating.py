from ...models import sellable
from ...models.core import seating_key
from ...models.schema import HOLD_FIELDS

def check(data,g,start,end,releasing,sessions,seatmap,year):
    for s in data['seating']:
        src='seating/'+'/'.join(seating_key(s));capacity=sellable(s)
        if capacity<0:g.add('Q008','BLOCK',src,'sellable_capacity >= 0',capacity)
        if capacity>s['physical_capacity'] or s['paid_rights']>capacity:
            g.add('Q009','BLOCK',src,'0 <= paid_rights <= sellable <= physical',dict(sellable=capacity,physical=s['physical_capacity'],paid=s['paid_rights']))
        policy=s.get('paid_rights_pricing')
        if policy and (policy['value']<0 or (policy['strategy']=='DISCOUNT_RATE' and policy['value']>1)):
            g.add('Q009','BLOCK',src+'/paid_rights_pricing','非负有效价/折扣率不超过1',policy)
        refs=[r for values in s['deduction_refs'].values() for r in values]
        if len(refs)!=len(set(refs)):
            g.add('Q010','BLOCK',src,'扣减来源ID在同一场次座区互斥',refs)
        for field in HOLD_FIELDS:
            if s[field]>0 and not s['deduction_refs'][field]:
                g.add('Q003','BLOCK',f'{src}/deduction_refs/{field}','正数扣减有来源ID',[])
