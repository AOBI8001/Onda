"""Real product catalog with synthetic, date-independent commerce fixtures."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from .db import Base, Record, engine, transaction, now

CATALOG=json.loads((Path(__file__).parent/'data'/'catalog.json').read_text(encoding='utf-8'))
CORE_ORDERS=('OD-Q7M2K9','OD-N4R8V1','OD-X6P3T5')
CORE_TICKETS=('TK-K8M2Q4','TK-N5V7R3','TK-P6X9C2','TK-H4J8W1')
LOCAL=timezone(timedelta(hours=8))


def stable_id(kind,key):
    return kind+'-'+uuid5(NAMESPACE_URL,'onda:'+str(key)).hex[:10].upper()


def product_data(product,index):
    return {**{k:v for k,v in product.items() if k!='id'},'stock':(3 if index==0 else 0 if index==1 else 8 if index==3 else 25+index*7%90),'status':'在售','sales':0,'updatedAt':now(),'dataOrigin':'品牌商品资料；库存与订单为合成经营数据'}


def order_data(product,age,status,index):
    current=datetime.now(LOCAL)
    when=(current-timedelta(days=age)).replace(hour=10,minute=0,second=0,microsecond=0)
    if when>current: when=current-timedelta(minutes=15)
    shipped=status not in ('待发货','已取消')
    return {'productId':product['id'],'productName':product['name'],'productImage':product['image'],'quantity':1,'date':when.date().isoformat(),'createdAt':when.isoformat(),'amount':product['price'],'status':status,'fulfillmentStatus':status,'refundStatus':None,'tracking':stable_id('SF','shipment-'+str(index)) if shipped else '—','shippedAt':(when+timedelta(days=1)).strftime('%Y-%m-%d %H:%M') if shipped else '尚未发货'}


def seed():
    Base.metadata.create_all(engine)
    with transaction() as s:
        existing=s.scalar(select(Record.id).limit(1))
    if existing:
        from .catalog_migration import migrate_legacy
        migrate_legacy()
        return
    with transaction() as s:
        for index,p in enumerate(CATALOG):
            s.add(Record(id=p['id'],kind='product',owner='seller-001',merchant='merchant-onda',data=product_data(p,index)))
        for i in range(63):
            if i<3:
                p=CATALOG[i];age=(0,2,6)[i];status=('待发货','运输中','已签收')[i]
            elif i<9:
                p=CATALOG[i+8];age=i;status='待发货'
            elif i<21:
                p=CATALOG[3];age=1+i%7;status='已签收'
            elif i<25:
                p=CATALOG[3];age=8+i%7;status='已签收'
            else:
                p=CATALOG[0 if i%3==0 else (i*7)%100];age=1+i%28;status='已取消' if i%13==0 else '已签收'
            s.add(Record(id=CORE_ORDERS[i] if i<3 else stable_id('OD','history-'+str(i)),kind='order',owner='buyer-001' if i<3 else f'buyer-{i+2:03}',merchant='merchant-onda',data=order_data(p,age,status,i)))
        descriptions=[('物流配送','查询订单物流进度。',CORE_ORDERS[1],'低'),('商品咨询','耳机如何连接手机？',CORE_ORDERS[0],'低'),('售后退款','咨询商品质量问题与售后处理。',CORE_ORDERS[2],'高'),('订单问题','尚未发货，咨询能否取消。',CORE_ORDERS[0],'高')]
        for i,(kind,text,oid,risk) in enumerate(descriptions):
            s.add(Record(id=CORE_TICKETS[i],kind='ticket',owner='buyer-001',merchant='merchant-onda',data={'user':'用户','phone':'—','type':kind,'description':text,'orderId':oid,'risk':risk,'status':'待处理','date':now(),'notes':[]}))
