from sqlalchemy import Column, Integer, String, Text, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from Modules.database import Base


class TonTransaction(Base):
    __tablename__ = 'tontransactions'

    id = Column(Integer, primary_key=True, index=True)
    src = Column(String, index=True)
    dest = Column(String, index=True)
    value_coins = Column(BigInteger)
    ihr_fee = Column(BigInteger)
    fwd_fee = Column(BigInteger)
    created_lt = Column(BigInteger)
    created_at = Column(BigInteger)
    status = Column(Integer, default=0)
    unixtime = Column(BigInteger, nullable=True)

    contract_data = relationship("ContractData", back_populates="tontransaction")

    def __init__(self, src, dest, value_coins, ihr_fee, fwd_fee, created_lt, created_at):
        self.src = src
        self.dest = dest
        self.value_coins = value_coins
        self.ihr_fee = ihr_fee
        self.fwd_fee = fwd_fee
        self.created_lt = created_lt
        self.created_at = created_at





class ContractData(Base):
    __tablename__ = 'contract_data'

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey('tontransactions.id'), nullable=False)
    src_address = Column(String, nullable=True)
    dest_address = Column(String, nullable=True)
    src_code = Column(Text, nullable=True)
    src_data = Column(Text, nullable=True)
    dest_code = Column(Text, nullable=True)
    dest_data = Column(Text, nullable=True)
    status = Column(Integer, default=0)
    unixtime = Column(BigInteger, nullable=True)

    tontransaction = relationship("TonTransaction", back_populates="contract_data")