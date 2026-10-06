"""One schema definition drives runtime shape validation and schema export."""
def obj(properties, optional=()):
    return {"type": "object", "properties": properties,
            "required": [k for k in properties if k not in optional], "additionalProperties": False}

def arr(items):
    return {"type": "array", "items": items}

S = {"type": "string", "minLength": 1}
TEXT = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer", "minimum": 0}
RATE = {"type": "number", "minimum": 0, "maximum": 1}
NULL_S = {"type": ["string", "null"]}
STATUS = {"enum": ["DRAFT", "APPROVED", "PUBLISHED", "RETIRED"]}
MAP_RATE = {"type": "object", "additionalProperties": RATE}
HOLD_FIELDS = ("functional_hold", "broadcast_hold", "free_rights", "other_hold")

SESSION = obj(dict(session_id=S, event_id=S, stage=S, start_time=S, end_time=S))
SEATING = obj(dict(session_id=S, zone_id=S, tier=S, visibility={"enum": ["CLEAR", "RESTRICTED"]},
                   physical_capacity=I, **{k:I for k in HOLD_FIELDS}, paid_rights=I,
                   deduction_refs=obj({k:arr(S) for k in HOLD_FIELDS})))
PRICE = obj(dict(price_version=S, session_id=S, tier=S, price=N,
                 status=STATUS, valid_from=S, approval_ref=NULL_S))
INVENTORY = obj(dict(inventory_id=S, session_id=S, zone_id=S, tier=S, channel=S,
                     status={"enum":["AVAILABLE", "SOLD", "LOCKED", "PAID_RESERVED"]},
                     allocation_type={"enum":["PUBLIC","PAID_RIGHTS"]}, quantity=I, as_of=S, source_ref=S))
COMPONENT = obj(dict(session_id=S, zone_id=S, tier=S, ticket_quantity=I))
TRAVEL = obj(dict(guests=I, expected_rooms=I, room_quantity=I, nights=I,
                  room_cost=N, service_per_guest=N, other_cost=N,
                  pricing_method={"enum":["markup", "margin"]}, rate=RATE,
                  actual_method={"enum":["markup", "margin"]}, quoted_non_ticket=N))
PRODUCT = obj(dict(product_id=S, product_type={"enum":["SINGLE", "PASS", "TRAVEL"]},
                   included_sessions=arr(COMPONENT), price={"type":["number","null"]},
                   price_claim={"enum":["INDEPENDENT", "SUM_FACE_PRICES"]},
                   travel=TRAVEL), optional=("travel",))
RULE = obj(dict(rule_id=S, rule_type={"enum":["refund", "transfer", "identity", "rights_return", "launch"]},
                version=S, content={"type":"object"}, valid_from=S, valid_to=S,
                status=STATUS, approval_ref=NULL_S))
TASK = obj(dict(task_id=S, title=S, owner_role=S, due_at=S, depends_on=arr(S),
                status={"enum":["TODO", "DOING", "DONE"]}, acceptance=S, proof=NULL_S,
                phase={"enum":["PRE_EVENT", "DURING_EVENT", "POST_EVENT"]}))
DECISION = obj(dict(decision_id=S, issue=S, options=arr(S), decision=S, reason=S,
                    approved_by_role=S, effective_at=S, source_ref=S, confirmed={"type":"boolean"},
                    changed_paths=arr(S)))
SCENARIO = obj(dict(session_rates=MAP_RATE, tier_rates=MAP_RATE, paid_rights_rate=RATE))
EVIDENCE = obj(dict(
    cells=arr(obj(dict(source=S, value={"type":["string","number","null"]}))),
    totals=arr(obj(dict(source=S, components=arr(N), declared=N))),
    summaries=arr(obj(dict(source=S, metric=S, value=N, mode={"enum":["FORMULA","HARDCODED"]}))),
    percentages=arr(obj(dict(source=S, values=arr(RATE), expected=RATE))),
    metrics=arr(obj(dict(metric_id=S, unit=S, source=S))),
    documents=arr(obj(dict(source=S, text=TEXT, critical={"type":"boolean"}))),
    named_models=arr(obj(dict(name=S, content=TEXT, source=S))),
    output_refs=arr(obj(dict(source=S, snapshot_id=S)))
))
SCHEMA = obj(dict(
    schema_version={"const":"1.0"}, data_version=S, rules_version=S, price_version=S,
    status=STATUS, approval_ref=NULL_S, snapshot_id=NULL_S, synthetic={"const":True},
    event=obj(dict(event_id=S, event_name=S, year={"type":"integer","minimum":2000,"maximum":2200},
                   venue=S, timezone=S, status=STATUS)),
    sessions=arr(SESSION), seating=arr(SEATING), prices=arr(PRICE), inventory=arr(INVENTORY),
    products=arr(PRODUCT), rules=arr(RULE), tasks=arr(TASK), decisions=arr(DECISION),
    scenarios=obj({k:SCENARIO for k in ("low","mid","high")}),
    quality_evidence=EVIDENCE
))
# Optional v1.1 bridge fields; legacy documents remain valid.
SEATING['properties']['price_class_id'] = S
PRICE['properties']['price_class_id'] = S
SEATING['properties']['paid_rights_pricing'] = obj(dict(
    strategy={'enum':['FACE_VALUE','FIXED_PRICE','DISCOUNT_RATE']}, value=N))
SCHEMA.update({"$schema":"https://json-schema.org/draft/2020-12/schema", "title":"Synthetic Event Master v1"})
