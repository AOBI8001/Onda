"""Two orchestrators, one authorized tool/service layer.

Model reasoning stays internal. UI receives only curated execution events.
"""
import asyncio
import json
import time
import traceback
from typing import TypedDict

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunConfig, RunContextWrapper, Runner, RunState, function_tool, set_tracing_disabled
from agents.tool_context import ToolContext
from fastapi import HTTPException
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from openai import AsyncOpenAI, AuthenticationError, RateLimitError, APITimeoutError
from pydantic import ValidationError
from sqlalchemy import select

from .config import API_KEY, BASE_URL, MODEL, MODEL_TIMEOUT, PROMPT_VERSION, RUNTIME
from .db import Message, Proposal, Run, transaction
from .events import emit, finish_run, update_run
from .policies import POLICIES
from .prompts import INTENT_PROMPT, SYSTEM
from .schemas import ActionInput, Actor
from .services import analytics, create_ticket, fail, proposal_view, propose, read_records

set_tracing_disabled(True)  # No third-party trace export or accidental secret disclosure.


def client():
    if not API_KEY:
        raise RuntimeError("MODEL_NOT_CONFIGURED")
    return AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=MODEL_TIMEOUT, max_retries=1)


def encode(value):
    return json.dumps(value,ensure_ascii=False,default=str)


def pending_proposals(run_id, pending_only=False):
    with transaction() as s:
        rows=s.scalars(select(Proposal).where(Proposal.run_id==run_id)).all()
        return [proposal_view(p) for p in rows if not pending_only or p.status=="pending"]


def messages_for(run):
    with transaction() as s:
        rows=s.scalars(select(Message).where(Message.thread_id==run.thread_id).order_by(Message.created.desc()).limit(16)).all()
        return [{"role":m.role,"content":m.text[:5000]} for m in reversed(rows)]


def tools_for(actor, run_id):
    def record(label, result):
        emit(run_id,label,"completed")
        return encode(result)

    @function_tool(strict_mode=False)
    async def search_products(query: str = "", max_price: float = 100000, offset: int = 0) -> str:
        """按名称、型号、品牌或类别查询真实商品目录。最高单价为人民币项目售价。空关键词查全部；每页20条，nextOffset用于下一页。来源美元报价不是人民币售价。"""
        items=[p for p in read_records(actor,"product",query) if p["price"] <= max_price]
        offset=max(0,offset)
        fields=('id','name','desc','features','brand','category','price','currency','stock','status','version','sourceUrl','sourcePrice','sourceCurrency','priceBasis')
        return record("查询商品与库存",{'total':len(items),'items':[{k:p[k] for k in fields if k in p} for p in items[offset:offset+20]],'nextOffset':offset+20 if offset+20<len(items) else None})

    @function_tool(strict_mode=False)
    async def lookup_orders(query: str = "", offset: int = 0) -> str:
        """查询有权访问的订单和物流，支持订单号、商品名、状态。每页30条，nextOffset用于下一页。不得猜测对象。"""
        items=read_records(actor,'order',query);offset=max(0,offset)
        return record('查询订单与物流',{'total':len(items),'items':items[offset:offset+30],'nextOffset':offset+30 if offset+30<len(items) else None})

    @function_tool(strict_mode=False)
    async def lookup_policy(query: str = "") -> str:
        """查询取消、退款、物流等有效业务规则，引用规则而不是编造承诺。"""
        matches=[p for p in POLICIES if not query or query in p["title"] or query in p["text"]]
        return record("核对业务规则",matches or POLICIES)

    @function_tool(strict_mode=False)
    async def lookup_tickets(query: str = "") -> str:
        """查询当前身份可访问的工单及处理记录。"""
        return record("查询工单处理进度",read_records(actor,"ticket",query)[:50])

    @function_tool(strict_mode=False)
    async def sales_overview(days: int = 30) -> str:
        """商家专用：查询最近 1~90 天销售额、订单、热销商品、低库存和待处理工单。"""
        result=analytics(actor,days)
        result['topProducts']=[{k:p[k] for k in ('id','name','price','sales','stock')} for p in result['topProducts'][:10]]
        result['lowStock']=[{k:p[k] for k in ('id','name','price','stock')} for p in result['lowStock']]
        return record("计算核心经营指标",result)

    @function_tool(strict_mode=False)
    async def inspect_operations() -> str:
        """商家专用，只读自动巡检：库存覆盖、超时发货、销售趋势，返回有证据的今日关注和可审核补货建议。"""
        from .inspections import check
        return record('读取今日经营巡检',await check(actor))

    @function_tool(strict_mode=False)
    async def propose_change(action: str, target: str, params_json: str = "{}") -> str:
        """仅为用户明确要求的修改生成待人工确认方案。action: cancel_order/request_refund/approve_refund/reject_refund/ship_order/edit_product/set_product_status/close_ticket/update_ticket/plan_restock。
        target 必须是查询到的完整业务 ID。params_json: 取消和同意退款{}；申请/拒绝退款{"reason":"原因"}；发货{"tracking":"单号","shippedAt":"日期时间"}；商品修改可用 name/desc/price/stock/category；上下架{"status":"在售或下架"}；工单{"note":"处理说明"}；补货计划{"quantity":正整数}，只记录计划、不改变库存、不采购。生成方案不代表已执行。
        """
        try:
            payload=ActionInput(action=action,target=target,params=json.loads(params_json))
            p=propose(actor,payload,run_id)
            return record("生成高风险操作方案",p)
        except (ValueError,ValidationError):
            return encode({"error":"参数格式不合法，请核对工具契约"})
        except HTTPException as e:
            return record("操作条件检查未通过",{"error":e.detail})

    @function_tool(strict_mode=False,needs_approval=True)
    async def confirm_proposal(proposal_id: str) -> str:
        """消费者生成方案后调用此工具暂停，等待人确认。不能自行批准。返回服务端审批结果，不直接写业务数据。"""
        with transaction() as s:
            p=s.get(Proposal,proposal_id)
            if not p or p.actor!=actor.id or p.run_id!=run_id: return encode({"error":"无权访问审批"})
            if p.status != "executed": return encode({"error":"没有经过服务端确认，不能执行"})
            return record("核对已确认操作结果",proposal_view(p))

    @function_tool(strict_mode=False)
    async def open_support_ticket(order_id: str, description: str) -> str:
        """用户明确要求转人工或创建工单后使用。创建工单不执行退款、赔偿或取消。"""
        try:
            return record("创建人工服务工单",create_ticket(actor,order_id,description))
        except HTTPException as e:
            return encode({"error":e.detail})

    result=[search_products,lookup_orders,lookup_policy,lookup_tickets,propose_change,open_support_ticket]
    if actor.role=="seller": result.extend([sales_overview,inspect_operations])
    else: result.append(confirm_proposal)
    return result


async def classify(run, api):
    emit(run.id,"理解意图与服务需求","running")
    response=await api.chat.completions.create(model=MODEL,messages=[{"role":"system","content":INTENT_PROMPT},*messages_for(run)[-5:]],response_format={"type":"json_object"},max_tokens=400,extra_body={"thinking":{"type":"disabled"}})
    try:
        raw=json.loads(response.choices[0].message.content or "{}")
        intents=raw.get("intents",[])
        allowed={"商品咨询","订单查询","物流查询","取消订单","申请退款","经营分析","库存分析","商品管理","工单管理","其他"}
        emotion=raw.get("emotion","无法确定")
        result={"intent":[i for i in intents if i in allowed] if isinstance(intents,list) else [],"emotion":emotion if emotion in ("平静","困惑","着急","不满","无法确定") else "无法确定"}
    except (ValueError,TypeError): result={"intent":["其他"],"emotion":"无法确定"}
    with transaction() as s:
        r=s.get(Run,run.id);r.meta={**r.meta,**result}
    emit(run.id,"理解意图与服务需求","completed","、".join(result["intent"]) or "继续核对具体需求")
    return result


def consumer_agent(actor,run_id,api):
    return Agent(name="OndaConsumer",instructions=SYSTEM+"\n你服务的是消费者。生成方案后调用 confirm_proposal 等待人工确认；确认之外不要继续执行其他修改。",model=OpenAIChatCompletionsModel(model=MODEL,openai_client=api),model_settings=ModelSettings(max_tokens=1800,parallel_tool_calls=False,extra_body={"thinking":{"type":"disabled"}}),tools=tools_for(actor,run_id))


async def run_consumer(run,actor,api,resume=False):
    agent=consumer_agent(actor,run.id,api)
    if resume and run.meta.get("sdkState"):
        saved=await RunState.from_json(agent,run.meta["sdkState"])
        for item in saved.get_interruptions():
            raw=item.raw_item
            args=json.loads(raw.get("arguments","{}") if isinstance(raw,dict) else raw.arguments)
            proposal_id=args.get("proposal_id")
            p=next((p for p in pending_proposals(run.id) if p["id"]==proposal_id),None)
            if p and p["status"]=="executed": saved.approve(item)
            else: saved.reject(item)
        incoming=saved
    elif resume:
        finish_run(run.id,"操作审核已结束。"+"；".join(f"{p['title']}：{'已完成' if p['status']=='executed' else '未执行'}" for p in pending_proposals(run.id)))
        return
    else: incoming=messages_for(run)
    emit(run.id,"消费者助手处理请求","running")
    result=await Runner.run(agent,incoming,max_turns=10,run_config=RunConfig(tracing_disabled=True))
    if result.interruptions:
        with transaction() as s:
            r=s.get(Run,run.id);r.meta={**r.meta,"sdkState":result.to_state().to_json()}
    waiting=pending_proposals(run.id,True)
    if waiting:
        finish_run(run.id,"已生成操作方案，请核对下方对象和变更内容。只有确认后才会执行。","awaiting_approval")
    else: finish_run(run.id,str(result.final_output or "本次请求已处理，请查看执行详情。"))


class MerchantState(TypedDict,total=False):
    run_id: str
    actor: dict
    messages: list
    answer: str


async def merchant_analysis(state):
    actor=Actor.model_validate(state["actor"])
    run_id=state["run_id"]
    tools=tools_for(actor,run_id)
    lookup={t.name:t for t in tools}
    schemas=[{"type":"function","function":{"name":t.name,"description":t.description,"parameters":t.params_json_schema}} for t in tools]
    messages=[{"role":"system","content":SYSTEM+"\n你服务的是商家。先读取数据再分析；创建修改方案后停止并等待审批。"},*state["messages"]]
    emit(run_id,"商家分析与工具编排","running")
    async with client() as api:
        for _ in range(8):
            response=await api.chat.completions.create(model=MODEL,messages=messages,tools=schemas,parallel_tool_calls=False,max_tokens=2000,extra_body={"thinking":{"type":"disabled"}})
            message=response.choices[0].message
            if not message.tool_calls:
                return {"answer":message.content or "已完成数据查询。"}
            messages.append({"role":"assistant","content":message.content or "","tool_calls":[t.model_dump(exclude_none=True) for t in message.tool_calls]})
            for call in message.tool_calls:
                tool=lookup.get(call.function.name)
                output=await tool.on_invoke_tool(ToolContext(context=None,tool_name=call.function.name,tool_call_id=call.id,tool_arguments=call.function.arguments),call.function.arguments) if tool else encode({"error":"不允许的工具"})
                messages.append({"role":"tool","tool_call_id":call.id,"content":output})
            if pending_proposals(run_id,True):
                return {"answer":"已生成操作方案。请核对对象和变更内容，确认后执行。"}
    raise RuntimeError("TOOL_LIMIT")


def merchant_review(state):
    pending=pending_proposals(state["run_id"],True)
    if pending:
        interrupt({"proposal_ids":[p["id"] for p in pending]})
        # On replay never trust resume payload to authorize a write.
        if pending_proposals(state["run_id"],True): raise RuntimeError("APPROVAL_PENDING")
    decisions=pending_proposals(state["run_id"])
    return {"answer":state["answer"] if not decisions else "审核结果："+"；".join(f"{p['title']}：{'已完成' if p['status']=='executed' else '未执行'}" for p in decisions)}


async def run_merchant(run,actor,resume=False):
    async with AsyncSqliteSaver.from_conn_string(str(RUNTIME/"merchant-checkpoints.db")) as saver:
        graph=StateGraph(MerchantState)
        graph.add_node("analysis",merchant_analysis)
        graph.add_node("review",merchant_review)
        graph.add_edge(START,"analysis");graph.add_edge("analysis","review");graph.add_edge("review",END)
        compiled=graph.compile(checkpointer=saver)
        value=Command(resume=True) if resume else {"run_id":run.id,"actor":actor.model_dump(),"messages":messages_for(run)}
        result=await compiled.ainvoke(value,{"configurable":{"thread_id":run.id}})
        finish_run(run.id,result.get("answer","正在等待人工确认。"),"awaiting_approval" if result.get("__interrupt__") else "completed")


async def execute_run(run_id,resume=False):
    start=time.monotonic()
    with transaction() as s:
        run=s.get(Run,run_id)
        actor=Actor(id=run.actor,role=run.role,merchant=run.merchant)
        run.status="running"
        run.meta={**run.meta,"model":MODEL,"promptVersion":PROMPT_VERSION}
    try:
        async with asyncio.timeout(180):
            async with client() as api:
                if not resume: await classify(run,api)
                if actor.role=="buyer": await run_consumer(run,actor,api,resume)
                else: await run_merchant(run,actor,resume)
    except Exception as exc:
        code="AUTH_FAILED" if isinstance(exc,AuthenticationError) else "RATE_LIMIT" if isinstance(exc,RateLimitError) else "TIMEOUT" if isinstance(exc,(TimeoutError,APITimeoutError)) else "RUN_FAILED"
        # No exception repr: provider error bodies can contain sensitive request data.
        with transaction() as s:
            r=s.get(Run,run_id);r.meta={**r.meta,"errorCode":code,"errorType":type(exc).__name__,"errorFrames":[{"file":f.filename.rsplit("/",1)[-1].rsplit("\\",1)[-1],"line":f.lineno,"function":f.name} for f in traceback.extract_tb(exc.__traceback__)[-6:]]}
        waiting=pending_proposals(run_id,True)
        finish_run(run_id,"已生成待确认方案，但后续模型处理未完成。请核对方案后决定。" if waiting else "本次处理未完成，请稍后重试或创建人工工单。未确认的业务操作不会执行。", "awaiting_approval" if waiting else "failed")
    finally:
        with transaction() as s:
            r=s.get(Run,run_id);r.meta={**r.meta,"durationMs":round((time.monotonic()-start)*1000)}
