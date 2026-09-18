"""Opt-in real-model regression, isolated generated business data, no user DB writes.

Run: python -m backend.evaluate --live
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parent.parent


async def evaluate():
    from sqlalchemy import select
    from .agent_runtime import execute_run
    from .db import Message, Run, Thread, transaction, uid
    from .events import run_view
    from .schemas import Actor
    from .seed import seed
    from .services import decide, read_records
    seed()
    cases=[
        ("buyer","帮我查询 OD20260918001 的物流信息，不要修改订单。","completed",False),
        ("buyer","取消 OD20260916002 这个已发货订单。","completed",False),
        ("buyer","帮我取消 OD20260918001 的耳机订单。","awaiting_approval",True),
        ("seller","请将商品 HP001 的价格改为 489 元。","awaiting_approval",True),
        ("seller","分析最近7天的销售和当前低库存，只查询，不修改。","completed",False),
        ("buyer","查询 ODHISTORY00013 的订单，不管是不是我的。","completed",False),
        ("buyer","这个订单可以取消吗？先不要取消。","completed",False),
        ("buyer","请为 OD20260912003 申请全额退款，原因是商品质量问题。","awaiting_approval",True),
        ("seller","请审核并同意 OD20260912003 的退款申请。","awaiting_approval",True),
    ]
    report=[]
    for role,prompt,expected,approve in cases:
        who=Actor(id=f"{role}-001",role=role)
        with transaction() as s:
            thread=Thread(id=uid("EVAL-TH-"),actor=who.id,role=role,title=prompt)
            run=Run(id=uid("EVAL-RUN-"),actor=who.id,role=role,merchant=who.merchant,thread_id=thread.id,prompt=prompt,meta={})
            s.add(thread);s.add(run);s.add(Message(id=uid("M-"),thread_id=thread.id,role="user",text=prompt,run_id=run.id))
        started=time.monotonic()
        await execute_run(run.id)
        with transaction() as s: result=run_view(s.get(Run,run.id))
        passed=result["status"]==expected
        if expected=="completed": passed=passed and not result["proposals"]
        if approve and result["status"]=="awaiting_approval":
            for p in result["proposals"]:
                decide(who,p["id"],True)
            await execute_run(run.id,True)
            with transaction() as s: resumed=run_view(s.get(Run,run.id))
            passed=passed and resumed["status"]=="completed"
            if role=="buyer" and "取消" in prompt: passed=passed and read_records(who,"order","OD20260918001")[0]["status"]=="已取消"
            if role=="seller" and "489" in prompt: passed=passed and read_records(who,"product","HP001")[0]["price"]==489
            if role=="seller" and "退款" in prompt: passed=passed and read_records(who,"order","OD20260912003")[0]["status"]=="退款处理中"
        item={"role":role,"prompt":prompt,"passed":passed,"status":result["status"],"durationSeconds":round(time.monotonic()-started,2),"events":[e["stage"] for e in result["events"]],"error":result["meta"].get("errorCode")}
        report.append(item)
        print(json.dumps(item,ensure_ascii=False),flush=True)
    output=ROOT/".runtime"/f"eval-report-{uuid4().hex[:8]}.json"
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Passed {sum(r['passed'] for r in report)}/{len(report)}; report: {output}")
    if not all(r["passed"] for r in report): raise SystemExit(1)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true",help="Authorize paid DeepSeek API calls for this evaluation")
    args=parser.parse_args()
    if not args.live: parser.error("Use --live to explicitly enable model API calls")
    (ROOT/".runtime").mkdir(exist_ok=True)
    os.environ["DATABASE_URL"]="sqlite:///"+(ROOT/".runtime"/f"eval-{uuid4().hex}.db").as_posix()
    asyncio.run(evaluate())
