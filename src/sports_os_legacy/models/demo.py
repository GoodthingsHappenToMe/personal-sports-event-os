"""All values below are invented; no company file is used as input."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from .core import sellable

def make_demo():
    start = datetime(2027,7,10,10,tzinfo=timezone.utc)
    d = dict(schema_version="1.0",data_version="demo-a",rules_version="rules-a",price_version="prices-a",
             status="APPROVED",approval_ref="SYNTHETIC-APPROVAL-A",snapshot_id=None,synthetic=True,
             event=dict(event_id="GRM-2027-FICTION",event_name="2027 Global Racket Masters",
                        year=2027,venue="Fictional Aurora Arena",timezone="UTC",status="APPROVED"),
             sessions=[],seating=[],prices=[],inventory=[],products=[],rules=[],tasks=[],decisions=[],scenarios={},
             quality_evidence={k:[] for k in ("cells","totals","summaries","percentages","metrics","documents","named_models","output_refs")})
    tiers = [("VIP",760,730),("GOLD",1440,510),("SILVER",1960,330),("BRONZE",2280,210),("VALUE",1600,95)]
    stages = ["QUALIFYING","GROUP","PLAYOFF","FINALS"]
    for i in range(16):
        sid=f"S{i+1:02d}"; st=start+timedelta(days=i//2,hours=7*(i%2)); stage=stages[i//4]
        d["sessions"].append(dict(session_id=sid,event_id=d["event"]["event_id"],stage=stage,
                                  start_time=st.isoformat(),end_time=(st+timedelta(hours=3)).isoformat()))
        for tier,capacity,base in tiers:
            d["prices"].append(dict(price_version="prices-a",session_id=sid,tier=tier,
                price=base+85*(i//4),status="APPROVED",valid_from="2027-05-01T00:00:00+00:00",approval_ref="SYNTHETIC-PRICE-A"))
            for zone,cap in (("MAIN",capacity*4//5),("SIDE",capacity-capacity*4//5)):
                holds=dict(functional_hold=cap//40,broadcast_hold=cap//50,free_rights=cap//30,other_hold=cap//80)
                row=dict(session_id=sid,zone_id=zone,tier=tier,visibility="RESTRICTED" if zone=="SIDE" else "CLEAR",
                         physical_capacity=cap,paid_rights=cap//25,**holds,
                         deduction_refs={k:[f"{sid}-{zone}-{tier}-{k}"] for k in holds})
                d["seating"].append(row)
                for status,quantity,channel in (("PAID_RESERVED",row["paid_rights"],"FICTIONAL_RIGHTS"),
                                                ("AVAILABLE",sellable(row)-row["paid_rights"],"FICTIONAL_PUBLIC")):
                    d["inventory"].append(dict(inventory_id=f"{sid}-{tier}-{zone}-{status}",session_id=sid,zone_id=zone,
                        tier=tier,channel=channel,status=status,allocation_type="PAID_RIGHTS" if status=="PAID_RESERVED" else "PUBLIC",quantity=quantity,as_of="2027-05-01T00:00:00+00:00",source_ref="SYNTHETIC-DEMO"))
    for name,rate in (("low",.52),("mid",.71),("high",.88)):
        d["scenarios"][name]=dict(session_rates={s["session_id"]:round(min(.99,rate+.02*(i//4)),2) for i,s in enumerate(d["sessions"])},
                                    tier_rates={t:round(.92+i*.02,2) for i,(t,_,_) in enumerate(tiers)},paid_rights_rate=1)
    def comp(sid,quantity=1):
        return dict(session_id=sid,zone_id="MAIN",tier="VIP",ticket_quantity=quantity)
    d["products"]=[dict(product_id="SINGLE-DEMO",product_type="SINGLE",included_sessions=[comp("S01")],price=None,price_claim="SUM_FACE_PRICES"),
        dict(product_id="PASS-DEMO",product_type="PASS",included_sessions=[comp(s["session_id"]) for s in d["sessions"]],price=None,price_claim="SUM_FACE_PRICES"),
        dict(product_id="TRAVEL-TWIN-DEMO",product_type="TRAVEL",included_sessions=[comp("S15",2)],price=2*985+858,
             price_claim="INDEPENDENT",travel=dict(guests=2,expected_rooms=1,room_quantity=1,nights=1,room_cost=420,
                 service_per_guest=180,other_cost=0,pricing_method="markup",actual_method="markup",rate=.1,quoted_non_ticket=858))]
    common=dict(version="rules-a",valid_from="2027-05-01T00:00:00+00:00",valid_to="2027-07-18T00:00:00+00:00",
                status="APPROVED",approval_ref="SYNTHETIC-RULE-A")
    for kind,content in [
        ("refund",dict(coverage_start="2027-05-01T00:00:00+00:00",coverage_end="2027-07-18T00:00:00+00:00",windows=[
            dict(start="2027-05-01T00:00:00+00:00",end="2027-07-01T00:00:00+00:00",fee_rate=0),
            dict(start="2027-07-01T00:00:00+00:00",end="2027-07-08T00:00:00+00:00",fee_rate=.15),
            dict(start="2027-07-08T00:00:00+00:00",end="2027-07-18T00:00:00+00:00",fee_rate=1)])),
        ("transfer",dict(allowed=False)),("identity",dict(mode="ONE_TICKET_PER_SESSION_NO_PERSONAL_DATA")),
        ("rights_return",dict(hours_before=60)),
        ("launch",dict(denominator="PUBLIC_POOL",rounds=[dict(at=f"2027-06-{day:02d}T09:00:00+00:00",fraction=f) for day,f in [(1,.25),(12,.45),(24,.30)]]))]:
        d["rules"].append(dict(rule_id=f"R-{kind}",rule_type=kind,content=content,**common))
    d["tasks"]=[dict(task_id="T1",title="Review synthetic seating plan",owner_role="VENUE_REVIEWER",due_at="2027-04-20T00:00:00+00:00",
        depends_on=[],status="DONE",acceptance="Plan reference checked",proof="SYNTHETIC-PROOF-1",phase="PRE_EVENT")]
    d["quality_evidence"]["documents"]=[dict(source="demo/title",text=d["event"]["event_name"],critical=True)]
    return d

def make_version_b(a):
    b=deepcopy(a);b["data_version"]="demo-b";b["price_version"]="prices-b";b["rules_version"]="rules-b"
    for p in b["prices"]:
        p["price_version"]="prices-b"
        if p["session_id"]=="S01" and p["tier"]=="VIP":p["price"]+=35
    for r in b["rules"]:
        r["version"]="rules-b"
        if r["rule_type"]=="rights_return":r["content"]["hours_before"]=72
    b["decisions"]=[dict(decision_id="D-DEMO-1",issue="Synthetic price scenario",options=["Keep price","Test increment"],
        decision="Test increment",reason="Fictional demand experiment",approved_by_role="DEMO_REVIEWER",
        effective_at="2027-05-01T00:00:00+00:00",source_ref="SYNTHETIC-DECISION-1",confirmed=True,changed_paths=["prices/S01/VIP/price"])]
    b["seating"][0]["physical_capacity"]+=12
    b["inventory"][1]["quantity"]+=12
    launch=next(r for r in b["rules"] if r["rule_type"]=="launch")
    launch["content"]["rounds"][0].update(at="2027-05-30T09:00:00+00:00",fraction=.30)
    launch["content"]["rounds"][1]["fraction"]=.40
    b["products"].pop(0)
    b["products"].append(dict(product_id="WEEKEND-PASS-DEMO",product_type="PASS",price=None,price_claim="SUM_FACE_PRICES",
        included_sessions=[dict(session_id=s,zone_id="MAIN",tier="GOLD",ticket_quantity=1) for s in ["S15","S16"]]))
    b["quality_evidence"]["documents"][0]["text"]+="\nSynthetic revised plan; reasons need evidence."
    for product in b["products"]:
        if product["price_claim"]=="SUM_FACE_PRICES":
            product["price"]=None
    return b
