import React, { useState } from 'react';
import { AuthenticationDetails, CognitoUser } from 'amazon-cognito-identity-js';
import { userPool } from '../auth/cognito';
import './Login.css';

export const Login: React.FC<{ onLogin: () => void }> = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (isSignUp) {
      userPool.signUp(email, password, [], [], (err) => {
        setLoading(false);
        if (err) {
          setError(err.message || JSON.stringify(err));
          return;
        }
        alert('Sign up successful! Please check your email to verify your account, then log in.');
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
        onFailure: (err: Error) => {
          setLoading(false);
          setError(err.message || JSON.stringify(err));
        },
      });
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1 className="login-title">Traffic Simulation</h1>
        <p className="login-subtitle">
          {isSignUp ? 'Create a new account' : 'Sign in to access your simulation'}
        </p>
        
        {error && <div className="login-error">{error}</div>}
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="input-group">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); }}
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
              onChange={(e) => { setPassword(e.target.value); }}
              placeholder="••••••••"
              required
            />
          </div>
          
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? 'Processing...' : (isSignUp ? 'Sign Up' : 'Sign In')}
          </button>
        </form>
        
        <div className="login-toggle">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}{' '}
          <button type="button" onClick={() => { setIsSignUp(!isSignUp); }}>
            {isSignUp ? 'Sign In' : 'Sign Up'}
          </button>
        </div>
      </div>
    </div>
  );
};
