from .common import *

class Tasks(RowsModule):
    display_name='任务 Tasks'
    category='Project'
    description='赛前、赛中、赛后任务及其依赖与完成证据'
    module_id='project.tasks'
    optional_capabilities=('schedule',)
    identity=('task_id',)
    row_schema=obj(dict(task_id=S,title=S,owner_role=S,due_at=S,depends_on=arr(S),
        status={'enum':['TODO','DOING','DONE']},acceptance=S,proof=NULL_S,
        phase={'enum':['PRE_EVENT','DURING_EVENT','POST_EVENT']}))
    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g);rows=self.rows(c)
        index={t['task_id']:i for i,t in reversed(list(enumerate(rows)))}
        for i,t in enumerate(rows):
            at=ck.row(i);ck.time(t['due_at'],at('due_at'))
            for dep in t['depends_on']:
                ck(dep in index,'TASK_UNKNOWN_DEPENDENCY',at('depends_on'),'任务依赖不存在',sorted(index),dep)
            ck(t['status']!='DONE' or bool(t['proof'] and t['proof'].strip()),'TASK_DONE_WITHOUT_PROOF',at('proof'),'完成任务缺证据','非空proof',t['proof'])
        # Report each dependency cycle once, at the first task on the cycle.
        state={};reported=set()
        def visit(key,path):
            state[key]='active'
            for dep in rows[index[key]]['depends_on']:
                if dep not in index:continue
                if state.get(dep)=='active':
                    cycle=path[path.index(dep):]+[dep]
                    if frozenset(cycle) not in reported:
                        reported.add(frozenset(cycle))
                        ck(False,'TASK_DEPENDENCY_CYCLE',ck.row(index[dep])('depends_on'),'任务依赖循环','无循环',cycle)
                elif dep not in state:visit(dep,path+[dep])
            state[key]='done'
        for key in index:
            if key not in state:visit(key,[key])

    def cross_validate(self,c,g):
        s=c.provider('schedule',required=False)
        if s is None:return
        ck=self.checks(g)
        for i,t in enumerate(self.rows(c)):
            due=moment(t['due_at']);at=ck.row(i)('due_at')
            if t['phase']=='PRE_EVENT':
                ck(s['start'] is not None and due<s['start'],'TASK_PRE_EVENT_TOO_LATE',at,'赛前任务必须早于首场开始',
                   f"< {s['start'].isoformat() if s['start'] else '首场'}",t['due_at'])
            if t['phase']=='POST_EVENT':
                ck(s['end'] is not None and due>=s['end'],'TASK_POST_EVENT_TOO_EARLY',at,'赛后任务不得早于末场结束',
                   f">= {s['end'].isoformat() if s['end'] else '末场'}",t['due_at'])
