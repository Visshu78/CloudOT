from sqlalchemy import Column, Integer, String, Float, Boolean
from database import Base

class EventLog(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(String)
    device_id = Column(String, index=True)
    zone = Column(String, index=True)
    attack_type = Column(String)
    confidence = Column(Float)
    severity = Column(String)
    verified = Column(Boolean)

class BlockChain(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_num = Column(Integer, unique=True, index=True)
    hash = Column(String)
    prev_hash = Column(String)
    timestamp = Column(String)
    event_count = Column(Integer)
    status = Column(String)
