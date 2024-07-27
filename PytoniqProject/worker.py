# PytoniqProject/worker.py
import asyncio
import logging
from pytoniq import LiteClient, Contract
from celery import Celery
from sqlalchemy.orm import Session
from datetime import datetime
from Modules.database import get_db
from Modules.models import ContractData, TonTransaction

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройка Celery
celery_app = Celery('worker',
                    broker='redis://redis:6379/0',
                    backend='redis://redis:6379/0')

# Конфигурация Celery
celery_app.conf.update(
    worker_prefetch_multiplier=1,
    task_annotations={'worker.process_address': {'rate_limit': '15/m'}}
)

client = LiteClient.from_mainnet_config(ls_i=14, trust_level=2, timeout=20)
is_client_connected = False

async def initialize_client():
    global is_client_connected
    if not is_client_connected:
        try:
            await client.connect()
            is_client_connected = True
        except Exception as e:
            print(f"Error connect: {e}")

async def fetch_contract_code_and_data(client, address):
    '''
    Главный метод для запроса смарт-контракта для dest и src.
    '''
    logger.info(f"Fetching contract code and data for address: {address}")
    try:
        contract = await Contract.from_address(client, address)
        if contract is None:
            logger.error(f"Failed to fetch contract for address: {address}. Contract is None.")
            return None, None
        await contract.update()
        code = getattr(contract, 'code', None)
        data = getattr(contract, 'data', None)
        logger.info(f"Fetched code and data for address: {address}")
        return code, data
    except Exception as e:
        logger.error(f"Error fetching contract code and data for address {address}: {e}")
        return None, None

@celery_app.task
def process_address(transaction_id, raw_address, user_friendly_address, is_src):
    '''
    Метод для обработки данных запроса смарт-контракта.
    '''
    global is_client_connected

    logger.info(f"Processing address for transaction_id: {transaction_id}, raw_address: {raw_address}, user_friendly_address: {user_friendly_address}, is_src: {is_src}")
    db: Session = next(get_db())

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(initialize_client())

    if not is_client_connected:
        loop.run_until_complete(initialize_client())

    logger.info(f"Fetching contract code and data for user-friendly address: {user_friendly_address}")
    code, data = loop.run_until_complete(fetch_contract_code_and_data(client, user_friendly_address))

    logger.info(f"Querying ContractData for transaction_id: {transaction_id}")
    contract_data = db.query(ContractData).filter_by(transaction_id=transaction_id).first()

    if not contract_data:
        logger.info(f"No existing ContractData found. Creating new entry for transaction_id: {transaction_id}")
        contract_data = ContractData(transaction_id=transaction_id)
        db.add(contract_data)

    if is_src:
        logger.info(f"Updating src_address, src_code, and src_data for transaction_id: {transaction_id}")
        contract_data.src_address = raw_address
        contract_data.src_code = code.data if code else None
        contract_data.src_data = data.data if data else None
    else:
        logger.info(f"Updating dest_address, dest_code, and dest_data for transaction_id: {transaction_id}")
        contract_data.dest_address = raw_address
        contract_data.dest_code = code.data if code else None
        contract_data.dest_data = data.data if data else None

    # Обновление полей в TonTransaction
    logger.info(f"Updating status and unixtime for transaction_id: {transaction_id}")
    transaction = db.query(TonTransaction).filter_by(id=transaction_id).first()
    if transaction:
        transaction.status = 1
        transaction.unixtime = int(datetime.utcnow().timestamp())

    logger.info(f"Committing changes to the database for transaction_id: {transaction_id}")
    db.commit()
    db.close()
    logger.info(f"Processing completed for transaction_id: {transaction_id}")
