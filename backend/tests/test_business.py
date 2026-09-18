import os
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
(ROOT/".runtime").mkdir(exist_ok=True)
os.environ["DATABASE_URL"]="sqlite:///"+(ROOT/".runtime"/"test-business.db").as_posix()
os.environ["ONDA_DEV_MODE"]="true"

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import Base, Record, Proposal, Audit, engine, transaction
from backend.schemas import Actor, ActionInput
from backend.seed import seed
from backend.services import propose, decide, read_records, analytics
from backend.app import app

BUYER=Actor(id="buyer-001",role="buyer")
SELLER=Actor(id="seller-001",role="seller")


@pytest.fixture(autouse=True)
def reset():
    Base.metadata.drop_all(engine)
    seed()


def action(who,kind,target,params=None,version=None):
    return propose(who,ActionInput(action=kind,target=target,params=params or {},expected_version=version))


def test_scope_isolation():
    assert len(read_records(BUYER,"order"))==3
    assert len(read_records(SELLER,"order"))==63
    with pytest.raises(HTTPException) as exc: action(BUYER,"cancel_order","ODHISTORY00013")
    assert exc.value.status_code==404


def test_no_change_before_confirmation():
    p=action(BUYER,"cancel_order","OD20260918001")
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="待发货"
    decide(BUYER,p["id"],False)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="待发货"


def test_cancel_idempotency():
    p=action(BUYER,"cancel_order","OD20260918001")
    first=decide(BUYER,p["id"],True)
    assert first==decide(BUYER,p["id"],True)
    with transaction() as s: assert len(s.scalars(select(Audit)).all())==1


def test_concurrent_proposals_stale():
    a=action(BUYER,"cancel_order","OD20260918001")
    b=action(BUYER,"cancel_order","OD20260918001")
    decide(BUYER,a["id"],True)
    with pytest.raises(HTTPException) as exc: decide(BUYER,b["id"],True)
    assert exc.value.status_code==409


def test_cross_role_approval_forbidden():
    p=action(BUYER,"cancel_order","OD20260918001")
    with pytest.raises(HTTPException): decide(SELLER,p["id"],True)


def test_expired_approval():
    p=action(BUYER,"cancel_order","OD20260918001")
    with transaction() as s:s.get(Proposal,p["id"]).expires="2000-01-01"
    with pytest.raises(HTTPException): decide(BUYER,p["id"],True)
    assert decide(BUYER,p["id"],False)["status"] == "rejected"


@pytest.mark.parametrize("params",[{"price":-1},{"stock":-1},{"name":" "}])
def test_bad_product_fields_are_client_errors(params):
    with pytest.raises(HTTPException) as exc: action(SELLER,"edit_product","HP001",params)
    assert exc.value.status_code == 422


def test_concurrent_confirmation_executes_once():
    from concurrent.futures import ThreadPoolExecutor
    p=action(BUYER,"cancel_order","OD20260918001")
    def confirm():
        try: return decide(BUYER,p["id"],True)["status"]
        except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _: confirm(), range(2)))
    assert "executed" in outcomes
    assert all(value in ("executed",409) for value in outcomes)
    with transaction() as s: assert len(s.scalars(select(Audit)).all()) == 1


@pytest.mark.parametrize("target",["OD20260916002","OD20260912003"])
def test_no_cancel_after_shipping(target):
    with pytest.raises(HTTPException): action(BUYER,"cancel_order",target)


def test_refund_end_to_end():
    p=action(BUYER,"request_refund","OD20260912003",{"reason":"质量问题"})
    decide(BUYER,p["id"],True)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="退款审核中"
    assert len(read_records(BUYER,"refund"))==1
    p=action(SELLER,"approve_refund",p["target"])
    decide(SELLER,p["id"],True)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="退款处理中"
    assert read_records(BUYER,"refund")[0]["status"]=="处理中"


def test_duplicate_refund_rejected():
    p=action(BUYER,"request_refund","OD20260912003")
    decide(BUYER,p["id"],True)
    with pytest.raises(HTTPException): action(BUYER,"request_refund",p["target"])


def test_buyer_cannot_change_price():
    with pytest.raises(HTTPException): action(BUYER,"edit_product","HP001",{"price":1})


def test_tool_parameter_injection_rejected():
    with pytest.raises(HTTPException): action(BUYER,"cancel_order","OD20260918001",{"owner":"buyer-999"})


def test_product_version_and_visibility():
    p=action(SELLER,"set_product_status","HP001",{"status":"下架"},1)
    decide(SELLER,p["id"],True)
    assert not read_records(BUYER,"product","HP001")
    with pytest.raises(HTTPException): action(SELLER,"edit_product","HP001",{"price":300},1)


def test_shipping_validates_time_and_tracking():
    with pytest.raises(HTTPException): action(SELLER,"ship_order","OD20260918001",{"tracking":"?","shippedAt":"2026-09-18T10:00"})
    with pytest.raises(HTTPException): action(SELLER,"ship_order","OD20260918001",{"tracking":"SF123456789","shippedAt":"2099-01-01T10:00"})


def test_metrics_computed_from_orders():
    data=analytics(SELLER)
    records=[o for o in read_records(SELLER,"order") if data["trend"][0]["date"]<=o["date"]]
    assert data["orderCount"]==len(records)
    assert data["sales"]==sum(o["amount"] for o in records if o["status"]!="已取消")
    assert sum(d["amount"] for d in data["trend"])==data["sales"]


def test_ticket_close_does_not_refund():
    p=action(SELLER,"close_ticket","WD20260918003",{"note":"人工已记录诉求"})
    decide(SELLER,p["id"],True)
    assert read_records(BUYER,"order","OD20260912003")[0]["status"]=="已签收"


def test_api_requires_auth_and_local_session():
    with TestClient(app,client=("127.0.0.1",50100)) as c:
        assert c.get("/api/state").status_code==401
        token=c.post("/api/auth/dev/buyer").json()["token"]
        headers={"Authorization":"Bearer "+token}
        assert len(c.get("/api/state",headers=headers).json()["orders"])==3
        assert c.get("/api/analytics",headers=headers).status_code==403
        assert c.post("/api/auth/dev/seller",headers={"Origin":"https://evil.example"}).status_code==403


def test_nonlocal_development_login_rejected():
    with TestClient(app,client=("203.0.113.4",50100)) as c:
        assert c.post("/api/auth/dev/seller").status_code==403
