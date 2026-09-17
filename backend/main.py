import re
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta, datetime
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import List, Dict, Any
import json

import models, schemas, database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="FEFO Pharmacy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "fefo-super-secret-key-production"
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- HELPER FUNCTIONS ---
def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": date.today() + timedelta(days=1)}) 
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def parse_date(date_str):
    if not date_str: return None
    try: return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except ValueError: pass
    try: return datetime.strptime(str(date_str).strip(), "%d/%m/%Y").date()
    except ValueError: pass
    return None

def parse_qty(qty_str):
    if isinstance(qty_str, int): return qty_str
    if not qty_str: return None
    match = re.search(r'\d+', str(qty_str))
    return int(match.group()) if match else None

# --- NEW GRADING ENDPOINTS ---

@app.post("/clock")
def run_daily_job(db: Session = Depends(database.get_db)):
    """Level 1 (T2): Flags 7-day expirations and quarantines expired stock."""
    today = date.today()
    seven_days = today + timedelta(days=7)

    expired_batches = db.query(models.Batch).filter(
        models.Batch.expiry_date <= today,
        models.Batch.is_quarantined == False
    ).all()

    for batch in expired_batches:
        batch.is_quarantined = True

    expiring_count = db.query(models.Batch).filter(
        models.Batch.expiry_date > today,
        models.Batch.expiry_date <= seven_days,
        models.Batch.is_quarantined == False,
        models.Batch.quantity > 0
    ).count()

    db.commit()
    return {
        "quarantined_count": len(expired_batches),
        "expiring_within_7_days": expiring_count
    }

@app.post("/import")
def import_messy_batches(payload: List[Dict[str, Any]], db: Session = Depends(database.get_db)):
    """Level 2 (T4): Imports messy data, handling nulls, string parsing, formats, and duplicates."""
    imported = 0
    deduped = 0
    rejected = 0
    seen_in_payload = set()

    for row in payload:
        med_name = row.get("medicine_name")
        batch_no = row.get("batch_number")
        raw_qty = row.get("quantity")
        raw_date = row.get("expiry_date")

        if not med_name or not batch_no or raw_qty is None or not raw_date:
            rejected += 1
            continue

        qty = parse_qty(raw_qty)
        exp_date = parse_date(raw_date)

        if qty is None or exp_date is None:
            rejected += 1
            continue

        identifier = (str(med_name).strip().lower(), str(batch_no).strip().lower())
        if identifier in seen_in_payload:
            deduped += 1
            continue
        seen_in_payload.add(identifier)

        medicine = db.query(models.Medicine).filter(func.lower(models.Medicine.name) == identifier[0]).first()
        if not medicine:
            medicine = models.Medicine(name=str(med_name).strip(), description="Imported", reorder_threshold=20)
            db.add(medicine)
            db.commit()
            db.refresh(medicine)

        existing_batch = db.query(models.Batch).filter(
            models.Batch.medicine_id == medicine.id,
            func.lower(models.Batch.batch_number) == identifier[1]
        ).first()

        if existing_batch:
            deduped += 1
            continue

        db.add(models.Batch(medicine_id=medicine.id, batch_number=str(batch_no).strip(), quantity=qty, expiry_date=exp_date))
        imported += 1

    db.commit()
    return {"imported": imported, "deduped": deduped, "rejected": rejected}

@app.get("/outbox")
def get_outbox(db: Session = Depends(database.get_db)):
    """Level 3 (T1): Exposes the notification outbox for grading."""
    events = db.query(models.Outbox).filter(models.Outbox.processed == False).all()
    return [{"id": e.id, "event_type": e.event_type, "payload": json.loads(e.payload)} for e in events]

# --- EXISTING ENDPOINTS (UPDATED FOR NEW LOGIC) ---

@app.post("/medicines/{medicine_id}/dispense/")
def dispense_medicine(medicine_id: int, request: schemas.DispenseRequest, db: Session = Depends(database.get_db)):
    if request.quantity <= 0: raise HTTPException(status_code=400, detail="Quantity must be > 0")
    today = date.today()
    
    medicine = db.query(models.Medicine).filter(models.Medicine.id == medicine_id).first()
    if not medicine: raise HTTPException(status_code=404, detail="Medicine not found")

    batches = db.query(models.Batch).filter(
        models.Batch.medicine_id == medicine_id,
        models.Batch.expiry_date > today,
        models.Batch.is_quarantined == False,
        models.Batch.quantity > 0
    ).order_by(models.Batch.expiry_date.asc()).with_for_update().all()
    
    total_available = sum(b.quantity for b in batches)
    if total_available < request.quantity:
        raise HTTPException(status_code=400, detail="Insufficient unexpired stock.")
        
    remaining = request.quantity
    for batch in batches:
        if remaining == 0: break
        if batch.quantity <= remaining:
            remaining -= batch.quantity
            batch.quantity = 0
        else:
            batch.quantity -= remaining
            remaining = 0

    # Level 3: Re-order Alert Integration
    new_stock = total_available - request.quantity
    if new_stock < medicine.reorder_threshold:
        alert_payload = json.dumps({"medicine_id": medicine.id, "medicine_name": medicine.name, "current_stock": new_stock, "threshold": medicine.reorder_threshold})
        db.add(models.Outbox(event_type="REORDER_ALERT", payload=alert_payload))
            
    db.commit()
    return {"message": "Dispensed successfully"}