from .common import *
from .rule_base import RuleModule

class Identity(RuleModule):
    display_name='实名规则'
    category='Rules'
    description='实名制要求及适用期间'
    module_id='ticketing.identity'
    content_schema=obj(dict(mode=S))
    def applicability(self,r,c,ck,at):
        self.cover_session_lifetime(r,c,ck,at)
