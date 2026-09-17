from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    reorder_threshold = Column(Integer, default=20) # Level 3: Re-order threshold
    
    batches = relationship("Batch", back_populates="medicine")

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"))
    batch_number = Column(String, index=True)
    quantity = Column(Integer, default=0)
    expiry_date = Column(Date, index=True)
    is_quarantined = Column(Boolean, default=False) # Level 1: Quarantine flag

    medicine = relationship("Medicine", back_populates="batches")

class Outbox(Base):
    __tablename__ = "outbox"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)
    payload = Column(String)
    processed = Column(Boolean, default=False)