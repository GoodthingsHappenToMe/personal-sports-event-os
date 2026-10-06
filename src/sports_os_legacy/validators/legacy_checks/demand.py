
def check(data,g,start,end,releasing,sessions,seatmap,year):
    for seat in data['seating']:
        sid,tier=seat['session_id'],seat['tier']
        rates=[data['scenarios'][k]['session_rates'][sid]*data['scenarios'][k]['tier_rates'][tier] for k in ('low','mid','high')]
        if rates!=sorted(rates):g.add('Q026','BLOCK',f'scenarios/{sid}/{tier}','low <= mid <= high',rates)
    paid=[data['scenarios'][k]['paid_rights_rate'] for k in ('low','mid','high')]
    if paid!=sorted(paid):g.add('Q026','BLOCK','scenarios/paid_rights_rate','low <= mid <= high',paid)
