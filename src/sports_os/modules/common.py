"""Shared module utilities, not a central business schema or dispatcher."""
from decimal import Decimal, ROUND_HALF_UP
from ..kernel.contract import Module
from ..kernel.data import KernelError, moment
from ..kernel.diff import changes

S={'type':'string','minLength':1}
I={'type':'integer','minimum':0,'maximum':10**12}
N={'type':'number','minimum':0,'maximum':10**12}
RATE={'type':'number','minimum':0,'maximum':1}
BOOL={'type':'boolean'}
NULL_S={'type':['string','null']}
D=lambda x:Decimal(str(x))
ZERO=Decimal(0)

def obj(properties,optional=()):
    return dict(type='object',properties=properties,required=[k for k in properties if k not in optional],additionalProperties=False)

def arr(items):return dict(type='array',items=items)
def money(value):return format(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')
def pool_key(row):return (row['session_id'],row['zone_id'],row['tier'])
def price_key(row):return (row['session_id'],row['price_class_id'])

def unique(rows,key):
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)):raise KernelError('重复业务键')
    return dict(zip(keys,rows))

def require(condition,message):
    """Raise for calculation-time invariants. Validation should use Checks so every problem is reported."""
    if not condition:raise KernelError(message)


class Checks:
    """Collects findings instead of stopping at the first failure.

    Sources use the editor's field paths (``module/rows/3/price``) so the desktop app can focus the field.
    Every call returns whether the condition held, so dependent checks can be skipped without raising.
    """
    def __init__(self,gate,module_id):
        self.gate=gate;self.module_id=module_id

    def where(self,*parts):
        return '/'.join([self.module_id,*(str(p) for p in parts)])

    def row(self,index,collection='rows'):
        """Field-path builder for one row: ``at=ck.row(3); at('price')``."""
        def at(*fields):return self.where(collection,index,*fields)
        return at

    def __call__(self,ok,rule,source,message,expected=None,actual=None,severity='BLOCK'):
        if not ok:self.gate.add(rule,source,message if expected is None else expected,actual,message,severity)
        return bool(ok)

    def time(self,value,source,rule='INVALID_TIME'):
        try:return moment(value)
        except KernelError as e:
            self.gate.add(rule,source,'带UTC偏移的ISO 8601时间',value,str(e))
            return None

    def unique(self,rows,key,collection='rows',rule='DUPLICATE_KEY'):
        """Report every duplicate business key; return the first row for each key."""
        seen={}
        for i,row in enumerate(rows):
            k=key(row)
            if k in seen:
                self.gate.add(rule,self.where(collection,i),'业务键唯一',list(k) if isinstance(k,tuple) else k,
                              f'与第{seen[k]+1}行业务键重复')
            else:seen[k]=i
        return {k:rows[i] for k,i in seen.items()}

class RowsModule(Module):
    row_schema=None
    identity=()

    def schema(self):return obj({'rows':arr(self.row_schema)})
    def rows(self,context):return context.payload(self.module_id)['rows']
    def key(self,row):return tuple(row[k] for k in self.identity)
    def checks(self,gate):return Checks(gate,self.module_id)
    def validate(self,context,gate):self.checks(gate).unique(self.rows(context),self.key)
    def canonical_row(self,row):return row
    def diff(self,old,new):
        def keyed(payload):return {'/'.join(map(str,self.key(r))):self.canonical_row(r) for r in payload['rows']}
        return changes(keyed(old),keyed(new))
    def export(self,context):return context.payload(self.module_id)


def strip_lifecycle(payload,fields):
    """Migration helper: approval lives only in ModuleState, never inside business rows."""
    for row in payload['rows']:
        for field in fields:row.pop(field,None)
    return payload
