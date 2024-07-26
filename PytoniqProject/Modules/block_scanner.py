import asyncio
from types import coroutine

from pytoniq_core.tlb.block import ExtBlkRef
from pytoniq.liteclient import LiteClient
from pytoniq_core.tl import BlockIdExt

class BlockScanner:

    def __init__(self,
                 client: LiteClient,
                 block_handler: coroutine):
        """
        Инициализация класса BlockScanner.

        :param client: LiteClient, объект для взаимодействия с сетью TON
        :param block_handler: функция-обработчик для новых блоков
        """
        self.client = client
        self.block_handler = block_handler
        self.shards_storage = {}  # Хранит информацию о просмотренных шард-блоках
        self.blks_queue = asyncio.Queue()  # Очередь для обработки блоков

    async def run(self, mc_seqno: int = None):
        if not self.client.inited:
            raise Exception('should init client first')  # Проверка на инициализацию клиента

        if mc_seqno is None:
            # Получение информации о мастерчейне и преобразование в BlockIdExt
            master_blk: BlockIdExt = self.mc_info_to_tl_blk(await self.client.get_masterchain_info())
        else:
            # Поиск блока по заданному seqno
            master_blk, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=mc_seqno)

        # Получение предыдущего блока
        master_blk_prev, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=master_blk.seqno - 1)

        # Получение информации обо всех шардах для предыдущего блока
        shards_prev = await self.client.get_all_shards_info(master_blk_prev)
        for shard in shards_prev:
            self.shards_storage[self.get_shard_id(shard)] = shard.seqno  # Сохранение информации о просмотренных шардах

        while True:
            await self.blks_queue.put(master_blk)  # Добавление текущего мастер-блока в очередь

            # Получение информации обо всех шардах для текущего блока
            shards = await self.client.get_all_shards_info(master_blk)
            for shard in shards:
                await self.get_not_seen_shards(shard)  # Получение новых шардов
                self.shards_storage[self.get_shard_id(shard)] = shard.seqno  # Обновление информации о просмотренных шардах

            while not self.blks_queue.empty():
                # Обработка блоков из очереди
                await self.block_handler(self.blks_queue.get_nowait())

            while True:
                # Проверка, достигли ли мы последнего блока мастерчейна
                if master_blk.seqno + 1 == self.client.last_mc_block.seqno:
                    master_blk = self.client.last_mc_block
                    break
                elif master_blk.seqno + 1 < self.client.last_mc_block.seqno:
                    master_blk, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=master_blk.seqno + 1)
                    break
                await asyncio.sleep(0.1)

    async def get_not_seen_shards(self, shard: BlockIdExt):
        # Проверка, был ли уже просмотрен данный шард
        if self.shards_storage.get(self.get_shard_id(shard)) == shard.seqno:
            return

        # Получение полного заголовка блока
        full_blk = await self.client.raw_get_block_header(shard)
        prev_ref = full_blk.info.prev_ref

        if prev_ref.type_ == 'prev_blk_info':
            # Обработка одного предыдущего блока
            prev: ExtBlkRef = prev_ref.prev
            prev_shard = self.get_parent_shard(shard.shard) if full_blk.info.after_split else shard.shard
            await self.get_not_seen_shards(BlockIdExt(
                workchain=shard.workchain, seqno=prev.seqno, shard=prev_shard,
                root_hash=prev.root_hash, file_hash=prev.file_hash
            ))
        else:
            # Обработка двух предыдущих блоков
            prev1: ExtBlkRef = prev_ref.prev1
            prev2: ExtBlkRef = prev_ref.prev2
            await self.get_not_seen_shards(BlockIdExt(
                workchain=shard.workchain, seqno=prev1.seqno, shard=self.get_child_shard(shard.shard, left=True),
                root_hash=prev1.root_hash, file_hash=prev1.file_hash
            ))
            await self.get_not_seen_shards(BlockIdExt(
                workchain=shard.workchain, seqno=prev2.seqno, shard=self.get_child_shard(shard.shard, left=False),
                root_hash=prev2.root_hash, file_hash=prev2.file_hash
            ))

        await self.blks_queue.put(shard)  # Добавление блока в очередь

    def get_child_shard(self, shard: int, left: bool) -> int:
        # Получение дочернего шарда
        x = self.lower_bit64(shard) >> 1
        if left:
            return self.simulate_overflow(shard - x)
        return self.simulate_overflow(shard + x)

    def get_parent_shard(self, shard: int) -> int:
        # Получение родительского шарда
        x = self.lower_bit64(shard)
        return self.simulate_overflow((shard - x) | (x << 1))

    @staticmethod
    def simulate_overflow(x) -> int:
        # Симуляция переполнения
        return (x + 2**63) % 2**64 - 2**63

    @staticmethod
    def lower_bit64(num: int) -> int:
        # Получение младшего бита 64-битного числа
        return num & (~num + 1)

    @staticmethod
    def mc_info_to_tl_blk(info: dict):
        # Преобразование информации о мастерчейне в BlockIdExt
        return BlockIdExt.from_dict(info['last'])

    @staticmethod
    def get_shard_id(blk: BlockIdExt):
        # Получение идентификатора шарда
        return f'{blk.workchain}:{blk.shard}'

async def handle_block(block: BlockIdExt):
    if block.workchain == -1:  # Пропуск мастерчейн блоков
        return
    print(block)  # Вывод информации о блоке
    transactions = await client.raw_get_block_transactions_ext(block)  # Получение транзакций блока
    print(f"{len(transactions)=}")  # Вывод количества транзакций
    # for transaction in transactions:
    #     print(transaction.in_msg)  # Вывод информации о транзакциях (закомментировано)

# Создание клиента для подключения к mainnet с заданными параметрами
client = LiteClient.from_mainnet_config(ls_i=14, trust_level=2, timeout=20)

async def main():
    await client.connect()  # Подключение клиента
    await client.reconnect()  # Переподключение клиента
    # Создание и запуск BlockScanner с клиентом и обработчиком блоков
    await BlockScanner(client=client, block_handler=handle_block).run()

if __name__ == '__main__':
    asyncio.run(main())  # Запуск main функции
