import React, { useState } from "react";
import { AuthenticationDetails, CognitoUser } from "amazon-cognito-identity-js";
import { userPool } from "../auth/cognito";
import "./Login.css";

export const Login: React.FC<{ onLogin: () => void }> = ({ onLogin }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (isSignUp) {
      userPool.signUp(email, password, [], [], (err) => {
        setLoading(false);
        if (err) {
          setError(err.message || JSON.stringify(err));
          return;
        }
        setIsConfirming(true);
        setIsSignUp(false);
      });
    } else {
      const authenticationDetails = new AuthenticationDetails({
        Username: email,
        Password: password,
      });

      const cognitoUser = new CognitoUser({
        Username: email,
        Pool: userPool,
      });

      cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: () => {
          setLoading(false);
          onLogin();
        },
        onFailure: (err: { code?: string; name?: string; message?: string }) => {
          setLoading(false);
          if (err.code === "UserNotConfirmedException" || err.name === "UserNotConfirmedException") {
            setIsConfirming(true);
            setError("Please check your email for a verification code.");
          } else {
            setError(err.message ?? JSON.stringify(err));
          }
        },
      });
    }
  };

  const handleConfirm = (e: React.SyntheticEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: userPool,
    });

    cognitoUser.confirmRegistration(verificationCode, true, (err: { message?: string } | null) => {
      setLoading(false);
      if (err) {
        setError(err.message ?? JSON.stringify(err));
        return;
      }
      setIsConfirming(false);
      setVerificationCode("");
      alert("Verification successful! Please log in.");
    });
  };

  const handleResendCode = () => {
    setError("");
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: userPool,
    });
    cognitoUser.resendConfirmationCode((err) => {
      if (err) {
        setError(err.message || JSON.stringify(err));
        return;
      }
      alert("Verification code resent.");
    });
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1 className="login-title">Traffic Simulation</h1>
        <p className="login-subtitle">
          {isConfirming
            ? "We emailed you a verification code"
            : isSignUp
            ? "Create a new account"
            : "Sign in to access your simulation"}
        </p>

        {error && <div className="login-error">{error}</div>}

        {isConfirming ? (
          <>
            <form onSubmit={handleConfirm} className="login-form">
              <div className="input-group">
                <label htmlFor="code">Verification Code</label>
                <input
                  id="code"
                  type="text"
                  value={verificationCode}
                  onChange={(e) => { setVerificationCode(e.target.value); }}
                  placeholder="Enter 6-digit code"
                  required
                />
              </div>

              <button type="submit" className="login-btn" disabled={loading}>
                {loading ? "Verifying..." : "Verify Account"}
              </button>
            </form>

            <div className="login-toggle" style={{ display: "flex", justifyContent: "space-between", padding: "0 10px" }}>
              <button type="button" onClick={handleResendCode} style={{ background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", padding: 0 }}>
                Resend Code
              </button>
              <button type="button" onClick={() => { setIsConfirming(false); }} style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", padding: 0 }}>
                Back to Login
              </button>
            </div>
          </>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="login-form">
              <div className="input-group">
                <label htmlFor="email">Email address</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                  }}
                  placeholder="you@example.com"
                  required
                />
              </div>

              <div className="input-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                  }}
                  placeholder="••••••••"
                  required
                />
              </div>

              <button type="submit" className="login-btn" disabled={loading}>
                {loading ? "Processing..." : isSignUp ? "Sign Up" : "Sign In"}
              </button>
            </form>

            <div className="login-toggle">
              {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                }}
              >
                {isSignUp ? "Sign In" : "Sign Up"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
