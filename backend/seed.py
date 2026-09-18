"""Small reproducible fixtures; never read the original DataCo dataset."""
from datetime import date, timedelta
from sqlalchemy import select
from .db import Base, Record, engine, transaction

PRODUCTS = [
    ("HP001", "Onda 无线蓝牙耳机", "沉浸音质，静享生活", 499, 120, "生活电器", "在售", [383,368,382,165]),
    ("CUP002", "Onda 保温随行杯", "一杯温暖，陪伴每一天", 229, 85, "居家日用", "在售", [788,369,383,164]),
    ("BLANKET003", "Onda 轻柔云感毯", "柔软舒适，治愈日常", 299, 62, "居家日用", "在售", [383,636,382,155]),
    ("LAMP004", "Onda 护眼桌面灯", "柔和之光，专注更久", 399, 8, "办公学习", "下架", [1197,369,394,164]),
    ("KB005", "Onda 无线轻薄键盘", "流畅输入，灵感不停", 349, 50, "办公学习", "在售", [788,636,383,155]),
    ("PLANT006", "Onda 治愈绿植盆栽", "一抹绿意，让空间更温柔", 199, 0, "居家日用", "草稿", [1197,636,394,155]),
    ("SC001", "晨雾香氛机", "清新香调，简约设计", 259, 24, "居家日用", "在售", [568,405,226,148]),
    ("SC002", "山野檀香香薰蜡烛", "自然木质香，礼盒包装", 189, 6, "居家日用", "在售", [809,405,227,148]),
    ("SC003", "云屿无火香薰", "清新花果香，适合送礼", 269, 32, "居家日用", "在售", [1049,405,229,148]),
]


def seed():
    Base.metadata.create_all(engine)
    with transaction() as s:
        if s.scalar(select(Record.id).limit(1)):
            return
        for pid, name, desc, price, stock, category, status, crop in PRODUCTS:
            s.add(Record(id=pid, kind="product", owner="seller-001", merchant="merchant-onda", data={"name":name,"desc":desc,"price":price,"stock":stock,"category":category,"status":status,"crop":crop,"source":"消费者Onda.png" if pid.startswith("SC") else "消费者商品页.png","sales":0}))
        today = date.today()
        for i in range(63):
            core = i < 3
            pid = PRODUCTS[i % len(PRODUCTS)][0]
            age = [0,2,6][i] if core else 7 + i % 24
            ordered = today - timedelta(days=age)
            status = ["待发货","运输中","已签收"][i] if core else ("已取消" if i % 13 == 0 else "已签收")
            oid = ["OD20260918001","OD20260916002","OD20260912003"][i] if core else f"ODHISTORY{i:05}"
            shipped = status not in ("待发货","已取消")
            s.add(Record(id=oid,kind="order",owner="buyer-001" if core else f"buyer-{i+2:03}",merchant="merchant-onda",data={"productId":pid,"productName":PRODUCTS[i % len(PRODUCTS)][1],"quantity":1,"date":ordered.isoformat(),"amount":PRODUCTS[i % len(PRODUCTS)][3],"status":status,"fulfillmentStatus":status,"refundStatus":None,"tracking":f"SF13800138{i:04}" if shipped else "—","shippedAt":f"{ordered + timedelta(days=1)} 10:30" if shipped else "尚未发货"}))
        descriptions = [("物流配送","查询随行杯订单的物流进度。","OD20260916002","低"),("商品咨询","耳机怎么连接手机？","OD20260918001","低"),("售后退款","云感毯有质量问题，咨询售后处理。","OD20260912003","高"),("订单问题","耳机还没发货，咨询能否取消。","OD20260918001","高")]
        for i,(kind,text,oid,risk) in enumerate(descriptions):
            s.add(Record(id=f"WD2026091800{i+1}",kind="ticket",owner="buyer-001",merchant="merchant-onda",data={"user":"用户","phone":"—","type":kind,"description":text,"orderId":oid,"risk":risk,"status":"待处理","date":today.isoformat(),"notes":[]}))
