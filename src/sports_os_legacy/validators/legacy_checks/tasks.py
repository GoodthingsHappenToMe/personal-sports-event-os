from ...models.core import moment

def check(data,g,start,end,releasing,sessions,seatmap,year):
    for t in data['tasks']:
        if t['phase']=='PRE_EVENT' and moment(t['due_at'])>=start:
            g.add('Q013','BLOCK',f"tasks/{t['task_id']}",'赛前准备截止早于赛事首场',t['due_at'])
        if t['phase']=='POST_EVENT' and moment(t['due_at'])<end:
            g.add('Q013','BLOCK',f"tasks/{t['task_id']}",'赛后任务不早于赛事结束',t['due_at'])
        if t['status']=='DONE' and not (t['proof'] and t['proof'].strip()):
            g.add('Q028','BLOCK',f"tasks/{t['task_id']}/proof",'非空完成证据',t['proof'])
