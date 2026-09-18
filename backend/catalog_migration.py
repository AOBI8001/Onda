"""One-time, backed-up migration of known legacy fixture products and identifiers.

Unrelated user-created products are preserved. Business history stays connected;
old purchase amounts and statuses are not reset. Backups remain local and ignored.
"""
from datetime import datetime, timezone
import copy
from pathlib import Path
import sqlite3
from sqlalchemy import select

from .db import Audit, Inspection, Message, Proposal, Record, Run, Thread, engine, transaction, uid

LEGACY_PRODUCTS=('HP001','CUP002','BLANKET003','LAMP004','KB005','PLANT006','SC001','SC002','SC003')


def migrate_legacy():
    from .seed import CATALOG, CORE_ORDERS, CORE_TICKETS, product_data, stable_id, order_data
    with transaction() as s:
        legacy=s.scalars(select(Record).where(Record.id.in_(LEGACY_PRODUCTS),Record.kind=='product')).all()
    if not legacy: return
    if engine.url.get_backend_name()!='sqlite': raise RuntimeError('Legacy catalog migration requires an explicit database backup on PostgreSQL')
    root=Path(__file__).resolve().parents[1]
    backup=root/'.runtime'/'backups'/f'pre-catalog-{uid()[:12]}.db'
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(engine.url.database) as source,sqlite3.connect(backup) as destination: source.backup(destination)
    mapping={old:CATALOG[i]['id'] for i,old in enumerate(LEGACY_PRODUCTS)}
    mapping.update(dict(zip(('OD20260918001','OD20260916002','OD20260912003'),CORE_ORDERS)))
    mapping.update({f'WD2026091800{i+1}':value for i,value in enumerate(CORE_TICKETS)})
    mapping.update({f'ODHISTORY{i:05}':stable_id('OD','history-'+str(i)) for i in range(3,63)})
    def rewrite(value):
        if isinstance(value,str):
            for old,new in mapping.items(): value=value.replace(old,new)
            return value
        if isinstance(value,list): return [rewrite(v) for v in value]
        if isinstance(value,dict): return {k:rewrite(v) for k,v in value.items()}
        return value
    lookup={p['id']:p for p in CATALOG}
    with transaction() as s:
        for old in s.scalars(select(Record).where(Record.id.in_(LEGACY_PRODUCTS),Record.kind=='product')).all(): s.delete(old)
        s.flush()
        for index,p in enumerate(CATALOG):
            if not s.get(Record,p['id']): s.add(Record(id=p['id'],kind='product',owner='seller-001',merchant='merchant-onda',data=product_data(p,index)))
        for record in s.scalars(select(Record).where(Record.kind!='product')).all():
            data=rewrite(copy.deepcopy(record.data))
            if record.kind=='order' and data.get('productId') in lookup:
                product=lookup[data['productId']]
                data['productName']=product['name'];data['productImage']=product['image']
            record.id=mapping.get(record.id,record.id);record.data=data;record.version+=1
        for proposal in s.scalars(select(Proposal)):
            proposal.target=rewrite(proposal.target);proposal.params=rewrite(proposal.params);proposal.result=rewrite(proposal.result)
            if proposal.status=='pending': proposal.status='rejected'
        for model,fields in ((Message,('text',)),(Thread,('title',)),(Run,('prompt','answer','meta')),(Audit,('data',))):
            for row in s.scalars(select(model)):
                for field in fields: setattr(row,field,rewrite(getattr(row,field)))
                if isinstance(row,Run) and row.status=='awaiting_approval':
                    row.status='completed';row.answer='商品目录已更新，旧待确认方案未执行。请重新发起操作。'
        for cached in s.scalars(select(Inspection)): s.delete(cached)
        # Add bounded synthetic operations scenarios; existing orders are unchanged.
        for i in range(22):
            p=CATALOG[12+i] if i<6 else CATALOG[3]
            age=3+i if i<6 else 1+i%7 if i<18 else 8+i%7
            data=order_data(p,age,'待发货' if i<6 else '已签收','attention-'+str(i))
            data['syntheticScenario']='catalog-attention-v1'
            s.add(Record(id=stable_id('OD','attention-'+str(i)),kind='order',owner='buyer-ops-fixture',merchant='merchant-onda',data=data))
    print(f'Catalog migrated; previous local database preserved at {backup}')


def refresh_source_metadata():
    """Explicit maintenance command; preserves live price, stock and listing status."""
    from .seed import CATALOG
    fields=('name','desc','features','brand','image','sourceUrl','sourceTitle','sourceVariant','sourcePrice','sourceCurrency','sourceCapturedAt','sourceImage','priceBasis')
    with transaction() as s:
        for product in CATALOG:
            record=s.get(Record,product['id'])
            if record:
                updated={**record.data,**{k:product[k] for k in fields}}
                if updated!=record.data: record.data=updated;record.version+=1
    print('Catalog source metadata refreshed; business price and inventory preserved.')


if __name__=='__main__':
    import sys
    if '--refresh-metadata' in sys.argv: refresh_source_metadata()
