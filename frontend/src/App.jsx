import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import Admin from "./pages/Admin";
import Customer from "./pages/Customer";
import AdminLogin from "./pages/AdminLogin";
import "./App.css";

function ProtectedAdmin() {
  const authenticated = sessionStorage.getItem("adminAuthenticated") === "true";

  if (!authenticated) {
    return <Navigate to="/admin-login" replace />;
  }

  return <Admin />;
}

function Home() {
  return (
    <div className="home-page">
      <div className="home-card">
        <h1>🤖 AI Revenue Recovery</h1>
        <p>Intelligent payment failure recovery and refund management system</p>

        <div className="stats-preview">
          <div className="stat-item">
            <span className="stat-value">500+</span>
            <span className="stat-label">Transactions Processed</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">₹1.2Cr</span>
            <span className="stat-label">Revenue Recovered</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">98%</span>
            <span className="stat-label">AI Accuracy</span>
          </div>
        </div>

        <div className="role-buttons">
          <Link to="/admin-login" className="role-button admin-role">
            👨‍💼 Admin Portal
            <span className="role-sub">Manage refunds & analytics</span>
          </Link>

          <Link to="/customer" className="role-button customer-role">
            👤 Customer Portal
            <span className="role-sub">Check transaction & request refund</span>
          </Link>
        </div>

        <div className="home-footer">
          <span>🔒 Secure • AI-Powered • Automated Recovery</span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    localStorage.setItem("theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  return (
    <>
      <button
        className="theme-toggle"
        type="button"
        onClick={() => setDarkMode((current) => !current)}
        aria-label={darkMode ? "Use light mode" : "Use dark mode"}
        title={darkMode ? "Use light mode" : "Use dark mode"}
      >
        {darkMode ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/admin-login" element={<AdminLogin />} />
          <Route path="/admin" element={<ProtectedAdmin />} />
          <Route path="/customer" element={<Customer />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;