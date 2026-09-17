from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt

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
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = database.func.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": date.today() + timedelta(days=1)}) 
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None: raise credentials_exception
    return user

@app.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/medicines/", response_model=schemas.MedicineResponse)
def create_medicine(medicine: schemas.MedicineCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    db_medicine = models.Medicine(**medicine.model_dump())
    db.add(db_medicine)
    db.commit()
    db.refresh(db_medicine)
    return schemas.MedicineResponse(**db_medicine.__dict__, total_unexpired_stock=0)

@app.get("/medicines/", response_model=List[schemas.MedicineResponse])
def get_medicines(skip: int = 0, limit: int = 10, search: str = "", db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Medicine)
    if search:
        query = query.filter(models.Medicine.name.ilike(f"%{search}%"))
    
    medicines = query.offset(skip).limit(limit).all()
    today = date.today()
    
    results = []
    for med in medicines:
        stock = db.query(func.sum(models.Batch.quantity)).filter(
            models.Batch.medicine_id == med.id,
            models.Batch.expiry_date > today
        ).scalar() or 0
        results.append(schemas.MedicineResponse(**med.__dict__, total_unexpired_stock=stock))
    return results

@app.post("/medicines/{medicine_id}/batches/", response_model=schemas.BatchResponse)
def add_batch(medicine_id: int, batch: schemas.BatchCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    medicine = db.query(models.Medicine).filter(models.Medicine.id == medicine_id).first()
    if not medicine: raise HTTPException(status_code=404, detail="Medicine not found")
    
    db_batch = models.Batch(**batch.model_dump(), medicine_id=medicine_id)
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch

@app.post("/medicines/{medicine_id}/dispense/")
def dispense_medicine(medicine_id: int, request: schemas.DispenseRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
        
    today = date.today()
    
    # 1. Fetch unexpired batches locked for update to prevent concurrent race conditions
    batches = db.query(models.Batch).filter(
        models.Batch.medicine_id == medicine_id,
        models.Batch.expiry_date > today,
        models.Batch.quantity > 0
    ).order_by(models.Batch.expiry_date.asc()).with_for_update().all()
    
    total_available = sum(b.quantity for b in batches)
    
    # 2. Strict Negative Inventory Check
    if total_available < request.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient unexpired stock. Requested {request.quantity}, available {total_available}.")
        
    # 3. FEFO Split Batch Logic
    remaining_to_dispense = request.quantity
    dispensed_from = []
    
    for batch in batches:
        if remaining_to_dispense == 0:
            break
            
        if batch.quantity <= remaining_to_dispense:
            dispensed = batch.quantity
            remaining_to_dispense -= batch.quantity
            batch.quantity = 0
        else:
            dispensed = remaining_to_dispense
            batch.quantity -= remaining_to_dispense
            remaining_to_dispense = 0
            
        dispensed_from.append({"batch_number": batch.batch_number, "quantity_dispensed": dispensed})
        
    # 4. Safe single transaction commit
    db.commit()
    return {"message": "Dispensed successfully", "details": dispensed_from}

@app.get("/alerts/expiring/", response_model=List[schemas.AlertResponse])
def get_expiring_alerts(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    today = date.today()
    threshold = today + timedelta(days=30)
    
    batches = db.query(models.Batch).join(models.Medicine).filter(
        models.Batch.quantity > 0,
        models.Batch.expiry_date > today,
        models.Batch.expiry_date <= threshold
    ).all()
    
    alerts = []
    for b in batches:
        alerts.append({
            "batch_id": b.id,
            "medicine_name": b.medicine.name,
            "batch_number": b.batch_number,
            "quantity": b.quantity,
            "expiry_date": b.expiry_date,
            "days_to_expiry": (b.expiry_date - today).days
        })
    return alerts