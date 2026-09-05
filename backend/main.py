import csv
import io
import uuid
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from database import engine, get_db
from models import Base
from recovery_engine import (
    analyze_transaction,
    execute_refund,
    create_refund_request
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="AI Revenue Recovery",
    description="AI-powered revenue recovery system",
    version="1.0.0"
)

STAGED_IMPORTS = {}
IMPORT_COLUMNS = {
    "transaction_id",
    "account_number",
    "customer_name",
    "email",
    "amount",
    "status",
    "debit_status",
    "failure_reason",
}


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def home():
    return {
        "message": "AI Revenue Recovery API is running.",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "revenue-recovery-system"
    }


# =========================================================
# ADMIN TRANSACTION IMPORT
# =========================================================

@app.post("/api/admin/import/preview")
async def preview_transaction_import(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        columns = [column.strip() for column in (reader.fieldnames or []) if column]
        rows = [
            {key.strip(): (value or "").strip() for key, value in row.items() if key}
            for row in reader
        ]
    except (UnicodeDecodeError, csv.Error) as error:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {error}")

    unknown_columns = sorted(set(columns) - IMPORT_COLUMNS)
    required_columns = {"transaction_id", "account_number", "amount", "status", "debit_status"}
    missing_columns = sorted(required_columns - set(columns))
    validation_errors = []

    for row_number, row in enumerate(rows, start=2):
        if not row.get("transaction_id"):
            validation_errors.append(f"Row {row_number}: transaction_id is required")
        if not row.get("account_number"):
            validation_errors.append(f"Row {row_number}: account_number is required")
        try:
            Decimal(row.get("amount", ""))
        except Exception:
            validation_errors.append(f"Row {row_number}: amount must be a number")
        if len(validation_errors) >= 20:
            break

    staging_id = uuid.uuid4().hex
    STAGED_IMPORTS[staging_id] = {
        "filename": file.filename,
        "columns": columns,
        "rows": rows,
    }

    return {
        "staging_id": staging_id,
        "filename": file.filename,
        "columns": columns,
        "row_count": len(rows),
        "preview": rows[:10],
        "unknown_columns": unknown_columns,
        "missing_columns": missing_columns,
        "validation_errors": validation_errors,
        "can_approve": not missing_columns and not unknown_columns and not validation_errors,
    }


@app.post("/api/admin/import/approve")
def approve_transaction_import(payload: Dict[str, Any], db: Session = Depends(get_db)):
    staging_id = payload.get("staging_id")
    approved_columns = set(payload.get("columns") or [])
    staged = STAGED_IMPORTS.get(staging_id)

    if not staged:
        raise HTTPException(status_code=404, detail="Import preview expired. Upload the file again.")

    required_columns = {"transaction_id", "account_number", "amount", "status", "debit_status"}
    if not required_columns.issubset(approved_columns):
        raise HTTPException(status_code=400, detail="Required columns cannot be removed.")

    invalid_columns = approved_columns - IMPORT_COLUMNS
    if invalid_columns:
        raise HTTPException(status_code=400, detail=f"Unsupported columns: {', '.join(sorted(invalid_columns))}")

    account_query = text("""
        INSERT INTO accounts (account_number, customer_name, email, status, balance)
        VALUES (:account_number, :customer_name, :email, 'ACTIVE', 0)
        ON DUPLICATE KEY UPDATE
            customer_name = VALUES(customer_name),
            email = VALUES(email)
    """)
    transaction_query = text("""
        INSERT INTO transactions
            (transaction_id, account_id, amount, status, debit_status, failure_reason)
        VALUES
            (:transaction_id, :account_id, :amount, :status, :debit_status, :failure_reason)
        ON DUPLICATE KEY UPDATE
            account_id = VALUES(account_id), amount = VALUES(amount),
            status = VALUES(status), debit_status = VALUES(debit_status),
            failure_reason = VALUES(failure_reason)
    """)

    imported = 0
    try:
        with db.begin():
            for row in staged["rows"]:
                approved_row = {key: row.get(key, "") for key in approved_columns}
                db.execute(account_query, {
                    "account_number": approved_row["account_number"],
                    "customer_name": approved_row.get("customer_name") or "Imported Customer",
                    "email": approved_row.get("email") or "imported@example.com",
                })
                account_id = db.execute(
                    text("SELECT id FROM accounts WHERE account_number = :account_number"),
                    {"account_number": approved_row["account_number"]},
                ).scalar_one()
                db.execute(transaction_query, {
                    "transaction_id": approved_row["transaction_id"],
                    "account_id": account_id,
                    "amount": Decimal(approved_row["amount"]),
                    "status": approved_row["status"],
                    "debit_status": approved_row["debit_status"],
                    "failure_reason": approved_row.get("failure_reason") or None,
                })
                imported += 1
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import failed; no rows were saved: {error}")

    del STAGED_IMPORTS[staging_id]
    return {"success": True, "imported": imported, "message": f"Imported {imported} transactions."}


# =========================================================
# GET ALL ACCOUNTS
# =========================================================

@app.get("/api/accounts")
def get_accounts(db: Session = Depends(get_db)):
    try:
        query = """
            SELECT 
                id,
                account_number,
                customer_name,
                email,
                balance,
                status,
                created_at
            FROM accounts
            ORDER BY id DESC
        """
        
        result = db.execute(text(query))
        accounts = [dict(row._mapping) for row in result.fetchall()]
        return accounts
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# GET ACCOUNT BY ID
# =========================================================

@app.get("/api/accounts/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT 
                id,
                account_number,
                customer_name,
                email,
                balance,
                status,
                created_at
            FROM accounts
            WHERE id = :account_id
        """)
        
        result = db.execute(query, {"account_id": account_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Account not found"
            )
        
        return dict(row._mapping)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# GET ALL TRANSACTIONS
# =========================================================

@app.get("/api/transactions")
def get_transactions(
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    account_id: Optional[int] = None,
    status: Optional[str] = None
):
    try:
        query = """
            SELECT
                t.id,
                t.transaction_id,
                t.account_id,
                a.account_number,
                a.customer_name,
                a.balance,
                t.amount,
                t.status,
                t.debit_status,
                t.failure_reason,
                t.created_at,
                t.risk_score,
                t.recovery_action,
                t.ai_confidence
            FROM transactions t
            JOIN accounts a
                ON t.account_id = a.id
            WHERE 1=1
            {account_filter}
            {status_filter}
            ORDER BY t.id DESC
            LIMIT :limit OFFSET :offset
        """
        
        params = {"limit": limit, "offset": offset}
        account_filter = ""
        status_filter = ""
        
        if account_id:
            account_filter = "AND t.account_id = :account_id"
            params["account_id"] = account_id
        
        if status:
            status_filter = "AND t.status = :status"
            params["status"] = status
        
        final_query = text(query.format(
            account_filter=account_filter,
            status_filter=status_filter
        ))
        
        result = db.execute(final_query, params)
        transactions = [dict(row._mapping) for row in result.fetchall()]
        return transactions
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# GET SINGLE TRANSACTION
# =========================================================

@app.get("/api/transactions/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    try:
        query = """
            SELECT
                t.id,
                t.transaction_id,
                t.account_id,
                a.account_number,
                a.customer_name,
                a.email,
                a.balance,
                t.amount,
                t.status,
                t.debit_status,
                t.failure_reason,
                t.created_at,
                t.risk_score,
                t.recovery_action,
                t.ai_confidence,
                t.analysis_timestamp
            FROM transactions t
            JOIN accounts a
                ON t.account_id = a.id
            WHERE t.transaction_id = :transaction_id
        """
        
        result = db.execute(text(query), {"transaction_id": transaction_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found"
            )
        
        return dict(row._mapping)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# ANALYZE TRANSACTION (AI)
# =========================================================

@app.post("/api/transactions/{transaction_id}/analyze")
def analyze_transaction_endpoint(
    transaction_id: str,
    failure_reason: str,
    db: Session = Depends(get_db)
):
    try:
        # Get transaction
        query = text("""
            SELECT
                t.id,
                t.transaction_id,
                t.account_id,
                a.account_number,
                a.customer_name,
                t.amount,
                t.status,
                t.debit_status,
                t.failure_reason
            FROM transactions t
            JOIN accounts a
                ON t.account_id = a.id
            WHERE t.transaction_id = :transaction_id
            FOR UPDATE
        """)
        
        result = db.execute(query, {"transaction_id": transaction_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found"
            )
        
        transaction = dict(row._mapping)
        
        # Update failure reason
        update_query = text("""
            UPDATE transactions
            SET failure_reason = :failure_reason
            WHERE transaction_id = :transaction_id
        """)
        
        db.execute(update_query, {
            "failure_reason": failure_reason,
            "transaction_id": transaction_id
        })
        db.commit()
        
        # Run AI analysis
        decision = analyze_transaction(transaction)
        
        # Update transaction with AI results
        update_ai_query = text("""
            UPDATE transactions
            SET 
                risk_score = :risk_score,
                recovery_action = :recovery_action,
                ai_confidence = :ai_confidence,
                analysis_timestamp = CURRENT_TIMESTAMP
            WHERE transaction_id = :transaction_id
        """)
        
        db.execute(update_ai_query, {
            "risk_score": decision["risk_score"],
            "recovery_action": decision["recommended_action"],
            "ai_confidence": decision.get("confidence", 85.0),
            "transaction_id": transaction_id
        })
        db.commit()
        
        # Default values
        action_taken = "AI_ANALYSIS"
        result_message = "Transaction analyzed."
        
        # AUTO REFUND
        if decision["recommended_action"] == "REFUND":
            refund_result = execute_refund(transaction_id, db)
            
            if refund_result["success"]:
                action_taken = "AUTOMATIC_REFUND"
                result_message = "Automatic refund completed successfully."
                transaction["status"] = "REFUNDED"
            else:
                action_taken = "REFUND_FAILED"
                result_message = refund_result["message"]
            
            # Save recovery action
            save_query = text("""
                INSERT INTO recovery_actions
                (
                    transaction_id,
                    risk_score,
                    recommended_action,
                    reason,
                    action_taken,
                    result
                )
                VALUES
                (
                    :transaction_id,
                    :risk_score,
                    :recommended_action,
                    :reason,
                    :action_taken,
                    :result
                )
            """)
            
            db.execute(save_query, {
                "transaction_id": transaction["id"],
                "risk_score": decision["risk_score"],
                "recommended_action": decision["recommended_action"],
                "reason": decision["reason"],
                "action_taken": action_taken,
                "result": result_message
            })
            db.commit()
            
            return {
                "transaction": transaction,
                "ai_decision": decision,
                "action_executed": refund_result["success"],
                "refund": refund_result
            }
        
        # ESCALATE TO ADMIN
        if decision["recommended_action"] == "REVIEW":
            refund_request = create_refund_request(
                transaction_id,
                db,
                "AI escalated transaction for admin review"
            )
            
            if refund_request["success"]:
                action_taken = "ESCALATED"
                result_message = "Admin refund request created."
            else:
                action_taken = "ESCALATION_FAILED"
                result_message = refund_request["message"]
            
            # Save recovery action
            save_query = text("""
                INSERT INTO recovery_actions
                (
                    transaction_id,
                    risk_score,
                    recommended_action,
                    reason,
                    action_taken,
                    result
                )
                VALUES
                (
                    :transaction_id,
                    :risk_score,
                    :recommended_action,
                    :reason,
                    :action_taken,
                    :result
                )
            """)
            
            db.execute(save_query, {
                "transaction_id": transaction["id"],
                "risk_score": decision["risk_score"],
                "recommended_action": decision["recommended_action"],
                "reason": decision["reason"],
                "action_taken": action_taken,
                "result": result_message
            })
            db.commit()
            
            return {
                "transaction": transaction,
                "ai_decision": decision,
                "action_executed": False,
                "refund_request": refund_request
            }
        
        # REJECT
        if decision["recommended_action"] == "REJECT":
            action_taken = "REJECTED"
            result_message = "Transaction rejected for refund."
        
        # Save recovery action
        save_query = text("""
            INSERT INTO recovery_actions
            (
                transaction_id,
                risk_score,
                recommended_action,
                reason,
                action_taken,
                result
            )
            VALUES
            (
                :transaction_id,
                :risk_score,
                :recommended_action,
                :reason,
                :action_taken,
                :result
            )
        """)
        
        db.execute(save_query, {
            "transaction_id": transaction["id"],
            "risk_score": decision["risk_score"],
            "recommended_action": decision["recommended_action"],
            "reason": decision["reason"],
            "action_taken": action_taken,
            "result": result_message
        })
        db.commit()
        
        return {
            "transaction": transaction,
            "ai_decision": decision,
            "action_executed": False,
            "message": result_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# REFUND REQUESTS
# =========================================================

@app.post("/api/refunds")
def create_refund(
    transaction_id: str,
    reason: str = "Customer requested refund",
    db: Session = Depends(get_db)
):
    try:
        result = create_refund_request(transaction_id, db, reason)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/api/refunds")
def get_refund_requests(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    account_id: Optional[int] = None
):
    try:
        query = """
            SELECT
                rr.id,
                rr.request_id,
                rr.transaction_id,
                t.transaction_id AS transaction_code,
                t.account_id,
                a.account_number,
                a.customer_name,
                rr.amount,
                rr.reason,
                rr.status,
                rr.admin_notes,
                rr.requested_at,
                rr.processed_at,
                rr.approved_by
            FROM refund_requests rr
            JOIN transactions t
                ON rr.transaction_id = t.id
            JOIN accounts a
                ON t.account_id = a.id
            WHERE 1=1
            {status_filter}
            {account_filter}
            ORDER BY rr.requested_at DESC
        """
        
        params = {}
        status_filter = ""
        account_filter = ""
        
        if status:
            status_filter = "AND rr.status = :status"
            params["status"] = status
        
        if account_id:
            account_filter = "AND t.account_id = :account_id"
            params["account_id"] = account_id
        
        final_query = text(query.format(
            status_filter=status_filter,
            account_filter=account_filter
        ))
        
        result = db.execute(final_query, params)
        requests = [dict(row._mapping) for row in result.fetchall()]
        return requests
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/api/refunds/history")
def get_refund_history(db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT
                rr.id,
                rr.request_id,
                t.transaction_id AS transaction_code,
                a.account_number,
                a.customer_name,
                rr.amount,
                rr.reason,
                rr.status,
                rr.requested_at,
                rr.processed_at,
                rr.approved_by
            FROM refund_requests rr
            JOIN transactions t
                ON rr.transaction_id = t.id
            JOIN accounts a
                ON t.account_id = a.id
            ORDER BY rr.requested_at DESC
            LIMIT 100
        """)

        result = db.execute(query)
        return [dict(row._mapping) for row in result.fetchall()]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/api/refunds/{request_id}")
def get_refund_request(request_id: int, db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT
                rr.id,
                rr.request_id,
                rr.transaction_id,
                t.transaction_id AS transaction_code,
                t.account_id,
                a.account_number,
                a.customer_name,
                rr.amount,
                rr.reason,
                rr.status,
                rr.admin_notes,
                rr.requested_at,
                rr.processed_at,
                rr.approved_by
            FROM refund_requests rr
            JOIN transactions t
                ON rr.transaction_id = t.id
            JOIN accounts a
                ON t.account_id = a.id
            WHERE rr.id = :request_id
        """)
        
        result = db.execute(query, {"request_id": request_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Refund request not found"
            )
        
        return dict(row._mapping)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# ADMIN ACTIONS
# =========================================================

@app.post("/api/admin/refunds/{request_id}/approve")
def approve_refund(
    request_id: int,
    admin_notes: Optional[str] = None,
    approved_by: str = "ADMIN",
    db: Session = Depends(get_db)
):
    try:
        # Get refund request
        query = text("""
            SELECT
                rr.id,
                rr.transaction_id,
                rr.amount,
                rr.reason,
                rr.status,
                t.transaction_id AS transaction_code,
                t.status AS transaction_status,
                t.debit_status,
                t.account_id,
                a.account_number,
                a.customer_name
            FROM refund_requests rr
            JOIN transactions t
                ON rr.transaction_id = t.id
            JOIN accounts a
                ON t.account_id = a.id
            WHERE rr.id = :request_id
            FOR UPDATE
        """)
        
        result = db.execute(query, {"request_id": request_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Refund request not found."
            )
        
        request = dict(row._mapping)
        
        # Must be pending
        if request["status"] != "PENDING":
            raise HTTPException(
                status_code=400,
                detail="This refund request has already been processed."
            )
        
        # Transaction must be failed
        if request["transaction_status"] != "FAILED":
            raise HTTPException(
                status_code=400,
                detail="Only failed transactions can be refunded."
            )
        
        # Money must be debited
        if request["debit_status"] != "DEBITED":
            raise HTTPException(
                status_code=400,
                detail="Money was not debited. Refund is not required."
            )
        
        amount = float(request["amount"])
        
        # Mark request approved
        db.execute(
            text("""
                UPDATE refund_requests
                SET 
                    status = 'APPROVED',
                    admin_notes = :admin_notes,
                    approved_by = :approved_by,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = :request_id
            """),
            {
                "request_id": request_id,
                "admin_notes": admin_notes,
                "approved_by": approved_by
            }
        )
        
        # Credit customer account
        db.execute(
            text("""
                UPDATE accounts
                SET balance = balance + :amount
                WHERE id = :account_id
            """),
            {
                "amount": amount,
                "account_id": request["account_id"]
            }
        )
        
        # Mark transaction refunded
        db.execute(
            text("""
                UPDATE transactions
                SET status = 'REFUNDED'
                WHERE id = :transaction_id
            """),
            {
                "transaction_id": request["transaction_id"]
            }
        )
        
        # Mark request completed
        db.execute(
            text("""
                UPDATE refund_requests
                SET 
                    status = 'COMPLETED',
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = :request_id
            """),
            {
                "request_id": request_id
            }
        )
        
        # Audit log
        db.execute(
            text("""
                INSERT INTO audit_logs
                (
                    transaction_id,
                    actor,
                    action,
                    details
                )
                VALUES
                (
                    :transaction_id,
                    :actor,
                    'REFUND_APPROVED',
                    :details
                )
            """),
            {
                "transaction_id": request["transaction_id"],
                "actor": approved_by,
                "details": (
                    f"Admin approved refund of "
                    f"₹{amount:.2f} for "
                    f"{request['customer_name']} "
                    f"({request['account_number']})."
                )
            }
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": "Refund approved and completed.",
            "request_id": request_id,
            "transaction_id": request["transaction_code"],
            "customer": request["customer_name"],
            "refund_amount": amount
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/api/admin/refunds/{request_id}/reject")
def reject_refund(
    request_id: int,
    admin_notes: Optional[str] = None,
    approved_by: str = "ADMIN",
    db: Session = Depends(get_db)
):
    try:
        # Get refund request
        query = text("""
            SELECT
                rr.id,
                rr.transaction_id,
                rr.amount,
                rr.reason,
                rr.status,
                t.transaction_id AS transaction_code,
                a.account_number,
                a.customer_name
            FROM refund_requests rr
            JOIN transactions t
                ON rr.transaction_id = t.id
            JOIN accounts a
                ON t.account_id = a.id
            WHERE rr.id = :request_id
            FOR UPDATE
        """)
        
        result = db.execute(query, {"request_id": request_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Refund request not found."
            )
        
        request = dict(row._mapping)
        
        # Must be pending
        if request["status"] != "PENDING":
            raise HTTPException(
                status_code=400,
                detail="This refund request has already been processed."
            )
        
        # Mark as rejected
        db.execute(
            text("""
                UPDATE refund_requests
                SET 
                    status = 'REJECTED',
                    admin_notes = :admin_notes,
                    approved_by = :approved_by,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = :request_id
            """),
            {
                "request_id": request_id,
                "admin_notes": admin_notes,
                "approved_by": approved_by
            }
        )
        
        # Audit log
        db.execute(
            text("""
                INSERT INTO audit_logs
                (
                    transaction_id,
                    actor,
                    action,
                    details
                )
                VALUES
                (
                    :transaction_id,
                    :actor,
                    'REFUND_REJECTED',
                    :details
                )
            """),
            {
                "transaction_id": request["transaction_id"],
                "actor": approved_by,
                "details": (
                    f"Admin rejected refund request "
                    f"of ₹{float(request['amount']):.2f} "
                    f"for {request['customer_name']} "
                    f"({request['account_number']})."
                )
            }
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": "Refund request rejected.",
            "request_id": request_id,
            "transaction_id": request["transaction_code"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# ANALYTICS & STATS
# =========================================================

@app.get("/api/analytics/stats")
def get_stats(db: Session = Depends(get_db)):
    try:
        # Transaction stats
        tx_query = text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed,
                COALESCE(SUM(CASE WHEN status = 'FAILED' AND debit_status = 'DEBITED' THEN amount ELSE 0 END), 0) AS revenue_at_risk,
                COALESCE(SUM(CASE WHEN status = 'REFUNDED' THEN amount ELSE 0 END), 0) AS total_refunded
            FROM transactions
        """)
        
        tx_result = db.execute(tx_query).fetchone()
        tx_stats = dict(tx_result._mapping)
        
        # Refund stats
        refund_query = text("""
            SELECT
                COUNT(*) AS total_requests,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected
            FROM refund_requests
        """)
        
        refund_result = db.execute(refund_query).fetchone()
        refund_stats = dict(refund_result._mapping)
        
        # AI analyzed count
        ai_query = text("""
            SELECT COUNT(*) AS count
            FROM transactions
            WHERE risk_score IS NOT NULL
        """)
        
        ai_result = db.execute(ai_query).fetchone()
        ai_count = int(ai_result._mapping["count"] or 0)
        
        # Automatic vs admin refunds
        auto_query = text("""
            SELECT COUNT(*) AS count
            FROM audit_logs
            WHERE actor = 'AI_AGENT' AND action = 'AUTOMATIC_REFUND'
        """)
        
        auto_result = db.execute(auto_query).fetchone()
        auto_refunds = int(auto_result._mapping["count"] or 0)
        
        admin_query = text("""
            SELECT COUNT(*) AS count
            FROM audit_logs
            WHERE actor = 'ADMIN' AND action = 'REFUND_APPROVED'
        """)
        
        admin_result = db.execute(admin_query).fetchone()
        admin_refunds = int(admin_result._mapping["count"] or 0)
        
        # Recovery rate
        failed = int(tx_stats["failed"] or 0)
        recovered = auto_refunds + admin_refunds
        recovery_rate = round((recovered / failed) * 100, 2) if failed > 0 else 0
        
        return {
            "transactions": {
                "total": int(tx_stats["total"] or 0),
                "successful": int(tx_stats["successful"] or 0),
                "failed": int(tx_stats["failed"] or 0),
                "revenue_at_risk": float(tx_stats["revenue_at_risk"] or 0),
                "total_refunded": float(tx_stats["total_refunded"] or 0)
            },
            "refunds": {
                "total_requests": int(refund_stats["total_requests"] or 0),
                "pending": int(refund_stats["pending"] or 0),
                "completed": int(refund_stats["completed"] or 0),
                "rejected": int(refund_stats["rejected"] or 0)
            },
            "recovery": {
                "recovery_rate": recovery_rate,
                "automatic_refunds": auto_refunds,
                "admin_refunds": admin_refunds,
                "rejected_by_admin": int(refund_stats["rejected"] or 0)
            },
            "ai_analyzed_count": ai_count,
            "auto_refund_limit": 5000.00
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/api/analytics/ai-insights")
def get_ai_insights(db: Session = Depends(get_db)):
    try:
        # Get AI analyzed transactions
        query = text("""
            SELECT
                risk_score,
                recovery_action,
                failure_reason
            FROM transactions
            WHERE risk_score IS NOT NULL
        """)
        
        result = db.execute(query)
        transactions = [dict(row._mapping) for row in result.fetchall()]
        
        # Action distribution
        action_distribution = {
            "REFUND": 0,
            "REVIEW": 0,
            "REJECT": 0
        }
        
        for tx in transactions:
            action = tx.get("recovery_action")
            if action in action_distribution:
                action_distribution[action] += 1
        
        # Risk by reason
        risk_by_reason = {}
        for tx in transactions:
            reason = tx.get("failure_reason")
            if reason:
                if reason not in risk_by_reason:
                    risk_by_reason[reason] = []
                risk_by_reason[reason].append(tx["risk_score"])
        
        avg_risk_by_reason = {
            reason: round(sum(scores) / len(scores), 1)
            for reason, scores in risk_by_reason.items()
        }
        
        return {
            "total_analyzed": len(transactions),
            "action_distribution": action_distribution,
            "average_risk_by_reason": avg_risk_by_reason,
            "high_risk_transactions": sum(1 for tx in transactions if tx["risk_score"] > 70),
            "low_risk_transactions": sum(1 for tx in transactions if tx["risk_score"] < 30)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# RUNNING THE APPLICATION
# =========================================================

# Start with:
#
# uvicorn main:app --reload
#
# API:
# http://127.0.0.1:8000
#
# Swagger:
# http://127.0.0.1:8000/docs