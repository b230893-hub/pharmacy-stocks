# Architectural Decisions & Edge Cases

## Tech Stack Choices
- **FastAPI:** Chosen for high performance, automatic OpenAPI documentation (Swagger), and native async support. Pydantic schemas enforce strict I/O validation.
- **SQLAlchemy:** Utilized as the ORM to manage relational data and ensure transaction safety.
- **React + Vite + Tailwind:** Provides a rapid, responsive, and lightweight frontend architecture. Vite significantly reduces build and HMR times.

## Critical Edge Cases & Solutions (FEFO Dispensing)
1. **Expired Stock Exclusion:** 
   - *Decision:* A medicine batch is considered expired if its `expiry_date` is less than or equal to `date.today()`.
   - *Implementation:* The SQLAlchemy query explicitly filters `Batch.expiry_date > date.today()`. Expired items never even reach Python memory during the dispense calculation.
2. **Split Batches:** 
   - *Decision:* If a requested quantity spans multiple batches, the system must drain the oldest batch to 0 before moving to the next.
   - *Implementation:* Batches are ordered by `expiry_date ASC`. A `while/for` loop processes the requested quantity. If a batch cannot fulfill the total remaining request, its quantity is set to 0, the remaining request is decremented, and the loop continues to the next batch.
3. **Negative Inventory Prevention:**
   - *Decision:* Total unexpired stock is aggregated first. If `requested_qty > total_unexpired`, a 400 Bad Request is raised *before* any mutations occur.
4. **Mutation & Concurrency Safety:**
   - *Decision:* Concurrent dispense requests for the same medicine could cause race conditions.
   - *Implementation:* Used SQLAlchemy's `with_for_update()` in the dispense query. This applies a row-level database lock (SELECT ... FOR UPDATE) on the queried batches. The entire validation, calculation, and mutation happens within a single atomic database transaction. If the transaction fails, nothing is saved.