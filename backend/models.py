from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import enum


# =========================================================
# ENUMS
# =========================================================

class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PENDING = "PENDING"


class DebitStatus(str, enum.Enum):
    DEBITED = "DEBITED"
    NOT_DEBITED = "NOT_DEBITED"
    PARTIAL = "PARTIAL"


class FailureReason(str, enum.Enum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    NETWORK_ISSUE = "NETWORK_ISSUE"
    BANK_ISSUE = "BANK_ISSUE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"
    OTHER = "OTHER"


class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


class RecoveryAction(str, enum.Enum):
    REFUND = "REFUND"
    REVIEW = "REVIEW"
    REJECT = "REJECT"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    NO_ACTION = "NO_ACTION"


# =========================================================
# ACCOUNT MODEL
# =========================================================

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    balance = Column(DECIMAL(15, 2), default=0.00)
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    refund_requests = relationship("RefundRequest", back_populates="account", cascade="all, delete-orphan")


# =========================================================
# TRANSACTION MODEL
# =========================================================

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, index=True, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    debit_status = Column(Enum(DebitStatus), default=DebitStatus.NOT_DEBITED)
    failure_reason = Column(Enum(FailureReason), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # AI Analysis Fields
    risk_score = Column(Float, nullable=True)
    recovery_action = Column(Enum(RecoveryAction), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    analysis_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="transactions")
    refund_requests = relationship("RefundRequest", back_populates="transaction", cascade="all, delete-orphan")
    recovery_actions = relationship("RecoveryActionLog", back_populates="transaction", cascade="all, delete-orphan")


# =========================================================
# REFUND REQUEST MODEL
# =========================================================

class RefundRequest(Base):
    __tablename__ = "refund_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), unique=True, index=True, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(RefundStatus), default=RefundStatus.PENDING)
    admin_notes = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(100), nullable=True)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="refund_requests")
    account = relationship("Account", back_populates="refund_requests")


# =========================================================
# RECOVERY ACTION LOG MODEL
# =========================================================

class RecoveryActionLog(Base):
    __tablename__ = "recovery_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    recommended_action = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    action_taken = Column(String(50), nullable=False)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    transaction = relationship("Transaction", back_populates="recovery_actions")


# =========================================================
# AUDIT LOG MODEL
# =========================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    actor = Column(String(50), nullable=False)  # AI_AGENT, ADMIN, CUSTOMER, SYSTEM
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    transaction = relationship("Transaction")