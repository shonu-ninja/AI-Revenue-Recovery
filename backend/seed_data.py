from decimal import Decimal

from sqlalchemy import text

from database import SessionLocal


ACCOUNTS = [
    ("ACC1001", "Aarav Sharma", "aarav.sharma@example.com", "ACTIVE", "125000.00"),
    ("ACC1002", "Diya Patel", "diya.patel@example.com", "ACTIVE", "87500.00"),
    ("ACC1003", "Rohan Mehta", "rohan.mehta@example.com", "ACTIVE", "64200.50"),
    ("ACC1004", "Ananya Singh", "ananya.singh@example.com", "ACTIVE", "218000.00"),
    ("ACC1005", "Vikram Nair", "vikram.nair@example.com", "ACTIVE", "45900.00"),
    ("ACC1006", "Ishita Rao", "ishita.rao@example.com", "ACTIVE", "91300.00"),
    ("ACC1007", "Kabir Joshi", "kabir.joshi@example.com", "SUSPENDED", "12000.00"),
    ("ACC1008", "Meera Iyer", "meera.iyer@example.com", "ACTIVE", "156750.75"),
    ("ACC1009", "Arjun Kapoor", "arjun.kapoor@example.com", "ACTIVE", "78500.00"),
    ("ACC1010", "Sara Khan", "sara.khan@example.com", "ACTIVE", "33400.00"),
    ("ACC1011", "Aditya Verma", "aditya.verma@example.com", "ACTIVE", "99000.00"),
    ("ACC1012", "Nisha Gupta", "nisha.gupta@example.com", "ACTIVE", "112500.00"),
    ("ACC1013", "Karan Malhotra", "karan.malhotra@example.com", "CLOSED", "0.00"),
    ("ACC1014", "Tara Desai", "tara.desai@example.com", "ACTIVE", "48750.25"),
    ("ACC1015", "Yash Kulkarni", "yash.kulkarni@example.com", "ACTIVE", "67000.00"),
    ("ACC1016", "Pooja Shah", "pooja.shah@example.com", "ACTIVE", "23900.00"),
    # Deliberately messy records for testing validation and recovery workflows.
    ("ACC-WRONG-17", "Test Missing Email", "not-an-email", "ACTIVE", "1000.00"),
    ("ACC-WRONG-18", "Test Negative Balance", "negative.balance@example.com", "ACTIVE", "-2500.00"),
    ("ACC-WRONG-19", "Test Suspended Account", "suspended@example.com", "SUSPENDED", "5.00"),
    ("ACC-WRONG-20", "Test Large Failed Payment", "large.payment@example.com", "ACTIVE", "15.00"),
]

TRANSACTIONS = [
    ("TXN001", "ACC1001", "2499.00", "SUCCESS", "DEBITED", None),
    ("TXN002", "ACC1002", "7999.00", "SUCCESS", "DEBITED", None),
    ("TXN003", "ACC1003", "1250.50", "REFUNDED", "DEBITED", None),
    ("TXN004", "ACC1004", "18500.00", "FAILED", "DEBITED", "INSUFFICIENT_FUNDS"),
    ("TXN005", "ACC1005", "499.00", "FAILED", "NOT_DEBITED", "NETWORK_ISSUE"),
    ("TXN006", "ACC1006", "3250.00", "SUCCESS", "DEBITED", None),
    ("TXN007", "ACC1007", "999.00", "PENDING", "PARTIAL", "BANK_ISSUE"),
    ("TXN008", "ACC1008", "27500.00", "FAILED", "DEBITED", "GATEWAY_TIMEOUT"),
    ("TXN009", "ACC1009", "1599.00", "SUCCESS", "DEBITED", None),
    ("TXN010", "ACC1010", "7499.00", "FAILED", "NOT_DEBITED", "TECHNICAL_ERROR"),
    ("TXN011", "ACC1011", "2150.00", "SUCCESS", "DEBITED", None),
    ("TXN012", "ACC1012", "65000.00", "FAILED", "PARTIAL", "BANK_ISSUE"),
    ("TXN013", "ACC1013", "300.00", "FAILED", "NOT_DEBITED", "OTHER"),
    ("TXN014", "ACC1014", "8750.00", "SUCCESS", "DEBITED", None),
    ("TXN015", "ACC1015", "1299.00", "REFUNDED", "DEBITED", None),
    ("TXN016", "ACC1016", "4500.00", "FAILED", "DEBITED", "NETWORK_ISSUE"),
    ("TXN017", "ACC-WRONG-17", "999999.99", "FAILED", "DEBITED", "OTHER"),
    ("TXN018", "ACC-WRONG-18", "-450.00", "FAILED", "DEBITED", "TECHNICAL_ERROR"),
    ("TXN019", "ACC-WRONG-19", "1.00", "SUCCESS", "DEBITED", None),
    ("TXN020", "ACC-WRONG-20", "125000.00", "FAILED", "DEBITED", "GATEWAY_TIMEOUT"),
]

REFUND_REQUESTS = [
    ("REQ-SEED-004", "TXN004", "18500.00", "Customer reported a failed payment but the account was debited."),
    ("REQ-SEED-008", "TXN008", "27500.00", "Gateway timeout after debit; needs admin review."),
    ("REQ-SEED-012", "TXN012", "65000.00", "Partial debit on failed payment; customer requested refund."),
    ("REQ-SEED-017", "TXN017", "999999.99", "Test record with an unusually large failed payment."),
    ("REQ-SEED-020", "TXN020", "125000.00", "Test record for high-value failed payment recovery."),
]


def seed_data():
    with SessionLocal.begin() as db:
        account_query = text("""
            INSERT INTO accounts
                (account_number, customer_name, email, status, balance)
            VALUES
                (:account_number, :customer_name, :email, :status, :balance)
            ON DUPLICATE KEY UPDATE
                customer_name = VALUES(customer_name),
                email = VALUES(email),
                status = VALUES(status),
                balance = VALUES(balance)
        """)

        for account_number, customer_name, email, status, balance in ACCOUNTS:
            db.execute(account_query, {
                "account_number": account_number,
                "customer_name": customer_name,
                "email": email,
                "status": status,
                "balance": Decimal(balance),
            })

        account_ids = {
            row.account_number: row.id
            for row in db.execute(text("SELECT id, account_number FROM accounts"))
        }

        transaction_query = text("""
            INSERT INTO transactions
                (transaction_id, account_id, amount, status, debit_status, failure_reason)
            VALUES
                (:transaction_id, :account_id, :amount, :status, :debit_status, :failure_reason)
            ON DUPLICATE KEY UPDATE
                account_id = VALUES(account_id),
                amount = VALUES(amount),
                status = VALUES(status),
                debit_status = VALUES(debit_status),
                failure_reason = VALUES(failure_reason)
        """)

        for transaction_id, account_number, amount, status, debit_status, failure_reason in TRANSACTIONS:
            db.execute(transaction_query, {
                "transaction_id": transaction_id,
                "account_id": account_ids[account_number],
                "amount": Decimal(amount),
                "status": status,
                "debit_status": debit_status,
                "failure_reason": failure_reason,
            })

        transaction_ids = {
            row.transaction_id: row.id
            for row in db.execute(text("SELECT id, transaction_id FROM transactions"))
        }

        refund_query = text("""
            INSERT INTO refund_requests
                (request_id, transaction_id, amount, reason, status)
            VALUES
                (:request_id, :transaction_id, :amount, :reason, 'PENDING')
            ON DUPLICATE KEY UPDATE
                transaction_id = VALUES(transaction_id),
                amount = VALUES(amount),
                reason = VALUES(reason),
                status = 'PENDING'
        """)

        for request_id, transaction_id, amount, reason in REFUND_REQUESTS:
            db.execute(refund_query, {
                "request_id": request_id,
                "transaction_id": transaction_ids[transaction_id],
                "amount": Decimal(amount),
                "reason": reason,
            })

    print("Seeded 20 accounts, 20 transactions, and 5 pending refund requests.")
    print("Try customer transaction IDs TXN001 through TXN020.")


if __name__ == "__main__":
    seed_data()
