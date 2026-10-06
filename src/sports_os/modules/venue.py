from .common import *

class Venue(RowsModule):
    display_name='场馆 Venue'
    category='Core'
    description='场馆及其IANA时区'
    module_id='core.venue'
    provides=('venues',)
    identity=('venue_id',)
    row_schema=obj(dict(venue_id=S,name=S,timezone=S))
    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        for i,r in enumerate(self.rows(c)):
            try:ZoneInfo(r['timezone']);valid=True
            except (ZoneInfoNotFoundError,ValueError):valid=False
            ck(valid,'VENUE_TIMEZONE',ck.row(i)('timezone'),'未知IANA时区','IANA时区名，例如Asia/Shanghai',r['timezone'])

    def calculate(self,c):return {r['venue_id']:r for r in self.rows(c)}
