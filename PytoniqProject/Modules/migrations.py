'''
Модуль предназначен для осуществления миграций,
моделей перечисленных в методе migrate.
'''
from sqlalchemy import inspect
from Modules.database import engine, Base
from Modules.models   import TonTransaction
from Modules.models   import ContractData

class Migrations:
    def __init__(self, base: Base):
        self.base = base

    def migrate(self):
        inspector = inspect(engine)

        # Проверяем и создаем таблицы для всех моделей
        for model in [TonTransaction, ContractData]:
            if not inspector.has_table(model.__tablename__):
                self.base.metadata.create_all(bind=engine)
                print(f"Table '{model.__tablename__}' created.")
            else:
                print(f"Table '{model.__tablename__}' already exists.")


def init_db():
    initializer = Migrations(Base)
    initializer.migrate()


if __name__ == "__main__":
    init_db()
