"""Read-only proactive merchant workflow: evidence first, no model-authorized writes."""
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .db import Inspection, now, transaction, uid
from .schemas import Actor
from .services import fail, read_records

VERSION='attention-v1'
SLA_HOURS=48
CACHE_SECONDS=300
_locks={}


def ordered_at(order):
    try:
        value=datetime.fromisoformat(order.get('createdAt') or order['date']+'T00:00:00+08:00')
        return value if value.tzinfo else value.replace(tzinfo=timezone(timedelta(hours=8)))
    except (ValueError,TypeError,KeyError): return None


def analyze(products,orders,plans,current=None):
    current=current or datetime.now(timezone.utc)
    today=current.astimezone(timezone(timedelta(hours=8))).date()
    recent=Counter();previous=Counter();older=Counter();valid=[]
    for order in orders:
        when=ordered_at(order)
        if not when or when>current or order['status'] in ('已取消','已退款'): continue
        age=(today-when.astimezone(timezone(timedelta(hours=8))).date()).days
        # Closed calendar days avoid treating a partial current day as a full day.
        q=order.get('quantity',1)
        if 1<=age<=7: recent[order['productId']]+=q
        if 8<=age<=14: previous[order['productId']]+=q
        if 8<=age<=28: older[order['productId']]+=q
        valid.append((order,age))
    planned={p['productId'] for p in plans if p.get('status')=='待补货'}
    stock=[];growth=[];margin=[]
    for product in products:
        if product['status']!='在售': continue
        pid=product['id'];r=recent[pid];prev=previous[pid]
        daily=.65*r/7+.35*older[pid]/21
        enough=r+older[pid]>=3
        coverage=product['stock']/daily if daily>0 else None
        if product['stock']==0 or (enough and coverage is not None and coverage<=7) or (not enough and product['stock']<=3):
            target=math.ceil(daily*14) if enough else 10
            stock.append({'id':pid,'name':product['name'],'stock':product['stock'],'version':product['version'],'sold7':r,'dailyDemand':round(daily,2),'coverageDays':round(coverage,1) if coverage is not None else None,'suggestedQuantity':max(1,target-product['stock']),'confidence':'销售样本充足' if enough else '样本不足，采用低库存阈值','hasPlan':pid in planned})
        if prev>=3 and r>=5 and r/prev>=1.5:
            growth.append({'id':pid,'name':product['name'],'previous7':prev,'recent7':r,'growthPercent':round((r/prev-1)*100),'stock':product['stock']})
            related=[(o,a) for o,a in valid if o['productId']==pid and 1<=a<=14]
            # No costs, no profit claim. Current product cost cannot replace historical cost.
            if related and all(isinstance(o.get('unitCost'),(int,float)) and o['unitCost']>=0 for o,a in related):
                before=sum(o['amount']-o['unitCost']*o.get('quantity',1) for o,a in related if 8<=a<=14)
                after=sum(o['amount']-o['unitCost']*o.get('quantity',1) for o,a in related if 1<=a<=7)
                if before>0 and after<before*.9: margin.append({'id':pid,'name':product['name'],'previousGrossProfit':round(before,2),'recentGrossProfit':round(after,2),'note':'订单毛利，不含费用及税费'})
    overdue=[]
    for o in orders:
        when=ordered_at(o)
        if o['status']=='待发货' and when and when<=current:
            hours=(current-when).total_seconds()/3600
            if hours>SLA_HOURS: overdue.append({'id':o['id'],'productId':o['productId'],'name':o.get('productName','订单商品'),'hoursWaiting':round(hours),'hoursOverdue':round(hours-SLA_HOURS),'version':o['version']})
    stock.sort(key=lambda p:(p['hasPlan'],p['stock']>0,p['coverageDays'] if p['coverageDays'] is not None else 999,p['id']))
    overdue.sort(key=lambda p:-p['hoursOverdue'])
    growth.sort(key=lambda p:-p['growthPercent'])
    items=[]
    if stock:
        items.append({'id':'stock','priority':'优先处理','tone':'red','title':f'{len(stock)} 款商品存在缺货风险','reason':'结合近 7 天与前 21 天销量估计日需求；库存不足 7 天或已经缺货时提醒。低样本商品仅提示，不作销量预测。','next':'审核建议数量，确认后仅记录待补货计划，不自动增加库存。','action':'审核补货方案','rows':stock})
    if overdue:
        items.append({'id':'shipping','priority':'需要跟进','tone':'amber','title':f'{len(overdue)} 笔订单超过发货时限','reason':f'订单仍待发货，且下单已超过店铺配置的 {SLA_HOURS} 小时。优先处理等待最久的订单。','next':'核对商品与物流信息，优先处理等待最久的订单。','action':'查看并处理','rows':overdue})
    if margin:
        items.append({'id':'margin','priority':'经营建议','tone':'blue','title':f'{len(margin)} 款商品销量上升但毛利下降','reason':'最近两个完整 7 天窗口比较：销量增长至少 50%，订单毛利下降超过 10%，历史订单成本字段完整。','next':'核对成交价格与成本，先分析再决定是否调整售价。','action':'查看分析','rows':margin})
    elif growth:
        items.append({'id':'growth','priority':'经营建议','tone':'blue','title':f'{len(growth)} 款商品销量明显上升','reason':'比较最近两个完整 7 天：前期至少售出 3 件，本期至少 5 件，增长达到 50%。不把一天的偶然成交当作趋势。','next':'优先核对热销商品库存与商品信息；缺少完整成本记录，暂不推断利润变化。','action':'查看分析','rows':growth})
    return {'items':items,'coverage':{'products':len(products),'orders':len(orders)},'dataNotes':['销售与库存为项目经营数据；商品资料来自公开品牌页面。','缺少完整历史成本时，不生成利润下降提醒。'],'policy':{'stockCoverageDays':7,'targetStockDays':14,'shippingSlaHours':SLA_HOURS,'version':VERSION}}


class ScanState(TypedDict,total=False):
    products:list
    orders:list
    plans:list
    report:dict
    steps:list


def evaluate_rules(state):
    return {'report':analyze(state['products'],state['orders'],state['plans']),'steps':[{'stage':'读取商品、订单与已有计划','status':'completed'},{'stage':'计算库存覆盖、发货超时和销售变化','status':'completed'}]}


def explain(state):
    return {'report':{**state['report'],'steps':[*state['steps'],{'stage':'按紧急程度排序，生成可审核建议','status':'completed'}]}}


graph=StateGraph(ScanState)
graph.add_node('evaluate',evaluate_rules);graph.add_node('explain',explain)
graph.add_edge(START,'evaluate');graph.add_edge('evaluate','explain');graph.add_edge('explain',END)
workflow=graph.compile()


async def check(actor:Actor,force=False):
    if actor.role!='seller': fail(403,'仅商家可查看经营巡检')
    async with _locks.setdefault(actor.merchant,asyncio.Lock()):
        products=read_records(actor,'product');orders=read_records(actor,'order');plans=read_records(actor,'restock_plan')
        signature=hashlib.sha256(json.dumps({'version':VERSION,'rows':sorted((r['id'],r['version']) for r in [*products,*orders,*plans])},sort_keys=True).encode()).hexdigest()
        with transaction() as s:
            cached=s.get(Inspection,actor.merchant)
            if cached and not force and cached.signature==signature and (datetime.now(timezone.utc)-datetime.fromisoformat(cached.checked_at)).total_seconds()<CACHE_SECONDS:
                return {**cached.report,'checkedAt':cached.checked_at,'cached':True}
        result=await workflow.ainvoke({'products':products,'orders':orders,'plans':plans})
        checked=now();report=result['report']
        with transaction() as s:
            saved=s.get(Inspection,actor.merchant)
            if saved: saved.signature=signature;saved.checked_at=checked;saved.report=report
            else: s.add(Inspection(merchant=actor.merchant,signature=signature,checked_at=checked,report=report))
        return {**report,'checkedAt':checked,'cached':False}
