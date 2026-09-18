from sqlalchemy import select
from .db import Message, Proposal, Run, RunEvent, now, transaction, uid
from .services import proposal_view


def emit(run_id, stage, status="completed", detail=""):
    # Only curated public summaries; never serialize raw model reasoning or credentials.
    with transaction() as s:
        event=RunEvent(run_id=run_id,data={"stage":stage,"status":status,"detail":str(detail)[:1500]})
        s.add(event);s.flush()
        return event.id


def update_run(run_id, **values):
    with transaction() as s:
        run=s.get(Run,run_id)
        for k,v in values.items(): setattr(run,k,v)


def finish_run(run_id, answer, status="completed"):
    with transaction() as s:
        run=s.get(Run,run_id)
        run.answer=answer
        run.status=status
        s.add(Message(id=uid("MSG-"),thread_id=run.thread_id,role="assistant",text=answer,run_id=run_id))
    emit(run_id,"任务完成" if status=="completed" else "等待人工确认" if status=="awaiting_approval" else "任务未完成",status)


def run_view(run):
    with transaction() as s:
        events=s.scalars(select(RunEvent).where(RunEvent.run_id==run.id).order_by(RunEvent.id)).all()
        proposals=s.scalars(select(Proposal).where(Proposal.run_id==run.id)).all()
        return {"id":run.id,"thread_id":run.thread_id,"status":run.status,"answer":run.answer,"created":run.created,"meta":{k:v for k,v in run.meta.items() if k in ("intent","emotion","model","promptVersion","errorCode","durationMs","toolCalls")},"events":[{"id":e.id,**e.data,"created":e.created} for e in events],"proposals":[proposal_view(p) for p in proposals]}
