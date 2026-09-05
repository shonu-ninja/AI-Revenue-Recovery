from sqlalchemy import text
from typing import Dict, Any, Optional
import random
import logging
import os

logger = logging.getLogger(__name__)


# =========================================================
# CONFIGURATION
# =========================================================

AUTO_REFUND_LIMIT = float(os.getenv("AUTO_REFUND_LIMIT", "5000"))
FAILURE_REASONS = [
    "INSUFFICIENT_FUNDS",
    "NETWORK_ISSUE",
    "BANK_ISSUE",
    "GATEWAY_TIMEOUT",
    "TECHNICAL_ERROR",
    "OTHER"
]


# =========================================================
# AI TRANSACTION ANALYSIS
# =========================================================

def analyze_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a transaction and recommend a recovery action.
    
    Enhanced AI logic with risk scoring based on multiple factors:
    - Transaction amount
    - Payment status
    - Debit status
    - Failure reason (if available)
    - Customer history (simulated)
    
    Rules:
    - SUCCESS -> NO_ACTION (0% risk)
    - FAILED + NOT_DEBITED -> RETRY_PAYMENT (20% risk)
    - FAILED + DEBITED + amount < AUTO_REFUND_LIMIT -> REFUND (90% risk)
    - FAILED + DEBITED + amount >= AUTO_REFUND_LIMIT -> REVIEW (85% risk)
    - REFUNDED -> NO_ACTION (0% risk)
    """

    amount = float(transaction.get("amount", 0))
    status = transaction.get("status", "PENDING")
    debit_status = transaction.get("debit_status", "NOT_DEBITED")
    failure_reason = transaction.get("failure_reason", "OTHER")

    # -----------------------------------------------------
    # SUCCESSFUL PAYMENT
    # -----------------------------------------------------

    if status == "SUCCESS":
        return {
            "risk_score": 0.0,
            "recommended_action": "NO_ACTION",
            "confidence": 100.0,
            "reason": "Payment completed successfully. No action required."
        }

    # -----------------------------------------------------
    # ALREADY REFUNDED
    # -----------------------------------------------------

    if status == "REFUNDED":
        return {
            "risk_score": 0.0,
            "recommended_action": "NO_ACTION",
            "confidence": 100.0,
            "reason": "Transaction has already been refunded."
        }

    # -----------------------------------------------------
    # FAILED + MONEY NOT DEBITED
    # -----------------------------------------------------

    if status == "FAILED" and debit_status == "NOT_DEBITED":
        return {
            "risk_score": 20.0,
            "recommended_action": "RETRY_PAYMENT",
            "confidence": 95.0,
            "reason": "Payment failed but no money was debited. Recommend retrying the payment."
        }

    # -----------------------------------------------------
    # FAILED + MONEY DEBITED
    # -----------------------------------------------------

    if status == "FAILED" and debit_status == "DEBITED":
        risk_score = _calculate_risk_score(amount, failure_reason)
        
        # ---------------------------------------------
        # HIGH VALUE TRANSACTION
        # ---------------------------------------------

        if amount >= AUTO_REFUND_LIMIT:
            return {
                "risk_score": risk_score,
                "recommended_action": "REVIEW",
                "confidence": 85.0,
                "reason": (
                    f"Money was debited but the amount (₹{amount:,.2f}) exceeds "
                    f"the automatic refund limit of ₹{AUTO_REFUND_LIMIT:,}. "
                    "Manual admin review required."
                )
            }

        # ---------------------------------------------
        # AUTOMATIC REFUND
        # ---------------------------------------------

        return {
            "risk_score": risk_score,
            "recommended_action": "REFUND",
            "confidence": 90.0,
            "reason": (
                "Payment failed, money was debited, "
                f"and the amount (₹{amount:,.2f}) is within the automatic refund limit. "
                "Initiating automatic refund."
            )
        }

    # -----------------------------------------------------
    # FAILED + PARTIAL DEBIT
    # -----------------------------------------------------

    if status == "FAILED" and debit_status == "PARTIAL":
        risk_score = _calculate_risk_score(amount, failure_reason) + 10
        
        return {
            "risk_score": min(risk_score, 100.0),
            "recommended_action": "REVIEW",
            "confidence": 75.0,
            "reason": (
                "Partial debit occurred. Manual review required to verify "
                "the correct amount to refund."
            )
        }

    # -----------------------------------------------------
    # PENDING TRANSACTION
    # -----------------------------------------------------

    if status == "PENDING":
        return {
            "risk_score": 30.0,
            "recommended_action": "RETRY_PAYMENT",
            "confidence": 60.0,
            "reason": "Transaction is pending. Recommend checking status and retrying if needed."
        }

    # -----------------------------------------------------
    # UNEXPECTED SITUATION
    # -----------------------------------------------------

    return {
        "risk_score": 50.0,
        "recommended_action": "REVIEW",
        "confidence": 40.0,
        "reason": "Transaction requires manual investigation due to unexpected status."
    }


def _calculate_risk_score(amount: float, failure_reason: str) -> float:
    """
    Calculate risk score based on amount and failure reason.
    Higher score = higher risk = more likely to need review/reject.
    """
    # Base risk from failure reason
    failure_risk = {
        "INSUFFICIENT_FUNDS": 20.0,
        "NETWORK_ISSUE": 40.0,
        "BANK_ISSUE": 60.0,
        "GATEWAY_TIMEOUT": 70.0,
        "TECHNICAL_ERROR": 50.0,
        "OTHER": 30.0
    }
    
    base_risk = failure_risk.get(failure_reason, 40.0)
    
    # Amount factor - larger amounts = higher risk
    amount_factor = min((amount / AUTO_REFUND_LIMIT) * 30, 30.0)
    
    # Risk score = base_risk + amount_factor, capped at 100
    risk_score = min(base_risk + amount_factor, 100.0)
    
    return round(risk_score, 1)


# =========================================================
# AUTOMATIC REFUND
# =========================================================

def execute_refund(transaction_id: str, connection) -> Dict[str, Any]:
    """
    Execute an automatic refund.

    Safety checks:
    1. Transaction must exist.
    2. Transaction must be FAILED.
    3. Money must have been DEBITED.
    4. Transaction must not already be REFUNDED.
    5. Amount must be <= automatic refund limit.
    6. A completed refund must not already exist.
    """

    # -----------------------------------------------------
    # FIND TRANSACTION
    # -----------------------------------------------------

    query = text("""
        SELECT
            t.id,
            t.transaction_id,
            t.account_id,
            t.amount,
            t.status,
            t.debit_status,
            a.balance,
            a.account_number,
            a.customer_name
        FROM transactions t
        JOIN accounts a
            ON t.account_id = a.id
        WHERE t.transaction_id = :transaction_id
        FOR UPDATE
    """)

    result = connection.execute(
        query,
        {"transaction_id": transaction_id}
    )

    transaction = result.fetchone()

    if not transaction:
        return {
            "success": False,
            "message": "Transaction not found."
        }

    transaction = dict(transaction._mapping)
    amount = float(transaction["amount"])

    # -----------------------------------------------------
    # SAFETY CHECK 1
    # -----------------------------------------------------

    if transaction["status"] == "REFUNDED":
        return {
            "success": False,
            "message": "Transaction has already been refunded."
        }

    # -----------------------------------------------------
    # SAFETY CHECK 2
    # -----------------------------------------------------

    if transaction["status"] != "FAILED":
        return {
            "success": False,
            "message": "Only failed transactions can be refunded."
        }

    # -----------------------------------------------------
    # SAFETY CHECK 3
    # -----------------------------------------------------

    if transaction["debit_status"] != "DEBITED":
        return {
            "success": False,
            "message": "Money was not debited. Refund is not required."
        }

    # -----------------------------------------------------
    # SAFETY CHECK 4
    # -----------------------------------------------------

    if amount >= AUTO_REFUND_LIMIT:
        return {
            "success": False,
            "message": (
                f"Amount (₹{amount:,.2f}) exceeds automatic refund limit "
                f"(₹{AUTO_REFUND_LIMIT:,}). Admin approval required."
            )
        }

    # -----------------------------------------------------
    # SAFETY CHECK 5
    # -----------------------------------------------------

    existing_refund = connection.execute(
        text("""
            SELECT id
            FROM refund_requests
            WHERE transaction_id = :transaction_id
            AND status = 'COMPLETED'
            LIMIT 1
        """),
        {"transaction_id": transaction["id"]}
    ).fetchone()

    if existing_refund:
        return {
            "success": False,
            "message": "A completed refund already exists for this transaction."
        }

    # -----------------------------------------------------
    # GENERATE REQUEST ID
    # -----------------------------------------------------
    
    import uuid
    request_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

    # -----------------------------------------------------
    # CREDIT CUSTOMER ACCOUNT
    # -----------------------------------------------------

    connection.execute(
        text("""
            UPDATE accounts
            SET balance = balance + :amount
            WHERE id = :account_id
        """),
        {
            "amount": amount,
            "account_id": transaction["account_id"]
        }
    )

    # -----------------------------------------------------
    # MARK TRANSACTION AS REFUNDED
    # -----------------------------------------------------

    connection.execute(
        text("""
            UPDATE transactions
            SET status = 'REFUNDED'
            WHERE id = :transaction_id
        """),
        {"transaction_id": transaction["id"]}
    )

    # -----------------------------------------------------
    # CREATE COMPLETED REFUND RECORD
    # -----------------------------------------------------

    connection.execute(
        text("""
            INSERT INTO refund_requests
            (
                request_id,
                transaction_id,
                amount,
                reason,
                status,
                processed_at,
                approved_by
            )
            VALUES
            (
                :request_id,
                :transaction_id,
                :amount,
                :reason,
                'COMPLETED',
                CURRENT_TIMESTAMP,
                'AI_AGENT'
            )
        """),
        {
            "request_id": request_id,
            "transaction_id": transaction["id"],
            "amount": amount,
            "reason": "AI-approved automatic refund"
        }
    )

    # -----------------------------------------------------
    # CREATE AUDIT LOG
    # -----------------------------------------------------

    connection.execute(
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
                'AI_AGENT',
                'AUTOMATIC_REFUND',
                :details
            )
        """),
        {
            "transaction_id": transaction["id"],
            "details": (
                f"Automatically refunded ₹{amount:,.2f} "
                f"to {transaction['customer_name']} "
                f"({transaction['account_number']})."
            )
        }
    )

    # -----------------------------------------------------
    # RETURN RESULT
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Refund completed successfully.",
        "transaction_id": transaction["transaction_id"],
        "customer": transaction["customer_name"],
        "refund_amount": amount,
        "request_id": request_id
    }


# =========================================================
# CUSTOMER REFUND REQUEST
# =========================================================

def create_refund_request(transaction_id: str, connection, reason: str = "Customer requested refund") -> Dict[str, Any]:
    """
    Create a manual refund request for admin review.
    """

    # -----------------------------------------------------
    # FIND TRANSACTION
    # -----------------------------------------------------

    query = text("""
        SELECT
            id,
            transaction_id,
            amount,
            status,
            debit_status
        FROM transactions
        WHERE transaction_id = :transaction_id
        FOR UPDATE
    """)

    result = connection.execute(
        query,
        {"transaction_id": transaction_id}
    )

    row = result.fetchone()

    if not row:
        return {
            "success": False,
            "message": "Transaction not found."
        }

    transaction = dict(row._mapping)
    amount = float(transaction["amount"])

    # -----------------------------------------------------
    # ALREADY REFUNDED
    # -----------------------------------------------------

    if transaction["status"] == "REFUNDED":
        return {
            "success": False,
            "message": "Transaction has already been refunded."
        }

    # -----------------------------------------------------
    # ONLY FAILED TRANSACTIONS
    # -----------------------------------------------------

    if transaction["status"] != "FAILED":
        return {
            "success": False,
            "message": "Only failed transactions can have refund requests."
        }

    # -----------------------------------------------------
    # MONEY MUST BE DEBITED
    # -----------------------------------------------------

    if transaction["debit_status"] != "DEBITED":
        return {
            "success": False,
            "message": "Money was not debited. Refund request is not required."
        }

    # -----------------------------------------------------
    # CHECK EXISTING ACTIVE REQUEST
    # -----------------------------------------------------

    existing_query = text("""
        SELECT id, status
        FROM refund_requests
        WHERE transaction_id = :transaction_id
        AND status IN ('PENDING', 'APPROVED')
        LIMIT 1
    """)

    existing = connection.execute(
        existing_query,
        {"transaction_id": transaction["id"]}
    ).fetchone()

    if existing:
        return {
            "success": False,
            "message": f"A refund request already exists for this transaction (Status: {existing.status})."
        }

    # -----------------------------------------------------
    # GENERATE REQUEST ID
    # -----------------------------------------------------
    
    import uuid
    request_id = f"REF-{uuid.uuid4().hex[:8].upper()}"

    # -----------------------------------------------------
    # CREATE PENDING REQUEST
    # -----------------------------------------------------

    insert_query = text("""
        INSERT INTO refund_requests
        (
            request_id,
            transaction_id,
            amount,
            reason,
            status
        )
        VALUES
        (
            :request_id,
            :transaction_id,
            :amount,
            :reason,
            'PENDING'
        )
    """)

    connection.execute(
        insert_query,
        {
            "request_id": request_id,
            "transaction_id": transaction["id"],
            "amount": amount,
            "reason": reason
        }
    )

    # -----------------------------------------------------
    # CREATE AUDIT LOG
    # -----------------------------------------------------

    audit_query = text("""
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
            'CUSTOMER',
            'REFUND_REQUESTED',
            :details
        )
    """)

    connection.execute(
        audit_query,
        {
            "transaction_id": transaction["id"],
            "details": f"Customer requested refund. Reason: {reason}"
        }
    )

    # -----------------------------------------------------
    # RETURN RESULT
    # -----------------------------------------------------

    return {
        "success": True,
        "message": "Refund request submitted for admin review.",
        "transaction_id": transaction["transaction_id"],
        "amount": amount,
        "status": "PENDING",
        "request_id": request_id
    }


# =========================================================
# BULK ANALYSIS (For background jobs)
# =========================================================

def analyze_bulk_transactions(transactions: list) -> list:
    """
    Analyze multiple transactions in bulk.
    Useful for scheduled jobs or reporting.
    """
    results = []
    for transaction in transactions:
        results.append(analyze_transaction(transaction))
    return results


# =========================================================
# GET RECOVERY STATISTICS
# =========================================================

def get_recovery_stats(connection) -> Dict[str, Any]:
    """
    Get statistics about the recovery system performance.
    """
    
    query = text("""
        SELECT
            COUNT(*) AS total_analyzed,
            SUM(CASE WHEN recommended_action = 'REFUND' THEN 1 ELSE 0 END) AS refund_recommendations,
            SUM(CASE WHEN recommended_action = 'REVIEW' THEN 1 ELSE 0 END) AS review_recommendations,
            SUM(CASE WHEN recommended_action = 'REJECT' THEN 1 ELSE 0 END) AS reject_recommendations,
            AVG(risk_score) AS avg_risk_score
        FROM recovery_actions
    """)
    
    result = connection.execute(query).fetchone()
    stats = dict(result._mapping)
    
    return {
        "total_analyzed": int(stats.get("total_analyzed", 0)),
        "refund_recommendations": int(stats.get("refund_recommendations", 0)),
        "review_recommendations": int(stats.get("review_recommendations", 0)),
        "reject_recommendations": int(stats.get("reject_recommendations", 0)),
        "avg_risk_score": float(stats.get("avg_risk_score", 0) or 0)
    }