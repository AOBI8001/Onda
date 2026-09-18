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
    with pytest.raises(HTTPException) as exc: action(BUYER,"cancel_order","OD-697598AB2A")
    assert exc.value.status_code==404


def test_no_change_before_confirmation():
    p=action(BUYER,"cancel_order","OD-Q7M2K9")
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="待发货"
    decide(BUYER,p["id"],False)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="待发货"


def test_cancel_idempotency():
    p=action(BUYER,"cancel_order","OD-Q7M2K9")
    first=decide(BUYER,p["id"],True)
    assert first==decide(BUYER,p["id"],True)
    with transaction() as s: assert len(s.scalars(select(Audit)).all())==1


def test_concurrent_proposals_stale():
    a=action(BUYER,"cancel_order","OD-Q7M2K9")
    b=action(BUYER,"cancel_order","OD-Q7M2K9")
    decide(BUYER,a["id"],True)
    with pytest.raises(HTTPException) as exc: decide(BUYER,b["id"],True)
    assert exc.value.status_code==409


def test_cross_role_approval_forbidden():
    p=action(BUYER,"cancel_order","OD-Q7M2K9")
    with pytest.raises(HTTPException): decide(SELLER,p["id"],True)


def test_expired_approval():
    p=action(BUYER,"cancel_order","OD-Q7M2K9")
    with transaction() as s:s.get(Proposal,p["id"]).expires="2000-01-01"
    with pytest.raises(HTTPException): decide(BUYER,p["id"],True)
    assert decide(BUYER,p["id"],False)["status"] == "rejected"


@pytest.mark.parametrize("params",[{"price":-1},{"stock":-1},{"name":" "}])
def test_bad_product_fields_are_client_errors(params):
    with pytest.raises(HTTPException) as exc: action(SELLER,"edit_product","P-95CC2D4C8F",params)
    assert exc.value.status_code == 422


def test_concurrent_confirmation_executes_once():
    from concurrent.futures import ThreadPoolExecutor
    p=action(BUYER,"cancel_order","OD-Q7M2K9")
    def confirm():
        try: return decide(BUYER,p["id"],True)["status"]
        except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _: confirm(), range(2)))
    assert "executed" in outcomes
    assert all(value in ("executed",409) for value in outcomes)
    with transaction() as s: assert len(s.scalars(select(Audit)).all()) == 1


@pytest.mark.parametrize("target",["OD-N4R8V1","OD-X6P3T5"])
def test_no_cancel_after_shipping(target):
    with pytest.raises(HTTPException): action(BUYER,"cancel_order",target)


def test_refund_end_to_end():
    p=action(BUYER,"request_refund","OD-X6P3T5",{"reason":"质量问题"})
    decide(BUYER,p["id"],True)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="退款审核中"
    assert len(read_records(BUYER,"refund"))==1
    p=action(SELLER,"approve_refund",p["target"])
    decide(SELLER,p["id"],True)
    assert read_records(BUYER,"order",p["target"])[0]["status"]=="退款处理中"
    assert read_records(BUYER,"refund")[0]["status"]=="处理中"


def test_duplicate_refund_rejected():
    p=action(BUYER,"request_refund","OD-X6P3T5")
    decide(BUYER,p["id"],True)
    with pytest.raises(HTTPException): action(BUYER,"request_refund",p["target"])


def test_buyer_cannot_change_price():
    with pytest.raises(HTTPException): action(BUYER,"edit_product","P-95CC2D4C8F",{"price":1})


def test_tool_parameter_injection_rejected():
    with pytest.raises(HTTPException): action(BUYER,"cancel_order","OD-Q7M2K9",{"owner":"buyer-999"})


def test_product_version_and_visibility():
    p=action(SELLER,"set_product_status","P-95CC2D4C8F",{"status":"下架"},1)
    decide(SELLER,p["id"],True)
    assert not read_records(BUYER,"product","P-95CC2D4C8F")
    with pytest.raises(HTTPException): action(SELLER,"edit_product","P-95CC2D4C8F",{"price":300},1)


def test_shipping_validates_time_and_tracking():
    with pytest.raises(HTTPException): action(SELLER,"ship_order","OD-Q7M2K9",{"tracking":"?","shippedAt":"2026-09-18T10:00"})
    with pytest.raises(HTTPException): action(SELLER,"ship_order","OD-Q7M2K9",{"tracking":"SF123456789","shippedAt":"2099-01-01T10:00"})


def test_metrics_computed_from_orders():
    data=analytics(SELLER)
    records=[o for o in read_records(SELLER,"order") if data["trend"][0]["date"]<=o["date"]]
    assert data["orderCount"]==len(records)
    assert data["sales"]==pytest.approx(sum(o["amount"] for o in records if o["status"]!="已取消"))
    assert sum(d["amount"] for d in data["trend"])==pytest.approx(data["sales"])


def test_metrics_use_store_day_across_utc_midnight(monkeypatch):
    from datetime import datetime, timezone
    import backend.services as services
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value=cls(2026,9,18,17,tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(services,'datetime',FixedClock)
    orders=[{'date':day,'status':'待发货','amount':10,'productId':'P-TEST'} for day in ('2026-09-18','2026-09-19','2026-09-20')]
    monkeypatch.setattr(services,'read_records',lambda actor,kind: orders if kind=='order' else [])
    data=services.analytics(SELLER,days=1)
    assert data['trend']==[{'date':'2026-09-19','amount':10.0}]
    assert data['orderCount']==1


def test_ticket_close_does_not_refund():
    p=action(SELLER,"close_ticket","TK-P6X9C2",{"note":"人工已记录诉求"})
    decide(SELLER,p["id"],True)
    assert read_records(BUYER,"order","OD-X6P3T5")[0]["status"]=="已签收"


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


def test_catalog_has_100_real_sourced_products_and_local_images():
    products=read_records(SELLER,'product')
    assert len(products)==len({p['id'] for p in products})==len({p['name'] for p in products})==100
    assert len({p['category'] for p in products})==14
    for p in products:
        assert p['name'] and p['desc'] and len(p['features'])>=2
        assert p['sourceUrl'].startswith('https://') and p['sourcePrice']>0
        assert (ROOT/'public'/p['image'].lstrip('/')).is_file()
        assert p['currency']=='CNY' and p['sourceCurrency']=='USD'
    import re
    assert all(not re.search(r'20\d{6}',o['id']) for o in read_records(SELLER,'order'))


def test_inspection_detects_real_fixture_problems_without_business_writes():
    import asyncio
    from backend.inspections import check
    before=read_records(SELLER,'order'),read_records(SELLER,'product')
    result=asyncio.run(check(SELLER))
    items={r['id']:r for r in result['items']}
    assert 'stock' in items and 'growth' in items
    assert len(items['shipping']['rows'])==6
    assert 'margin' not in items
    assert before==(read_records(SELLER,'order'),read_records(SELLER,'product'))
    assert all(step['status']=='completed' for step in result['steps'])


def test_inspection_cache_and_version_invalidation():
    import asyncio
    from backend.inspections import check
    async def run():
        first=await check(SELLER)
        second=await check(SELLER)
        assert second['cached'] and first['checkedAt']==second['checkedAt']
        p=action(SELLER,'edit_product','P-95CC2D4C8F',{'stock':100})
        decide(SELLER,p['id'],True)
        third=await check(SELLER)
        assert not third['cached']
        stock=next(i for i in third['items'] if i['id']=='stock')
        assert 'P-95CC2D4C8F' not in [r['id'] for r in stock['rows']]
    asyncio.run(run())


def test_buyer_cannot_inspect_merchant():
    import asyncio
    from backend.inspections import check
    with pytest.raises(HTTPException): asyncio.run(check(BUYER))


def test_restock_approval_is_plan_not_inventory():
    before=read_records(SELLER,'product','P-95CC2D4C8F')[0]['stock']
    p=action(SELLER,'plan_restock','P-95CC2D4C8F',{'quantity':25})
    assert read_records(SELLER,'restock_plan')==[]
    decide(SELLER,p['id'],True);decide(SELLER,p['id'],True)
    assert read_records(SELLER,'product','P-95CC2D4C8F')[0]['stock']==before
    assert len(read_records(SELLER,'restock_plan'))==1
    with pytest.raises(HTTPException): action(SELLER,'plan_restock','P-95CC2D4C8F',{'quantity':25})


@pytest.mark.parametrize('quantity',[0,-1,10001,1.5,True,'4'])
def test_invalid_restock_quantity(quantity):
    with pytest.raises(HTTPException): action(SELLER,'plan_restock','P-95CC2D4C8F',{'quantity':quantity})


def test_buyer_cannot_restock():
    with pytest.raises(HTTPException): action(BUYER,'plan_restock','P-95CC2D4C8F',{'quantity':5})


def test_inspection_cold_start_no_sales_forecast_or_fake_profit():
    from backend.inspections import analyze
    p=read_records(SELLER,'product','P-95CC2D4C8F')[0]
    result=analyze([p],[],[])
    row=result['items'][0]['rows'][0]
    assert row['coverageDays'] is None and row['dailyDemand']==0
    assert '样本不足' in row['confidence']
    assert all(i['id']!='margin' for i in result['items'])


def test_cancelled_orders_not_overdue_and_future_orders_not_demand():
    from backend.inspections import analyze
    p=read_records(SELLER,'product','P-95CC2D4C8F')[0]
    result=analyze([p],[{'id':'OD-X','productId':p['id'],'date':'2000-01-01','status':'已取消','quantity':100,'version':1},{'id':'OD-Y','productId':p['id'],'date':'2099-01-01','status':'待发货','quantity':100,'version':1}],[])
    assert not any(i['id']=='shipping' for i in result['items'])
    assert result['items'][0]['rows'][0]['sold7']==0


def test_gross_profit_alert_requires_historical_cost_and_sales_growth():
    from datetime import datetime,timedelta,timezone
    from backend.inspections import analyze
    p=read_records(SELLER,'product','P-95CC2D4C8F')[0]
    current=datetime(2026,9,19,10,tzinfo=timezone.utc)
    orders=[{'id':'OD-OLD','productId':p['id'],'date':'2026-09-09','status':'已签收','quantity':4,'amount':400,'unitCost':40,'version':1},{'id':'OD-NEW','productId':p['id'],'date':'2026-09-16','status':'已签收','quantity':8,'amount':480,'unitCost':50,'version':1}]
    assert any(i['id']=='margin' for i in analyze([p],orders,[],current)['items'])
    del orders[0]['unitCost']
    assert not any(i['id']=='margin' for i in analyze([p],orders,[],current)['items'])


def test_legacy_migration_preserves_purchase_status_and_links():
    from backend.catalog_migration import migrate_legacy
    with transaction() as s:
        s.add(Record(id='HP001',kind='product',owner=SELLER.id,merchant=SELLER.merchant,data={'name':'旧商品'}))
        s.add(Record(id='OD20260918001',kind='order',owner=BUYER.id,merchant=BUYER.merchant,data={'productId':'HP001','productName':'旧商品','amount':499,'status':'待发货','date':'2026-09-18','quantity':1}))
        # Avoid an intentional primary-key collision in this migration fixture.
        s.delete(s.get(Record,'OD-Q7M2K9'))
    migrate_legacy()
    updated=read_records(BUYER,'order','OD-Q7M2K9')[0]
    assert updated['productId']=='P-95CC2D4C8F' and updated['amount']==499 and updated['status']=='待发货'
    assert len(read_records(SELLER,'product'))==100
    with transaction() as s: assert s.get(Record,'HP001') is None
    assert list((ROOT/'.runtime'/'backups').glob('pre-catalog-*.db'))
