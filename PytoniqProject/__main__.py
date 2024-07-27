import asyncio
from datetime import datetime
from pytoniq_core import BlockIdExt
from pytoniq import LiteClient
from pytoniq_core import Address
from pytoniq_core.boc.address import Address as core_Address
from Modules.block_scanner import BlockScanner

from sqlalchemy.orm import Session
from Modules.database import get_db, Base
from Modules.migrations import Migrations
from Modules.models import TonTransaction
from worker import celery_app

# celery -A worker.celery_app flower
# celery -A worker.celery_app worker --loglevel=info
# python __main__.py
# celery -A worker purge
# psql -U postgres -d postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
# redis-cli FLUSHALL
# psql -U postgres -d postgres -c "COPY (SELECT row_to_json(contract_data) FROM contract_data) TO STDOUT" > /var/lib/postgresql/data/contract_data.json

async def handle_block(block: BlockIdExt):
    '''
    Получает src и dest адреса транзакции,
    для получения смарт-контрактов на их основе,
    и записи полученных данных в таблицу 'contract_data'.
    '''

    if block.workchain == -1:  # skip masterchain blocks
        return

    transactions = await client.raw_get_block_transactions_ext(block)

    for transaction in transactions:
        src = getattr(transaction.in_msg.info, 'src', None)
        dest = getattr(transaction.in_msg.info, 'dest', None)

        src_address = Address(src) if isinstance(src, core_Address) else None
        dest_address = Address(dest) if isinstance(dest, core_Address) else None

        raw_src_address = src_address.to_str(is_user_friendly=False) if src_address else None
        raw_dest_address = dest_address.to_str(is_user_friendly=False) if dest_address else None
        user_friendly_src_address = src_address.to_str(is_user_friendly=True, is_bounceable=True, is_url_safe=True) if src_address else None
        user_friendly_dest_address = dest_address.to_str(is_user_friendly=True, is_bounceable=True, is_url_safe=True) if dest_address else None

        # Запись транзакции в таблицу
        db: Session = next(get_db())
        transaction_entry = TonTransaction(
            src=raw_src_address,
            dest=raw_dest_address,
            value_coins=transaction.in_msg.info.value_coins if getattr(transaction.in_msg.info, 'value_coins', None) else 0,
            ihr_fee=transaction.in_msg.info.ihr_fee if getattr(transaction.in_msg.info, 'ihr_fee', None) else 0,
            fwd_fee=transaction.in_msg.info.fwd_fee if getattr(transaction.in_msg.info, 'fwd_fee', None) else 0,
            created_lt=transaction.in_msg.info.created_lt if getattr(transaction.in_msg.info, 'created_lt', None) else 0,
            created_at=transaction.in_msg.info.created_at if getattr(transaction.in_msg.info, 'created_at', None) else 0,
            unixtime=int(datetime.utcnow().timestamp())
        )
        db.add(transaction_entry)
        db.commit()
        db.refresh(transaction_entry)

        # Создание задач для воркера
        if user_friendly_src_address:
            celery_app.send_task('worker.process_address',
                                 args=[transaction_entry.id, raw_src_address, user_friendly_src_address, True])
        if user_friendly_dest_address:
            celery_app.send_task('worker.process_address',
                                 args=[transaction_entry.id, raw_dest_address, user_friendly_dest_address, False])

        db.close()


client = LiteClient.from_mainnet_config(ls_i=14, trust_level=2, timeout=20)


async def main():
    try:
        initializer = Migrations(Base)
        initializer.migrate()

        await client.connect()
        await BlockScanner(client=client, block_handler=handle_block).run()

    except Exception as e:
        print(f"Error connect: {e}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
