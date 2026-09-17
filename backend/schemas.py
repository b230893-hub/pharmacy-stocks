from pydantic import BaseModel
from datetime import date
from typing import List, Optional

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class BatchCreate(BaseModel):
    batch_number: str
    quantity: int
    expiry_date: date

class BatchResponse(BaseModel):
    id: int
    batch_number: str
    quantity: int
    expiry_date: date
    class Config:
        from_attributes = True

class MedicineCreate(BaseModel):
    name: str
    description: str

class MedicineResponse(BaseModel):
    id: int
    name: str
    description: str
    total_unexpired_stock: int
    class Config:
        from_attributes = True

class DispenseRequest(BaseModel):
    quantity: int

class AlertResponse(BaseModel):
    batch_id: int
    medicine_name: str
    batch_number: str
    quantity: int
    expiry_date: date
    days_to_expiry: int