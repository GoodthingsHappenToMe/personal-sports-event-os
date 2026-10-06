from .common import *

class Decisions(RowsModule):
    display_name='决策 Decisions'
    category='Project'
    description='业务决策记录及其来源和影响的字段'
    module_id='project.decisions'
    identity=('decision_id',)
    row_schema=obj(dict(decision_id=S,issue=S,options=arr(S),decision=S,reason=S,
        approved_by_role=S,effective_at=S,source_ref=S,confirmed=BOOL,changed_paths=arr(S)))
    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        for i,row in enumerate(self.rows(c)):ck.time(row['effective_at'],ck.row(i)('effective_at'))
    def canonical_row(self,row):return dict(row,changed_paths=sorted(row['changed_paths']))
