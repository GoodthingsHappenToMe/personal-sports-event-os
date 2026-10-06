from .common import *

LIFECYCLE=('version','status','approval_ref')
SCOPE=obj(dict(type={'enum':['ALL','SESSION']},session_ids=arr(S)),optional=('session_ids',))

class RuleModule(RowsModule):
    module_version='1.2.0'
    schema_version='3'
    requires_capabilities=('schedule',)
    identity=('rule_id',)
    content_schema=None

    def schema(self):
        # Approval and data_version live only in ModuleState; rows carry business facts only.
        row=obj(dict(rule_id=S,scope=SCOPE,content=self.content_schema,valid_from=S,valid_to=S))
        return obj(dict(rows=arr(row)))

    def session_ids(self,r,c):
        available=set(c.provider('schedule')['sessions']);scope=r['scope']
        if scope['type']=='ALL':
            require('session_ids' not in scope,'ALL不得附加session_ids过滤器')
            return available
        ids=scope.get('session_ids',[])
        require(bool(ids) and len(ids)==len(set(ids)),'SESSION需要非空且唯一session_ids')
        require(set(ids)<=available,'Scope引用不存在的Session')
        return set(ids)

    def scoped_schedule(self,r,c):
        schedule=c.provider('schedule');ids=self.session_ids(r,c)
        sessions={k:v for k,v in schedule['sessions'].items() if k in ids}
        return dict(schedule,sessions=sessions,
                    start=min((moment(s['start_time']) for s in sessions.values()),default=None),
                    end=max((moment(s['end_time']) for s in sessions.values()),default=None))

    def check_scope(self,r,c,ck,at):
        """Validation-time scope check: report problems, return the scoped session IDs or None."""
        available=set(c.provider('schedule')['sessions']);scope=r['scope']
        if scope['type']=='ALL':
            return available if ck('session_ids' not in scope,'RULE_SCOPE_ALL_WITH_IDS',at('scope','session_ids'),
                                   'ALL不得附加session_ids过滤器','不填写session_ids',scope.get('session_ids')) else None
        ids=scope.get('session_ids',[])
        ok=ck(bool(ids),'RULE_SCOPE_EMPTY',at('scope','session_ids'),'SESSION需要非空session_ids','至少一个session_id',ids)
        ok&=ck(len(ids)==len(set(ids)),'RULE_SCOPE_DUPLICATE',at('scope','session_ids'),'session_ids不得重复','唯一',
               sorted({x for x in ids if ids.count(x)>1}))
        unknown=sorted(set(ids)-available)
        ok&=ck(not unknown,'RULE_SCOPE_UNKNOWN_SESSION',at('scope','session_ids'),'Scope引用不存在的Session',sorted(available),unknown)
        return set(ids) if ok else None

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g);rows=self.rows(c);intervals=[];ready=[]
        ck(bool(rows),'RULE_EMPTY',ck.where('rows'),'已启用规则模块需要至少一条明确规则')
        for i,r in enumerate(rows):
            at=ck.row(i)
            lo,hi=ck.time(r['valid_from'],at('valid_from')),ck.time(r['valid_to'],at('valid_to'))
            sessions=self.check_scope(r,c,ck,at)
            if lo is None or hi is None or sessions is None:continue
            if not ck(hi>lo,'RULE_VALIDITY_EMPTY',at('valid_to'),'规则有效期为空或倒置',f'> {r["valid_from"]}',r['valid_to']):continue
            for j,ids,a,b in intervals:
                overlap=sorted(sessions&ids)
                ck(not (overlap and max(lo,a)<min(hi,b)),'RULE_OVERLAP',at('valid_from'),
                   f'与第{j+1}行规则的Scope和有效期重叠，不能唯一决策','Session或有效期不重叠',overlap)
            intervals.append((i,sessions,lo,hi));ready.append((i,r))
        if len(ready)==len(rows):
            for i,r in ready:self.applicability(r,c,ck,ck.row(i))

    def applicability(self,r,c,ck,at):
        raise NotImplementedError('规则模块必须定义实际适用期间')

    def cover(self,r,lo,hi,ck,at):
        if not ck(lo is not None and hi is not None and lo<=hi,'RULE_PERIOD_INVALID',at('content'),'业务适用期间缺失或倒置',
                  'start<=end',[x.isoformat() if x else None for x in (lo,hi)]):return
        ck(moment(r['valid_from'])<=lo,'RULE_PERIOD_NOT_COVERED',at('valid_from'),'规则有效期必须覆盖实际业务期间开始',f'<= {lo.isoformat()}',r['valid_from'])
        ck(hi<=moment(r['valid_to']),'RULE_PERIOD_NOT_COVERED',at('valid_to'),'规则有效期必须覆盖实际业务期间结束',f'>= {hi.isoformat()}',r['valid_to'])

    def cover_session_lifetime(self,r,c,ck,at):
        """Adjacent rule versions may jointly cover each scoped session, without gaps."""
        schedule=self.scoped_schedule(r,c);lo=schedule['sales_start']
        if not ck(lo is not None,'RULE_NEEDS_SALES_START','core.schedule/sales_start','规则需要Schedule的销售开始时间'):return
        for sid,session in schedule['sessions'].items():
            end=moment(session['end_time']);cursor=lo
            if not ck(lo<=end,'RULE_SALES_AFTER_SESSION',at('scope'),f'销售开始晚于Scope内场次{sid}结束，规则业务期间倒置',
                      f'<= {session["end_time"]}',lo.isoformat()):continue
            intervals=sorted((moment(x['valid_from']),moment(x['valid_to'])) for x in self.rows(c) if sid in self.session_ids(x,c))
            for a,b in intervals:
                if b<=cursor:continue
                if a>cursor:break
                cursor=b
            ck(cursor>=end,'RULE_COVERAGE_GAP',at('valid_to'),f'规则有效期未连续覆盖场次{sid}的销售至结束期间',
               f'覆盖至 {session["end_time"]}',cursor.isoformat())

    def canonical_row(self,row):
        scope=row['scope']
        if scope['type']=='SESSION':scope=dict(scope,session_ids=sorted(scope['session_ids']))
        return dict(row,scope=scope)

    def migrate(self,old_version,old_schema,payload):
        require((old_version,old_schema) in (('1.1.0','1'),('1.1.1','2')),'不支持的Rule迁移')
        if old_schema=='1':
            for row in payload['rows']:row['scope']={'type':'ALL'}
        return strip_lifecycle(payload,LIFECYCLE)
