from collections import defaultdict
from ...models import sellable
from ...models.core import moment,seating_key

def check(data,g,start,end,releasing,sessions,seatmap,year):
    inventory=defaultdict(list)
    for inv in data['inventory']:inventory[seating_key(inv)].append(inv)
    for key,s in seatmap.items():
        pool=inventory[key];quantity=sum(r['quantity'] for r in pool);capacity=sellable(s)
        if quantity != capacity:
            g.add('Q024','BLOCK','inventory/'+'/'.join(key),capacity,quantity,'库存各互斥状态之和必须等于可售总池（不是物理总量）')
        if len({moment(r['as_of']) for r in pool})>1:
            g.add('Q024','BLOCK','inventory/'+'/'.join(key),'同一池使用同一as_of',[r['as_of'] for r in pool])
        reserved=sum(r['quantity'] for r in pool if r['allocation_type']=='PAID_RIGHTS')
        if any(r['status']=='PAID_RESERVED' and r['allocation_type']!='PAID_RIGHTS' for r in pool):
            g.add('Q024','BLOCK','inventory/'+'/'.join(key),'PAID_RESERVED必须属于PAID_RIGHTS','公共池误标付费预留')
        if reserved != s['paid_rights']:
            g.add('Q024','BLOCK','inventory/'+'/'.join(key)+'/PAID_RESERVED',s['paid_rights'],reserved)
