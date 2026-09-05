# AI Revenue Recovery System

An AI-assisted revenue recovery prototype for identifying failed payments where a customer's account may have been debited, analyzing recovery eligibility, and managing automatic or administrator-approved refunds.

> This is a demonstration system that uses dummy data. It is not connected to a real payment gateway or banking system and must not be used to process real financial transactions without substantial security, compliance, and provider integration work.

## Features

- Detect successful, failed, pending, refunded, debited, non-debited, and partially debited transactions.
- Analyze transactions with deterministic rule-based recovery logic.
- Calculate a risk score and confidence value from amount and failure reason.
- Automatically refund failed, debited transactions below the automatic refund limit.
- Create administrator review requests for high-value and partially debited transactions.
- Allow customers to submit refund requests for failed, debited transactions.
- Approve or reject pending refund requests from the administrator portal.
- View transaction history, refund history, customer accounts, recovery statistics, and AI analysis results.
- Import transaction data from CSV after validation and preview.
- Generate a transaction invoice PDF from the customer portal.

## Recovery Workflow

```text
Transaction
    |
    +-- SUCCESS ----------------------> No recovery action
    |
    +-- FAILED and NOT_DEBITED --------> RETRY_PAYMENT
    |
    +-- FAILED and DEBITED
          |
          +-- Amount below limit ------> REFUND and automatic refund
          |
          +-- Amount at/above limit --> REVIEW and admin refund request
    |
    +-- FAILED and PARTIAL ------------> REVIEW and admin refund request
```

The recovery engine can return `REFUND`, `REVIEW`, `RETRY_PAYMENT`, and `NO_ACTION`. `REJECT` is defined in the data model for future or exceptional use, but is not currently produced by the normal analysis rules.

## Technology

### Frontend

- React 19
- Vite
- React Router
- Lucide React icons
- jsPDF

### Backend and database

- Python, FastAPI, SQLAlchemy, and Uvicorn
- MySQL through PyMySQL

The recovery engine is currently rule-based. The project includes data-processing and machine-learning dependencies for future experimentation, but it does not currently load or train a machine-learning model.

## Project Structure

```text
ai-revenue-recovery/
├── backend/
│   ├── database.py
│   ├── init_db.py
│   ├── main.py
│   ├── models.py
│   ├── recovery_engine.py
│   ├── seed_data.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/Admin.jsx
│   │   ├── pages/AdminLogin.jsx
│   │   ├── pages/Customer.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── transaction_sample_50.csv
├── requirements.txt
└── run.py
```

## Requirements

- Python 3.10 or newer
- Node.js and npm
- MySQL Server

## Configuration

Create a `.env` file in the project root or backend directory:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/revenue_recovery
AUTO_REFUND_LIMIT=5000
```

Create the database before starting the application:

```sql
CREATE DATABASE revenue_recovery;
```

The default database URL is `mysql+pymysql://root:password@localhost:3306/revenue_recovery`. Amounts below the automatic refund limit may be refunded automatically; amounts equal to or above it require administrator review.

## Installation

From the project root, in Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

## Run the Application

The simplest option is:

```powershell
python run.py
```

This creates the tables, seeds demo data, and starts both services.

- Frontend: http://127.0.0.1:5173
- Backend: http://127.0.0.1:8000
- API documentation: http://127.0.0.1:8000/docs

To run services separately:

```powershell
cd backend
python init_db.py
python seed_data.py
python -m uvicorn main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm run dev
```

The Vite server proxies `/api` requests to `http://127.0.0.1:8000`.

## API Endpoints

### Health

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | API status and documentation link |
| `GET` | `/health` | Health check |

### Accounts and transactions

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/accounts` | List customer accounts |
| `GET` | `/api/accounts/{account_id}` | Get one account |
| `GET` | `/api/transactions` | List transactions with optional filters |
| `GET` | `/api/transactions/{transaction_id}` | Get one transaction |
| `POST` | `/api/transactions/{transaction_id}/analyze` | Analyze and execute or create the next recovery action |

The analyze endpoint accepts `failure_reason` as a query parameter.

### Refunds and administration

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/refunds` | Create a refund request |
| `GET` | `/api/refunds` | List refund requests |
| `GET` | `/api/refunds/history` | List refund history |
| `GET` | `/api/refunds/{request_id}` | Get one refund request |
| `POST` | `/api/admin/refunds/{request_id}/approve` | Approve and complete a refund |
| `POST` | `/api/admin/refunds/{request_id}/reject` | Reject a pending refund request |
| `POST` | `/api/admin/import/preview` | Validate and preview a CSV import |
| `POST` | `/api/admin/import/approve` | Save an approved CSV import |

### Analytics

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/analytics/stats` | Transaction, refund, and recovery statistics |
| `GET` | `/api/analytics/ai-insights` | Analyzed transaction and risk summaries |

## Demo Data

The seed script creates 20 demo accounts, 20 demo transactions, and five pending refund requests. Transaction IDs range from `TXN001` through `TXN020`. Some seeded records are intentionally invalid or unusual for testing validation and recovery workflows.

## Important Limitations

- The recovery engine is rule-based, not a trained AI model.
- There is no real payment gateway, bank connection, or money movement.
- Admin authentication is a frontend prototype and is not production-grade authorization.
- There are no email, SMS, or push notifications.
- Analytics refresh on dashboard load or after an action; there is no WebSocket live stream.
- The in-memory CSV staging store is intended for local development only.
- Production use requires authentication, authorization, idempotency controls, audit hardening, provider reconciliation, secrets management, monitoring, and compliance review.

## Future Improvements

- Integrate a real payment provider and reconciliation process.
- Add secure customer and administrator authentication.
- Train and evaluate an ML model using historical transaction data.
- Add notifications and customer-facing refund tracking.
- Add background jobs, retry handling, and stronger idempotency guarantees.
- Add automated tests, deployment configuration, and production observability.

## License

No license has been specified for this prototype.