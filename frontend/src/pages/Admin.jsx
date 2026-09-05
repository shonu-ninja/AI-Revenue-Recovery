import { useEffect, useState } from "react";
import {
  RefreshCw,
  IndianRupee,
  AlertTriangle,
  Clock,
  CheckCircle,
  XCircle,
  Brain,
  ArrowLeft,
  TrendingUp,
  Bot,
  ShieldCheck,
  History,
  User,
  DollarSign,
  Zap,
  Database,
  Send,
  Upload,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { Link } from "react-router-dom";
import "../App.css";

function Admin() {
  const [transactions, setTransactions] = useState([]);
  const [refundRequests, setRefundRequests] = useState([]);
  const [refundHistory, setRefundHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refundLoading, setRefundLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [selectedFailureReason, setSelectedFailureReason] = useState("OTHER");
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);
  const [importState, setImportState] = useState({
    file: null,
    stagingId: "",
    columns: [],
    preview: [],
    rowCount: 0,
    errors: [],
    canApprove: false,
    uploading: false,
    approving: false,
    message: "",
  });

  const FAILURE_REASONS = [
    "INSUFFICIENT_FUNDS",
    "NETWORK_ISSUE",
    "BANK_ISSUE",
    "GATEWAY_TIMEOUT",
    "TECHNICAL_ERROR",
    "OTHER"
  ];

  // ==========================================
  // FETCH TRANSACTIONS
  // ==========================================

  const fetchTransactions = async () => {
    try {
      const response = await fetch("/api/transactions");
      if (!response.ok) throw new Error("Failed to fetch transactions");
      const data = await response.json();
      setTransactions(Array.isArray(data) ? data : data.transactions || []);
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  // ==========================================
  // FETCH PENDING REFUND REQUESTS
  // ==========================================

  const fetchRefundRequests = async () => {
    try {
      const response = await fetch("/api/refunds?status=PENDING");
      if (!response.ok) throw new Error("Failed to fetch refund requests");
      const data = await response.json();
      setRefundRequests(Array.isArray(data) ? data : data.refund_requests || []);
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  // ==========================================
  // FETCH REFUND HISTORY
  // ==========================================

  const fetchRefundHistory = async () => {
    try {
      setHistoryLoading(true);
      const response = await fetch("/api/refunds/history");
      if (!response.ok) throw new Error("Failed to fetch refund history");
      const data = await response.json();
      setRefundHistory(Array.isArray(data) ? data : data.refund_history || []);
    } catch (err) {
      console.error(err);
      setRefundHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  // ==========================================
  // FETCH DASHBOARD STATISTICS
  // ==========================================

  const fetchStats = async () => {
    try {
      const response = await fetch("/api/analytics/stats");
      if (!response.ok) throw new Error("Failed to fetch dashboard statistics");
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error(err);
      setStats(null);
    }
  };

  // ==========================================
  // FETCH EVERYTHING
  // ==========================================

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError("");
      await Promise.all([
        fetchTransactions(),
        fetchRefundRequests(),
        fetchRefundHistory(),
        fetchStats(),
      ]);
    } catch (err) {
      console.error(err);
      setError("Could not connect to backend. Please make sure the server is running.");
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // AI ANALYSIS
  // ==========================================

  const analyzeTransaction = async (transactionId) => {
    try {
      setAnalysisLoading(true);
      setSelectedAnalysis(null);
      setError("");

      const response = await fetch(
        `/api/transactions/${transactionId}/analyze?failure_reason=${selectedFailureReason}`,
        { method: "POST" }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "AI analysis failed");
      }

      setSelectedAnalysis(data);
      setShowAnalysisModal(true);
      await fetchDashboard();
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const sendManualRefundRequest = async (transactionId) => {
    try {
      setRefundLoading(true);
      setError("");

      const response = await fetch(
        `/api/refunds?transaction_id=${transactionId}&reason=${encodeURIComponent("Admin requested manual refund for high-value failed payment")}`,
        { method: "POST" }
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not create refund request");
      }

      await fetchDashboard();
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setRefundLoading(false);
    }
  };

  const previewImport = async (file) => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setImportState((current) => ({ ...current, file, uploading: true, message: "", errors: [] }));
    try {
      const response = await fetch("/api/admin/import/preview", { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not preview file");
      setImportState((current) => ({
        ...current,
        stagingId: data.staging_id,
        columns: data.columns,
        preview: data.preview,
        rowCount: data.row_count,
        errors: [...(data.missing_columns || []).map((column) => `Missing required column: ${column}`), ...(data.validation_errors || [])],
        canApprove: data.can_approve,
        uploading: false,
      }));
    } catch (err) {
      setImportState((current) => ({ ...current, uploading: false, errors: [err.message] }));
    }
  };

  const removeImportColumn = (column) => {
    const allowedColumns = ["transaction_id", "account_number", "customer_name", "email", "amount", "status", "debit_status", "failure_reason"];
    setImportState((current) => ({
      ...current,
      columns: current.columns.filter((item) => item !== column),
      canApprove: ["transaction_id", "account_number", "amount", "status", "debit_status"].every((required) => current.columns.filter((item) => item !== column).includes(required)) && current.columns.filter((item) => item !== column).every((item) => allowedColumns.includes(item)),
    }));
  };

  const restoreImportColumns = () => {
    previewImport(importState.file);
  };

  const approveImport = async () => {
    setImportState((current) => ({ ...current, approving: true, message: "" }));
    try {
      const response = await fetch("/api/admin/import/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staging_id: importState.stagingId, columns: importState.columns }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Import approval failed");
      setImportState((current) => ({ ...current, approving: false, message: data.message, stagingId: "", preview: [], columns: [], canApprove: false }));
      await fetchDashboard();
    } catch (err) {
      setImportState((current) => ({ ...current, approving: false, errors: [err.message] }));
    }
  };

  // ==========================================
  // APPROVE REFUND
  // ==========================================

  const approveRefund = async (requestId) => {
    const confirmed = window.confirm("Are you sure you want to approve this refund?");
    if (!confirmed) return;

    try {
      setRefundLoading(true);
      setError("");

      const response = await fetch(
        `/api/admin/refunds/${requestId}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved_by: "ADMIN",
            admin_notes: "Approved by admin"
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Refund approval failed");
      }

      alert(`Refund approved successfully!\n\nTransaction: ${data.transaction_id}\nAmount: ₹${Number(data.refund_amount || 0).toLocaleString("en-IN")}`);
      await fetchDashboard();
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setRefundLoading(false);
    }
  };

  // ==========================================
  // REJECT REFUND
  // ==========================================

  const rejectRefund = async (requestId) => {
    const confirmed = window.confirm("Are you sure you want to reject this refund request?");
    if (!confirmed) return;

    try {
      setRefundLoading(true);
      setError("");

      const response = await fetch(
        `/api/admin/refunds/${requestId}/reject`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved_by: "ADMIN",
            admin_notes: "Rejected by admin"
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Refund rejection failed");
      }

      alert("Refund request rejected.");
      await fetchDashboard();
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setRefundLoading(false);
    }
  };

  // ==========================================
  // INITIAL LOAD
  // ==========================================

  useEffect(() => {
    fetchDashboard();
  }, []);

  // ==========================================
  // LOCAL STATISTICS
  // ==========================================

  const failedAndDebited = transactions.filter(
    (t) => String(t.status || "").toUpperCase() === "FAILED"
  );

  const refundedTransactions = transactions.filter(
    (t) => String(t.status || "").toUpperCase() === "REFUNDED"
  );

  const revenueAtRisk = failedAndDebited.reduce(
    (total, t) => total + Number(t.amount || 0),
    0
  );

  const totalRefunded = refundedTransactions.reduce(
    (total, t) => total + Number(t.amount || 0),
    0
  );

  const transactionStats = stats?.transactions || {};
  const refundStats = stats?.refunds || {};
  const recoveryStats = stats?.recovery || {};

  const totalTransactions = transactionStats.total ?? transactions.length;
  const successfulCount = transactionStats.successful ?? 0;
  const failedCount = transactionStats.failed ?? 0;
  const dashboardRevenueAtRisk = transactionStats.revenue_at_risk ?? revenueAtRisk;
  const dashboardTotalRefunded = transactionStats.total_refunded ?? totalRefunded;
  const pendingCount = refundStats.pending ?? refundRequests.length;
  const rejectedCount = refundStats.rejected ?? 0;
  const recoveryRate = recoveryStats.recovery_rate ?? 0;
  const automaticRefunds = recoveryStats.automatic_refunds ?? 0;
  const adminRefunds = recoveryStats.admin_refunds ?? 0;
  const aiAnalyzedCount = stats?.ai_analyzed_count ?? 0;
  const autoRefundLimit = stats?.auto_refund_limit ?? 50000;

  // ==========================================
  // FORMAT DATE
  // ==========================================

  const formatDate = (date) => {
    if (!date) return "-";
    return new Date(date).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // ==========================================
  // UI
  // ==========================================

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div>
          <h1>🤖 AI Revenue Recovery</h1>
          <p>Admin Recovery Control Center</p>
        </div>
        <div className="admin">
          <span className="status-dot"></span>
          ADMIN
          <Link to="/" className="back-button">
            <ArrowLeft size={17} />
            Home
          </Link>
        </div>
      </header>

      <main className="container">
        {/* DASHBOARD HEADING */}
        <div className="dashboard-heading">
          <div>
            <h2>📊 Admin Dashboard</h2>
            <p>Monitor AI-driven revenue recovery and refund operations</p>
          </div>
          <button
            className="refresh-button"
            onClick={fetchDashboard}
            disabled={loading || refundLoading || analysisLoading}
          >
            <RefreshCw size={18} />
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {/* ERROR */}
        {error && (
          <div className="error">
            <AlertTriangle size={18} />
            {error}
          </div>
        )}

        {/* MAIN KPI CARDS */}
        <div className="cards">
          <div className="card">
            <div className="icon revenue">
              <IndianRupee size={24} />
            </div>
            <div>
              <p>Revenue at Risk</p>
              <h3>₹{Number(dashboardRevenueAtRisk).toLocaleString("en-IN")}</h3>
            </div>
          </div>

          <div className="card">
            <div className="icon failed">
              <AlertTriangle size={24} />
            </div>
            <div>
              <p>Failed Transactions</p>
              <h3>{failedCount}</h3>
            </div>
          </div>

          <div className="card">
            <div className="icon pending">
              <Clock size={24} />
            </div>
            <div>
              <p>Pending Refunds</p>
              <h3>{pendingCount}</h3>
            </div>
          </div>

          <div className="card">
            <div className="icon success">
              <TrendingUp size={24} />
            </div>
            <div>
              <p>Recovery Rate</p>
              <h3>{recoveryRate}%</h3>
            </div>
          </div>
        </div>

        {/* TRANSACTION FILE IMPORT */}
        <section className="section import-section">
          <div className="section-header">
            <h2><Upload size={21} /> Transaction File Lab</h2>
            <p>Upload a CSV, remove unwanted columns, preview the data, then approve the database update.</p>
          </div>
          <div className="import-toolbar">
            <label className="file-picker">
              <Upload size={17} />
              Choose CSV file
              <input type="file" accept=".csv,text/csv" onChange={(event) => previewImport(event.target.files?.[0])} />
            </label>
            {importState.file && <span className="file-name">{importState.file.name} · {importState.rowCount} rows</span>}
            {importState.columns.length > 0 && (
              <button className="refresh-button" type="button" onClick={restoreImportColumns}>
                <RotateCcw size={16} /> Restore columns
              </button>
            )}
          </div>
          {importState.errors.length > 0 && (
            <div className="error import-errors">{importState.errors.slice(0, 5).join(" · ")}</div>
          )}
          {importState.message && <div className="success-message">{importState.message}</div>}
          {importState.columns.length > 0 && (
            <>
              <div className="import-columns">
                {importState.columns.map((column) => (
                  <button key={column} type="button" className="column-chip" onClick={() => removeImportColumn(column)} title={`Remove ${column}`}>
                    {column}<Trash2 size={13} />
                  </button>
                ))}
              </div>
              <div className="table-wrapper import-preview">
                <table>
                  <thead><tr>{importState.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>{importState.preview.map((row, index) => <tr key={`${row.transaction_id || "row"}-${index}`}>{importState.columns.map((column) => <td key={column}>{row[column] || "-"}</td>)}</tr>)}</tbody>
                </table>
              </div>
              <div className="import-footer">
                <span>Showing first {importState.preview.length} of {importState.rowCount} rows</span>
                <button className="approve-button" type="button" onClick={approveImport} disabled={!importState.canApprove || importState.approving || importState.uploading}>
                  <CheckCircle size={17} /> {importState.approving ? "Updating database..." : "Approve & update database"}
                </button>
              </div>
            </>
          )}
        </section>

        {/* RECOVERY OVERVIEW */}
        <section className="section">
          <div className="section-header">
            <h2>
              <ShieldCheck size={21} />
              Recovery Overview
            </h2>
            <p>Overall performance of the revenue recovery system</p>
          </div>
          <div className="cards">
            <div className="card">
              <div className="icon">
                <Database size={24} />
              </div>
              <div>
                <p>Total Transactions</p>
                <h3>{totalTransactions}</h3>
              </div>
            </div>

            <div className="card">
              <div className="icon success">
                <CheckCircle size={24} />
              </div>
              <div>
                <p>Successful</p>
                <h3>{successfulCount}</h3>
              </div>
            </div>

            <div className="card">
              <div className="icon revenue">
                <DollarSign size={24} />
              </div>
              <div>
                <p>Total Refunded</p>
                <h3>₹{Number(dashboardTotalRefunded).toLocaleString("en-IN")}</h3>
              </div>
            </div>

            <div className="card">
              <div className="icon success">
                <CheckCircle size={24} />
              </div>
              <div>
                <p>AI Analyzed</p>
                <h3>{aiAnalyzedCount}</h3>
              </div>
            </div>
          </div>
        </section>

        {/* AI RECOVERY PERFORMANCE */}
        <section className="section">
          <div className="section-header">
            <h2>
              <Bot size={21} />
              AI Recovery Performance
            </h2>
            <p>Breakdown of how the recovery engine handled failed payments</p>
          </div>
          <div className="cards">
            <div className="card">
              <div className="icon success">
                <Zap size={24} />
              </div>
              <div>
                <p>Automatic Refunds</p>
                <h3>{automaticRefunds}</h3>
                <small>AI-approved</small>
              </div>
            </div>

            <div className="card">
              <div className="icon revenue">
                <ShieldCheck size={24} />
              </div>
              <div>
                <p>Admin Refunds</p>
                <h3>{adminRefunds}</h3>
                <small>Manually approved</small>
              </div>
            </div>

            <div className="card">
              <div className="icon failed">
                <XCircle size={24} />
              </div>
              <div>
                <p>Rejected</p>
                <h3>{rejectedCount}</h3>
                <small>Refund requests rejected</small>
              </div>
            </div>

            <div className="card">
              <div className="icon revenue">
                <IndianRupee size={24} />
              </div>
              <div>
                <p>Auto Refund Limit</p>
                <h3>₹{Number(autoRefundLimit).toLocaleString("en-IN")}</h3>
                <small>Per transaction</small>
              </div>
            </div>
          </div>
        </section>

        {/* FAILED PAYMENTS */}
        <section className="section">
          <div className="section-header">
            <h2>Failed Payments</h2>
            <p>Under ₹5,000: AI refunds automatically. Higher amounts go to manual refund review.</p>
          </div>

          {/* Failure Reason Selector */}
          <div className="failure-reason-selector">
            <label>Failure Reason:</label>
            <select
              value={selectedFailureReason}
              onChange={(e) => setSelectedFailureReason(e.target.value)}
              className="failure-select"
            >
              {FAILURE_REASONS.map((reason) => (
                <option key={reason} value={reason}>
                  {reason.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>TRANSACTION</th>
                  <th>CUSTOMER</th>
                  <th>AMOUNT</th>
                  <th>DEBIT STATUS</th>
                  <th>STATUS</th>
                  <th>AI SCORE</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="7" className="empty">Loading transactions...</td>
                  </tr>
                ) : failedAndDebited.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty">No failed transactions.</td>
                  </tr>
                ) : (
                  failedAndDebited.map((transaction) => (
                    <tr key={transaction.id} className="transaction-row">
                      <td><strong>{transaction.transaction_id}</strong></td>
                      <td>{transaction.customer_name}</td>
                      <td>₹{Number(transaction.amount || 0).toLocaleString("en-IN")}</td>
                      <td>
                        <span className={`badge ${transaction.debit_status === "DEBITED" ? "failed-badge" : "pending-badge"}`}>
                          {transaction.debit_status}
                        </span>
                      </td>
                      <td>
                        <span className="badge failed-badge">{transaction.status}</span>
                      </td>
                      <td>
                        {transaction.risk_score ? (
                          <span className={`risk-score-badge ${transaction.risk_score < 40 ? "low-risk" : transaction.risk_score < 70 ? "medium-risk" : "high-risk"}`}>
                            {transaction.risk_score}%
                          </span>
                        ) : (
                          <span className="badge pending-badge">-</span>
                        )}
                      </td>
                      <td>
                        {Number(transaction.amount || 0) < autoRefundLimit ? (
                          <button
                            className="analyze-button"
                            onClick={() => analyzeTransaction(transaction.transaction_id)}
                            disabled={analysisLoading || refundLoading}
                          >
                            <Brain size={16} />
                            AI Refund
                          </button>
                        ) : (
                          <button
                            className="approve-button"
                            onClick={() => sendManualRefundRequest(transaction.transaction_id)}
                            disabled={analysisLoading || refundLoading}
                          >
                            <Send size={16} />
                            Refund
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* PENDING REFUND REQUESTS */}
        <section className="section">
          <div className="section-header">
            <h2>
              <Clock size={21} />
              Refund Operations
            </h2>
            <p>Customer and admin requests waiting for approval. Click Approve to send the refund.</p>
          </div>

          {refundLoading ? (
            <div className="empty">Loading refund requests...</div>
          ) : refundRequests.length === 0 ? (
            <div className="empty">
              <CheckCircle size={20} />
              No pending refund requests.
            </div>
          ) : (
            <div className="refund-list">
              {refundRequests.map((request) => (
                <div className="refund-card" key={request.id}>
                  <div className="refund-info">
                    <div className="refund-title">
                      <strong>{request.transaction_code || request.transaction_id}</strong>
                      <span className="badge pending-badge">PENDING</span>
                    </div>
                    <div className="refund-details">
                      <p><strong>Customer:</strong> {request.customer_name}</p>
                      <p><strong>Account:</strong> {request.account_number}</p>
                      <p><strong>Amount:</strong> ₹{Number(request.amount || 0).toLocaleString("en-IN")}</p>
                      <p><strong>Reason:</strong> {request.reason}</p>
                      <p><strong>Requested:</strong> {formatDate(request.requested_at)}</p>
                    </div>
                  </div>
                  <div className="refund-actions">
                    <button
                      className="approve-button"
                      onClick={() => approveRefund(request.id)}
                      disabled={refundLoading}
                    >
                      <CheckCircle size={17} />
                      {refundLoading ? "Processing..." : "Approve"}
                    </button>
                    <button
                      className="reject-button"
                      onClick={() => rejectRefund(request.id)}
                      disabled={refundLoading}
                    >
                      <XCircle size={17} />
                      {refundLoading ? "Processing..." : "Reject"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* REFUND HISTORY */}
        <section className="section">
          <div className="section-header">
            <h2>
              <History size={21} />
              Refund History
            </h2>
            <p>Complete record of processed refund requests</p>
          </div>

          {historyLoading ? (
            <div className="empty">Loading refund history...</div>
          ) : refundHistory.length === 0 ? (
            <div className="empty">
              <History size={20} />
              No refund history available.
            </div>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>TRANSACTION</th>
                    <th>CUSTOMER</th>
                    <th>AMOUNT</th>
                    <th>STATUS</th>
                    <th>REQUESTED</th>
                    <th>PROCESSED</th>
                  </tr>
                </thead>
                <tbody>
                  {refundHistory.map((refund) => (
                    <tr key={refund.id}>
                      <td><strong>#{refund.id}</strong></td>
                      <td><strong>{refund.transaction_code}</strong></td>
                      <td>
                        <div className="history-customer">
                          <User size={15} />
                          {refund.customer_name}
                        </div>
                      </td>
                      <td><strong>₹{Number(refund.amount || 0).toLocaleString("en-IN")}</strong></td>
                      <td>
                        {refund.status === "COMPLETED" ? (
                          <span className="badge success-badge">
                            <CheckCircle size={14} />
                            COMPLETED
                          </span>
                        ) : refund.status === "REJECTED" ? (
                          <span className="badge failed-badge">
                            <XCircle size={14} />
                            REJECTED
                          </span>
                        ) : (
                          <span className="badge pending-badge">
                            <Clock size={14} />
                            {refund.status}
                          </span>
                        )}
                      </td>
                      <td>{formatDate(refund.requested_at)}</td>
                      <td>{formatDate(refund.processed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {/* ANALYSIS MODAL */}
      {showAnalysisModal && selectedAnalysis && (
        <div className="modal-overlay" onClick={() => setShowAnalysisModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowAnalysisModal(false)}>×</button>
            <div className="ai-analysis">
              <div className="analysis-header">
                <div>
                  <span className="analysis-label">TRANSACTION</span>
                  <h3>{selectedAnalysis.transaction?.transaction_id}</h3>
                </div>
                <span className={`badge ${selectedAnalysis.transaction?.status === "REFUNDED" ? "success-badge" : "failed-badge"}`}>
                  {selectedAnalysis.transaction?.status}
                </span>
              </div>

              <div className="analysis-grid">
                <div>
                  <span>Customer</span>
                  <strong>{selectedAnalysis.transaction?.customer_name}</strong>
                </div>
                <div>
                  <span>Amount</span>
                  <strong>₹{Number(selectedAnalysis.transaction?.amount || 0).toLocaleString("en-IN")}</strong>
                </div>
                <div>
                  <span>Debit Status</span>
                  <strong>{selectedAnalysis.transaction?.debit_status}</strong>
                </div>
              </div>

              <div className="ai-decision">
                <div>
                  <span className="analysis-label">AI RISK SCORE</span>
                  <div className={`risk-score-display ${selectedAnalysis.ai_decision?.risk_score < 40 ? "low-risk" : selectedAnalysis.ai_decision?.risk_score < 70 ? "medium-risk" : "high-risk"}`}>
                    {selectedAnalysis.ai_decision?.risk_score}%
                  </div>
                </div>
                <div>
                  <span className="analysis-label">RECOMMENDED ACTION</span>
                  <div className={`recommended-action-display ${selectedAnalysis.ai_decision?.recommended_action === "REFUND" ? "refund-action" : selectedAnalysis.ai_decision?.recommended_action === "REVIEW" ? "review-action" : "reject-action"}`}>
                    {selectedAnalysis.ai_decision?.recommended_action}
                  </div>
                </div>
                <div>
                  <span className="analysis-label">CONFIDENCE</span>
                  <div className="confidence-display">
                    {selectedAnalysis.ai_decision?.confidence || 85}%
                  </div>
                </div>
              </div>

              <div className="ai-reason">
                <span className="analysis-label">AI REASON</span>
                <p>{selectedAnalysis.ai_decision?.reason}</p>
                {selectedAnalysis.action_executed && (
                  <div className="success-message">
                    <CheckCircle size={18} />
                    <strong>Automatic refund completed successfully.</strong>
                  </div>
                )}
                {selectedAnalysis.refund_request?.success && (
                  <div className="success-message">
                    <Clock size={18} />
                    <strong>Refund request sent for admin review.</strong>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Admin;