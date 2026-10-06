from decimal import Decimal
from ...models.core import moment
from ..gate import approved

def check(data,g,start,end,releasing,sessions,seatmap,year):
    for p in data['prices']:
        src=f"prices/{p['session_id']}/{p['tier']}"
        if p['price']<0:g.add('Q009','BLOCK',src+'/price','非负价格',p['price'])
        if Decimal(str(p['price'])).quantize(Decimal('.01'))!=Decimal(str(p['price'])):
            g.add('Q009','BLOCK',src+'/price','票价最多2位小数',p['price'])
        if p['price_version']!=data['price_version']:
            g.add('Q027','BLOCK',src+'/price_version',data['price_version'],p['price_version'])
        if (p['status'] in ('APPROVED','PUBLISHED') or releasing or data['status']=='APPROVED') and not approved(p):
            g.add('Q016','BLOCK',src,'有效批准状态且有approval_ref',dict(status=p['status'],approval_ref=p['approval_ref']))
        if moment(p['valid_from'])>moment(sessions[p['session_id']]['start_time']):
            g.add('Q012','BLOCK',src+'/valid_from','不晚于该场开始',p['valid_from'])
