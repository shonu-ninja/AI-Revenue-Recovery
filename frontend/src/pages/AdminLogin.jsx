import { useState } from "react";
import {
  Lock,
  ArrowLeft,
  ShieldCheck,
  Eye,
  EyeOff,
  Sparkles,
  Key,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

function AdminLogin() {
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const ADMIN_PASSWORD = "admin123";

  const handleLogin = (e) => {
    e.preventDefault();

    if (!password.trim()) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);

    // Simulate authentication delay
    setTimeout(() => {
      if (password === ADMIN_PASSWORD) {
        sessionStorage.setItem("adminAuthenticated", "true");
        navigate("/admin");
      } else {
        setError("❌ Incorrect admin password. Please try again.");
        setPassword("");
        setLoading(false);
      }
    }, 500);
  };

  return (
    <div className="admin-login-page">
      {/* BACKGROUND DECORATION */}
      <div className="login-glow glow-one"></div>
      <div className="login-glow glow-two"></div>

      {/* BACK TO HOME */}
      <Link to="/" className="login-back-button">
        <ArrowLeft size={17} />
        Back to Home
      </Link>

      {/* LOGIN CARD */}
      <div className="admin-login-card">
        {/* ICON */}
        <div className="admin-icon-wrapper">
          <div className="admin-icon">
            <ShieldCheck size={36} />
          </div>
        </div>

        {/* TITLE */}
        <div className="login-heading">
          <div className="secure-label">
            <Sparkles size={14} />
            SECURE ACCESS
          </div>
          <h1>👨‍💼 Admin Portal</h1>
          <p>
            Sign in to access the AI Revenue Recovery
            control center and manage refund operations.
          </p>
        </div>

        {/* FORM */}
        <form onSubmit={handleLogin}>
          <label className="login-label">
            Administrator Password
          </label>

          <div className={`password-field ${error ? "password-error" : ""}`}>
            <Key size={19} />
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError("");
              }}
              autoFocus
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          </div>

          {/* ERROR */}
          {error && (
            <div className="login-error">
              <span>!</span>
              {error}
            </div>
          )}

          {/* LOGIN BUTTON */}
          <button
            type="submit"
            className="admin-login-button"
            disabled={loading}
          >
            <ShieldCheck size={19} />
            {loading ? "Authenticating..." : "Access Admin Dashboard"}
          </button>

          {/* HINT */}
          <div className="login-hint">
            <Lock size={14} />
            <span>Default password: <strong>admin123</strong></span>
          </div>
        </form>

        {/* SECURITY INFO */}
        <div className="security-info">
          <Lock size={15} />
          <span>Authorized administrators only</span>
        </div>
      </div>

      {/* FOOTER */}
      <div className="login-footer">
        🤖 AI Revenue Recovery • Secure Administration Portal v1.0
      </div>
    </div>
  );
}

export default AdminLogin;





