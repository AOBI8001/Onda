import asyncio
import hashlib
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from . import config, services
from .agent_runtime import execute_run, pending_proposals
from .db import AuthSession, Feedback, Message, Proposal, Run, RunEvent, Thread, now, transaction, uid
from .events import run_view
from .schemas import ActionInput, Actor, ChatInput, Decision, FeedbackInput, ProductInput
from .seed import seed

tasks=set()


def launch(run_id,resume=False):
    task=asyncio.create_task(execute_run(run_id,resume))
    tasks.add(task);task.add_done_callback(tasks.discard)


@asynccontextmanager
async def lifespan(app):
    seed()
    # In-flight model calls cannot safely be replayed automatically after a crash.
    # Persisted approval states remain resumable; unfinished queries can be retried.
    with transaction() as s:
        for run in s.scalars(select(Run).where(Run.status.in_(["queued","running"]))):
            pending=s.scalar(select(Proposal.id).where(Proposal.run_id==run.id,Proposal.status=="pending"))
            run.status="awaiting_approval" if pending else "failed"
            run.answer="服务重启，已保存进度。待确认操作未自动执行。"
    yield
    for task in tasks: task.cancel()
    if tasks: await asyncio.gather(*tasks,return_exceptions=True)


app=FastAPI(title="Onda API",version="0.2.0",lifespan=lifespan)


@app.middleware("http")
async def local_boundary(request:Request, call_next):
    from starlette.responses import JSONResponse
    origin=request.headers.get("origin")
    if origin and origin not in ("http://127.0.0.1:5173","http://localhost:5173","http://127.0.0.1:8000"):
        return JSONResponse({"detail":"不允许的请求来源"},status_code=403)
    response=await call_next(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response


def actor(authorization: str | None=Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "): services.fail(401,"需要有效身份")
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    with transaction() as s:
        session=s.get(AuthSession,digest)
        if not session or session.expires < now(): services.fail(401,"会话已过期")
        return Actor(id=session.actor,role=session.role,merchant=session.merchant)


def owned_run(s,who,run_id):
    run=s.get(Run,run_id)
    if not run or run.actor!=who.id or run.role!=who.role or run.merchant!=who.merchant: services.fail(404,"未找到任务")
    return run


@app.get("/api/health")
def health():
    return {"status":"ok","model":config.MODEL,"modelConfigured":bool(config.API_KEY),"developmentAuth":config.DEV_MODE}


@app.post("/api/auth/dev/{role}")
def dev_auth(role:Literal["buyer","seller"],request:Request):
    if not config.DEV_MODE or request.client.host not in ("127.0.0.1","::1"): services.fail(403,"开发身份仅允许本机使用；正式部署需接入身份认证")
    token=secrets.token_urlsafe(40)
    with transaction() as s:
        s.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),actor=f"{role}-001",role=role,merchant="merchant-onda",expires=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()))
    return {"token":token}


@app.get("/api/state")
def get_state(who:Actor=Depends(actor)): return services.state(who)


@app.get("/api/analytics")
def get_analytics(days:int=30,who:Actor=Depends(actor)): return services.analytics(who,days)


@app.post("/api/products")
def new_product(data:ProductInput,who:Actor=Depends(actor)): return services.create_product(who,data)


@app.post("/api/inspections")
async def inspect_business(force:bool=False,who:Actor=Depends(actor)):
    from .inspections import check
    return await check(who,force)


@app.post("/api/proposals")
def new_proposal(data:ActionInput,who:Actor=Depends(actor)): return services.propose(who,data)


@app.post("/api/proposals/{proposal_id}/decision")
async def decision(proposal_id:str,data:Decision,who:Actor=Depends(actor)):
    result=services.decide(who,proposal_id,data.approved)
    with transaction() as s:
        p=s.get(Proposal,proposal_id)
        if p.run_id:
            run=owned_run(s,who,p.run_id)
            pending=s.scalar(select(Proposal.id).where(Proposal.run_id==run.id,Proposal.status=="pending"))
            if not pending and run.status=="awaiting_approval":
                run.status="queued"
                launch(run.id,True)
    return result


@app.get("/api/threads")
def threads(who:Actor=Depends(actor)):
    with transaction() as s:
        rows=s.scalars(select(Thread).where(Thread.actor==who.id,Thread.role==who.role).order_by(Thread.created.desc()).limit(100)).all()
        result=[]
        for thread in rows:
            messages=s.scalars(select(Message).where(Message.thread_id==thread.id).order_by(Message.created)).all()
            runs=s.scalars(select(Run).where(Run.thread_id==thread.id).order_by(Run.created)).all()
            result.append({"id":thread.id,"title":thread.title,"created":thread.created,"messages":[{"id":m.id,"role":m.role,"text":m.text,"run_id":m.run_id,"created":m.created} for m in messages],"runs":[run_view(r) for r in runs]})
        return result


@app.post("/api/runs")
async def new_run(data:ChatInput,who:Actor=Depends(actor)):
    if not data.text.strip(): services.fail(422,"请输入问题")
    with transaction() as s:
        if data.thread_id:
            thread=s.get(Thread,data.thread_id)
            if not thread or thread.actor!=who.id or thread.role!=who.role: services.fail(404,"未找到对话")
            active=s.scalar(select(Run.id).where(Run.thread_id==thread.id,Run.status.in_(["queued","running","awaiting_approval"])))
            if active: services.fail(409,"请先完成或拒绝当前待确认操作")
        else:
            thread=Thread(id=uid("TH-"),actor=who.id,role=who.role,title=data.text[:40])
            s.add(thread)
        run=Run(id=uid("RUN-"),actor=who.id,role=who.role,merchant=who.merchant,thread_id=thread.id,prompt=data.text,meta={})
        s.add(run)
        s.add(Message(id=uid("MSG-"),thread_id=thread.id,role="user",text=data.text,run_id=run.id))
        s.flush()
        result={"id":run.id,"thread_id":thread.id}
    launch(run.id)
    return result


@app.get("/api/runs/{run_id}")
def get_run(run_id:str,who:Actor=Depends(actor)):
    with transaction() as s: return run_view(owned_run(s,who,run_id))


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id:str,after:int=0,who:Actor=Depends(actor)):
    with transaction() as s: owned_run(s,who,run_id)
    async def stream():
        cursor=after
        for _ in range(1000):
            with transaction() as s:
                run=owned_run(s,who,run_id)
                rows=s.scalars(select(RunEvent).where(RunEvent.run_id==run_id,RunEvent.id>cursor).order_by(RunEvent.id)).all()
                status=run.status
            for event in rows:
                cursor=event.id
                yield f"id: {event.id}\nevent: step\ndata: {json.dumps({'id':event.id,**event.data},ensure_ascii=False)}\n\n"
            if status in ("completed","failed","awaiting_approval"):
                yield f"event: settled\ndata: {json.dumps({'status':status})}\n\n"
                return
            yield ": heartbeat\n\n"
            await asyncio.sleep(.35)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"X-Accel-Buffering":"no"})


@app.post("/api/runs/{run_id}/feedback")
def feedback(run_id:str,data:FeedbackInput,who:Actor=Depends(actor)):
    with transaction() as s:
        owned_run(s,who,run_id)
        s.add(Feedback(id=uid("FB-"),actor=who.id,run_id=run_id,rating=data.rating,note=data.note))
    return {"saved":True}
