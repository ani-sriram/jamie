import React, { useState } from 'react';
import axios from 'axios';
import './SignIn.css';

const SignIn = ({ onSignIn }) => {
  const [username, setUsername] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;

    setIsLoading(true);
    setError('');
    
    try {
      const backendUrl = process.env.REACT_APP_API_URL;
      if (!backendUrl) {
        throw new Error('Backend API URL not configured');
      }

      const response = await axios.post(`${backendUrl}/signin`, {
        username: username.trim()
      });
      
      onSignIn(response.data.user_id, response.data.token);
    } catch (error) {
      console.error('Sign in error:', error);
      if (error.response?.data?.detail) {
        setError(error.response.data.detail);
      } else if (error.message) {
        setError(error.message);
      } else {
        setError('Failed to sign in. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="signin-container">
      <div className="signin-card">
        <h1>Jamie</h1>
        <p>Sign in</p>
        
        <form onSubmit={handleSubmit} className="signin-form">
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}
          <div className="input-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              disabled={isLoading}
            />
          </div>
          
          <button 
            type="submit" 
            className="signin-button"
            disabled={isLoading || !username.trim()}
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default SignIn;
