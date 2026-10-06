from .common import *
from .rule_base import RuleModule

class Refund(RuleModule):
    display_name='退票规则'
    category='Rules'
    description='退票窗口与手续费率'
    module_id='ticketing.refund'
    content_schema=obj(dict(coverage_start=S,coverage_end=S,windows=arr(obj(dict(start=S,end=S,fee_rate=RATE)))))
    def applicability(self,r,c,ck,at):
        p=r['content']
        lo,hi=ck.time(p['coverage_start'],at('content','coverage_start')),ck.time(p['coverage_end'],at('content','coverage_end'))
        windows=[]
        for j,w in enumerate(p['windows']):
            a,b=ck.time(w['start'],at('content','windows',j,'start')),ck.time(w['end'],at('content','windows',j,'end'))
            if a and b:windows.append((a,b,j))
        if lo is None or hi is None or len(windows)!=len(p['windows']):return
        ok=ck(lo<hi,'REFUND_COVERAGE_EMPTY',at('content','coverage_end'),'退款覆盖期不能为空或倒置',f'> {p["coverage_start"]}',p['coverage_end'])
        ok&=ck(bool(windows),'REFUND_NO_WINDOWS',at('content','windows'),'退款窗口不能为空')
        cursor=lo
        for a,b,j in sorted(windows):
            ok&=ck(a==cursor,'REFUND_WINDOW_GAP',at('content','windows',j,'start'),'退款窗口重叠或出现空档',cursor.isoformat(),p['windows'][j]['start'])
            ok&=ck(a<b<=hi,'REFUND_WINDOW_RANGE',at('content','windows',j,'end'),'退款窗口倒置或超出覆盖期',f'({p["windows"][j]["start"]}, {p["coverage_end"]}]',p['windows'][j]['end'])
            cursor=max(cursor,b)
        if windows:ok&=ck(cursor==hi,'REFUND_TAIL_GAP',at('content','coverage_end'),'最后一个退款窗口未到覆盖期末尾',p['coverage_end'],cursor.isoformat())
        fees=[D(w['fee_rate']) for w in sorted(p['windows'],key=lambda w:moment(w['start']))]
        if any(later<earlier for earlier,later in zip(fees,fees[1:])):
            ck(False,'REFUND_FEE_DECREASING',at('content','windows'),'退款手续费随时间下降，请确认窗口顺序和费率没有填反',
               '退款手续费随临近赛事不降低',[str(f) for f in fees],'WARNING')
        if ok:self.cover(r,lo,hi,ck,at)
