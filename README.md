# FEFO Pharmacy Inventory System

A production-ready Full-Stack Pharmacy Inventory System implementing strict First-Expiry-First-Out (FEFO) dispensing rules, ensuring expired medications are never sold, and inventory operations are mathematically and transactionally safe.

## Future Vision & Landing Pitch
**"Your Pharmacy's Safety Net."** Stop losing money to expired stock and eliminate the risk of dispensing out-of-date medication. Our FEFO-first engine handles the math, the split-batches, and the safety locks automatically.

**Coming Soon (Top 3 Future Features):**
1. **Barcode/QR Scanner Integration:** Scan incoming batches directly into the system for error-free entry.
2. **Predictive Ordering:** AI-driven reorder alerts based on dispensing velocity and upcoming expirations.
3. **Multi-Location Sync:** Share inventory visibility across multiple neighborhood pharmacy branches.

## Setup & Run Instructions

### Backend (Python/FastAPI)
1. Open a terminal and navigate to the `backend` directory.
2. Create a virtual environment: `python -m venv venv`
3. Activate it: 
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the server: `uvicorn main:app --reload --port 8000`

### Frontend (React/Vite/Tailwind)
1. Open a terminal and navigate to the `frontend` directory.
2. Install dependencies: `npm install`
3. Run the development server: `npm run dev`
4. Access the UI at `http://localhost:5173`

## Debugging
- **Database:** SQLite is used. The file `pharmacy.db` will be created in the `backend` folder. You can use DB Browser for SQLite to inspect it.
- **Swagger Docs:** Interactive API debugging is available at `http://localhost:8000/docs`.

## API List
- `POST /register` - Register a new user.
- `POST /token` - Login to get a JWT access token.
- `GET /medicines/` - List all medicines with search, pagination, and calculated stock.
- `POST /medicines/` - Add a new medicine.
- `POST /medicines/{medicine_id}/batches/` - Add a new stock batch to a medicine.
- `POST /medicines/{medicine_id}/dispense/` - Dispense medication (executes strict FEFO logic).
- `GET /alerts/expiring/` - Get batches expiring within 30 days.