"""Shared authorization, business transitions and immutable approvals.

Neither frontend handlers nor model tools can bypass this module to write records.
"""
import copy
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update

from .db import Audit, Proposal, Record, now, transaction, uid
from .policies import POLICY_VERSION
from .schemas import ActionInput, Actor, ProductInput

TITLES = {"cancel_order":"取消订单","request_refund":"申请退款","approve_refund":"同意退款申请","reject_refund":"拒绝退款申请","ship_order":"登记发货","edit_product":"修改商品信息","set_product_status":"调整商品上下架","close_ticket":"完成工单","update_ticket":"更新工单"}
TITLES['plan_restock']='记录补货计划'


def fail(status, message):
    raise HTTPException(status, message)


def visible(record, actor):
    if record.merchant != actor.merchant:
        return False
    if actor.role == "seller":
        return True
    return record.data.get("status") == "在售" if record.kind == "product" else record.owner == actor.id


def get_record(s, actor, target, kind=None):
    record = s.get(Record, target)
    if not record or not visible(record, actor) or (kind and record.kind != kind):
        fail(404, "未找到可访问的记录")
    return record


def present(record):
    return {**record.data, "id":record.id, "version":record.version}


def read_records(actor, kind, query=""):
    with transaction() as s:
        rows = s.scalars(select(Record).where(Record.kind == kind, Record.merchant == actor.merchant)).all()
        return [present(r) for r in rows if visible(r,actor) and (not query or query.casefold() in str(r.data).casefold() or query.casefold() in r.id.casefold())]


def analytics(actor, days=30):
    if actor.role != "seller":
        fail(403,"仅商家可查看经营数据")
    days = max(1,min(90,int(days)))
    orders = read_records(actor,"order")
    today = datetime.now(timezone(timedelta(hours=8))).date()
    cutoff = today - timedelta(days=days-1)
    selected = [o for o in orders if cutoff.isoformat() <= o["date"] <= today.isoformat()]
    paid = [o for o in selected if o["status"] != "已取消"]
    total = sum(Decimal(str(o["amount"])) for o in paid)
    counts = Counter()
    for order in paid: counts[order["productId"]] += order.get("quantity",1)
    trend = [{"date":(cutoff+timedelta(days=i)).isoformat(),"amount":float(sum(Decimal(str(o["amount"])) for o in paid if o["date"] == (cutoff+timedelta(days=i)).isoformat()))} for i in range(days)]
    products = read_records(actor,"product")
    return {"days":days,"sales":float(total),"orderCount":len(selected),"pendingTickets":len([t for t in read_records(actor,"ticket") if t["status"] != "已完成"]),"productCount":len(products),"trend":trend,"orderStatuses":dict(Counter(o["status"] for o in selected)),"topProducts":[{**p,"sales":counts[p["id"]]} for p in sorted(products,key=lambda p:counts[p["id"]],reverse=True)],"lowStock":[p for p in products if p["stock"] < 10],"definition":"按下单日期统计，排除已取消订单；退款处理中尚未扣除。没有成本和流量数据，不提供利润、转化率。"}


def state(actor):
    with transaction() as s:
        audit = s.scalars(select(Audit).where(Audit.merchant == actor.merchant).order_by(Audit.created.desc()).limit(100)).all()
        logs = [{"id":a.id,**a.data,"date":a.created} for a in audit if actor.role == "seller" or a.actor == actor.id]
    result = {"products":read_records(actor,"product"),"orders":read_records(actor,"order"),"tickets":read_records(actor,"ticket"),"audit":logs,"actor":{"role":actor.role,"name":"你好，用户"}}
    if actor.role == "seller":
        result["analytics"] = analytics(actor)
        sales = {p["id"]:p["sales"] for p in result["analytics"]["topProducts"]}
        result["products"] = [{**p,"sales":sales.get(p["id"],0)} for p in result["products"]]
    return result


def validated_change(record, actor, action, params):
    """Re-evaluated at proposal creation and immediately before commit."""
    d = copy.deepcopy(record.data)
    if action not in TITLES:
        fail(422,"不支持的操作")
    if actor.role == "buyer" and action not in ("cancel_order","request_refund"):
        fail(403,"当前角色无权执行此操作")
    expected_kind = "product" if action in ("edit_product","set_product_status","plan_restock") else "ticket" if action in ("close_ticket","update_ticket") else "order"
    if record.kind != expected_kind:
        fail(422,"操作与对象类型不匹配")
    allowed = {"cancel_order":set(),"request_refund":{"reason"},"approve_refund":set(),"reject_refund":{"reason"},"ship_order":{"tracking","shippedAt"},"edit_product":{"name","desc","price","stock","category"},"set_product_status":{"status"},"close_ticket":{"note"},"update_ticket":{"note","status"},"plan_restock":{"quantity"}}[action]
    if set(params) - allowed:
        fail(422,"操作包含不支持的参数")
    if action == "plan_restock":
        quantity=params.get('quantity')
        if isinstance(quantity,bool) or not isinstance(quantity,int) or not 1<=quantity<=10000: fail(422,'补货数量须为 1 至 10000 的整数')
        if d['status']!='在售': fail(409,'仅为在售商品记录补货计划')
    elif action == "cancel_order":
        if d["status"] != "待发货": fail(409,"只有待发货订单可以取消")
        d.update(status="已取消",fulfillmentStatus="已取消")
    elif action == "request_refund":
        if actor.role != "buyer": fail(403,"退款申请必须由订单所属消费者提交")
        if d["status"] != "已签收": fail(409,"只有已签收且没有在途退款的订单可申请退款")
        reason = str(params.get("reason","用户申请退款")).strip()
        if not reason or len(reason)>500: fail(422,"请提供有效的退款原因")
        d.update(status="退款审核中",refundStatus="待审核")
    elif action in ("approve_refund","reject_refund"):
        if d["status"] != "退款审核中": fail(409,"当前订单没有待审核退款")
        if action == "reject_refund" and not str(params.get("reason","")).strip(): fail(422,"拒绝退款需要填写原因")
        d.update(status="退款处理中" if action == "approve_refund" else "已签收",refundStatus="处理中" if action == "approve_refund" else "已拒绝")
    elif action == "ship_order":
        if d["status"] != "待发货": fail(409,"订单已不处于待发货状态")
        tracking = str(params.get("tracking","")).strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{6,40}",tracking): fail(422,"物流单号格式不正确")
        try:
            shipped = datetime.fromisoformat(params.get("shippedAt",""))
            if shipped.tzinfo: shipped = shipped.replace(tzinfo=None)
            if shipped.date() < date.fromisoformat(d["date"]) or shipped > datetime.now()+timedelta(minutes=5): raise ValueError()
        except (ValueError,TypeError): fail(422,"发货时间须在下单后且不能晚于当前时间")
        d.update(status="运输中",fulfillmentStatus="运输中",tracking=tracking,shippedAt=shipped.strftime("%Y-%m-%d %H:%M"))
    elif action == "edit_product":
        if not params: fail(422,"没有要修改的字段")
        try:
            values = ProductInput.model_validate({k:params.get(k,d[k]) for k in ("name","desc","price","stock","category")}).model_dump()
        except ValidationError:
            fail(422,"商品字段不合法，请检查名称、价格、库存与分类")
        values["price"] = float(Decimal(str(values["price"])).quantize(Decimal("0.01")))
        if values["price"] <= 0: fail(422,"价格必须至少为 0.01 元")
        d.update(values)
    elif action == "set_product_status":
        if params.get("status") not in ("在售","下架"): fail(422,"商品状态不合法")
        d["status"] = params["status"]
    elif action in ("close_ticket","update_ticket"):
        if d["status"] == "已完成": fail(409,"工单已完成")
        note = str(params.get("note","")).strip()
        if not note or len(note)>2000: fail(422,"请填写有效处理记录")
        target = "已完成" if action == "close_ticket" else params.get("status","处理中")
        if target not in ("待处理","处理中"):
            if action != "close_ticket": fail(422,"完成工单请使用完成操作")
        d.update(status=target,notes=[*d["notes"],{"text":note,"date":now()}])
    if record.kind == "product" and action!='plan_restock': d["updatedAt"] = now()
    return d


def proposal_view(p):
    return {"id":p.id,"title":TITLES[p.action],"action":p.action,"target":p.target,"params":p.params,"status":p.status,"risk":"高","expires":p.expires,"result":p.result,"description":"请核对操作对象与变更内容。确认后由服务端再次检查权限、状态及数据版本。退款审核通过仅进入处理中，不代表到账。"}


def propose(actor: Actor, payload: ActionInput, run_id=None):
    with transaction() as s:
        record = get_record(s,actor,payload.target)
        if payload.expected_version is not None and record.version != payload.expected_version:
            fail(409,"数据已更新，请刷新后重新发起")
        updated = validated_change(record,actor,payload.action,payload.params)
        if payload.action=='plan_restock':
            plans=s.scalars(select(Record).where(Record.kind=='restock_plan',Record.merchant==actor.merchant)).all()
            if any(p.data.get('productId')==record.id and p.data.get('status')=='待补货' for p in plans): fail(409,'该商品已有待补货计划，请先核对现有计划')
        p = Proposal(id=uid("AP-"),actor=actor.id,role=actor.role,merchant=actor.merchant,action=payload.action,target=record.id,version=record.version,params=payload.params,status="pending",expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),run_id=run_id,result={"changes":{k:{"before":record.data.get(k),"after":v} for k,v in updated.items() if record.data.get(k)!=v},"policyVersion":POLICY_VERSION})
        s.add(p)
        if payload.action=='plan_restock': p.result={**p.result,'changes':{'plannedQuantity':{'before':0,'after':payload.params['quantity']}}}
        s.flush()
        return proposal_view(p)


def decide(actor, proposal_id, approved):
    with transaction() as s:
        p = s.get(Proposal,proposal_id)
        if not p or p.actor != actor.id or p.role != actor.role or p.merchant != actor.merchant: fail(404,"未找到可审批的操作")
        if p.status in ("executed","rejected"):
            if (p.status=="executed") != approved: fail(409,"该审批已作出不同决定")
            return proposal_view(p)
        if p.status != "pending": fail(409,"该操作已失效")
        if approved and p.expires < now(): fail(409,"确认已过期，请拒绝旧方案后重新发起")
        # Compare-and-swap prevents two requests from executing the same approval.
        claimed=s.execute(update(Proposal).where(Proposal.id==p.id,Proposal.status=="pending").values(status="executing").execution_options(synchronize_session=False))
        if claimed.rowcount != 1: fail(409,"该操作正在处理，请查询结果")
        if not approved:
            p.status="rejected"
            s.add(Audit(id=uid("LOG-"),actor=actor.id,merchant=actor.merchant,data={"title":TITLES[p.action],"target":p.target,"role":actor.role,"status":"已拒绝","proposalId":p.id}))
            return proposal_view(p)
        record=get_record(s,actor,p.target)
        if record.version != p.version: fail(409,"对象已发生变化，本次确认不能执行，请重新发起")
        changed=validated_change(record,actor,p.action,p.params)
        done=s.execute(update(Record).where(Record.id==record.id,Record.version==p.version).values(data=changed,version=p.version+1).execution_options(synchronize_session=False))
        if done.rowcount != 1: fail(409,"数据发生并发更新，请重试")
        if p.action=='plan_restock':
            existing=s.scalars(select(Record).where(Record.kind=='restock_plan',Record.merchant==actor.merchant)).all()
            if any(r.data.get('productId')==record.id and r.data.get('status')=='待补货' for r in existing): fail(409,'已有待补货计划，不可重复提交')
            s.add(Record(id=uid('RP-'),kind='restock_plan',owner=actor.id,merchant=actor.merchant,data={'productId':record.id,'productName':record.data['name'],'quantity':p.params['quantity'],'status':'待补货','date':now(),'proposalId':p.id}))
        if p.action == "request_refund":
            s.add(Record(id=uid("RF-"),kind="refund",owner=record.owner,merchant=actor.merchant,data={"orderId":record.id,"amount":record.data["amount"],"reason":p.params.get("reason","用户申请退款"),"status":"待审核","date":now()}))
            s.add(Record(id=uid("WD-"),kind="ticket",owner=record.owner,merchant=actor.merchant,data={"user":"用户","phone":"—","type":"售后退款","description":p.params.get("reason","用户申请退款"),"orderId":record.id,"risk":"高","status":"待处理","date":now(),"notes":[]}))
        if p.action in ("approve_refund","reject_refund"):
            for related in s.scalars(select(Record).where(Record.merchant==actor.merchant,Record.kind.in_(["refund","ticket"]))):
                if related.data.get("orderId") != record.id: continue
                rd=copy.deepcopy(related.data)
                if related.kind=="refund" and rd["status"]=="待审核": rd["status"]=changed["refundStatus"]
                elif related.kind=="ticket" and rd["type"]=="售后退款" and rd["status"]!="已完成":
                    rd.update(status="处理中" if p.action=="approve_refund" else "已完成",notes=[*rd["notes"],{"text":TITLES[p.action]+("："+p.params["reason"] if p.params.get("reason") else "，等待渠道退款结果"),"date":now()}])
                else: continue
                related.data=rd
                related.version+=1
        p.status="executed"
        p.result={**p.result,"record":{"id":record.id,**changed,"version":p.version+1}}
        s.add(Audit(id=uid("LOG-"),actor=actor.id,merchant=actor.merchant,data={"title":TITLES[p.action],"target":p.target,"role":actor.role,"status":"已完成","proposalId":p.id,"changes":p.result["changes"]}))
        return proposal_view(p)


def create_product(actor, values):
    if actor.role != "seller": fail(403,"仅商家可创建商品")
    d=values.model_dump()
    d["price"] = float(Decimal(str(d["price"])).quantize(Decimal("0.01")))
    if d["price"] <= 0: fail(422,"价格必须至少为 0.01 元")
    d.update(status="草稿",sales=0,crop=[383,368,382,165],source="消费者商品页.png",updatedAt=now())
    with transaction() as s:
        r=Record(id=uid("P-"),kind="product",owner=actor.id,merchant=actor.merchant,data=d)
        s.add(r);s.flush()
        return present(r)


def create_ticket(actor, order_id, description):
    if not description.strip() or len(description)>2000: fail(422,"工单描述长度不正确")
    with transaction() as s:
        order=get_record(s,actor,order_id,"order")
        risk="高" if any(w in description for w in ("退款","取消","赔偿")) else "中"
        r=Record(id=uid("WD-"),kind="ticket",owner=order.owner,merchant=actor.merchant,data={"user":"用户","phone":"—","type":"售后退款" if "退款" in description else "其他问题","description":description,"orderId":order_id,"risk":risk,"status":"待处理","date":now(),"notes":[]})
        s.add(r);s.flush()
        return present(r)
