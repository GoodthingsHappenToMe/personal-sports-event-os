from .common import *
from .rule_base import RuleModule

class Transfer(RuleModule):
    display_name='转票规则'
    category='Rules'
    description='是否允许转票及适用期间'
    module_id='ticketing.transfer'
    content_schema=obj(dict(allowed=BOOL))
    def applicability(self,r,c,ck,at):
        self.cover_session_lifetime(r,c,ck,at)
