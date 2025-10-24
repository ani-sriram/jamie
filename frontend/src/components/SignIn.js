import React, { useState } from 'react';
import './SignIn.css';

const SignIn = ({ onSignIn }) => {
  const [username, setUsername] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;

    setIsLoading(true);
    
    try {
      // Generate a simple JWT token (for testing purposes)
      const token = btoa(JSON.stringify({ 
        username: username.trim(), 
        timestamp: Date.now() 
      }));
      
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      onSignIn(username.trim(), token);
    } catch (error) {
      console.error('Sign in error:', error);
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
