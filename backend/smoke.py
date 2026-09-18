"""Explicit opt-in live model smoke: python -m backend.smoke (running API required)."""
import time
import httpx


def main():
    with httpx.Client(base_url="http://127.0.0.1:8000",timeout=20) as c:
        for role,prompt in [("buyer","查询我的耳机订单物流，不要修改任何数据。"),("seller","分析最近7天的销售情况，并列出低库存商品。不要修改数据。")]:
            token=c.post(f"/api/auth/dev/{role}").json()["token"]
            headers={"Authorization":"Bearer "+token}
            response=c.post("/api/runs",headers=headers,json={"text":prompt})
            response.raise_for_status();run_id=response.json()["id"]
            for _ in range(90):
                run=c.get(f"/api/runs/{run_id}",headers=headers).json()
                if run["status"] not in ("queued","running"): break
                time.sleep(2)
            print({"role":role,"status":run["status"],"steps":[e["stage"] for e in run["events"]],"answer":run["answer"],"error":run["meta"].get("errorCode")},flush=True)
            assert run["status"]=="completed"


if __name__=="__main__": main()
