import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SignIn from './components/SignIn';
import Chat from './components/Chat';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);

  useEffect(() => {
    // Check for existing session
    const savedUser = localStorage.getItem('user');
    const savedToken = localStorage.getItem('token');
    if (savedUser && savedToken) {
      setUser(savedUser);
      setToken(savedToken);
    }
  }, []);

  const handleSignIn = (username, jwtToken) => {
    setUser(username);
    setToken(jwtToken);
    localStorage.setItem('user', username);
    localStorage.setItem('token', jwtToken);
  };

  const handleSignOut = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('user');
    localStorage.removeItem('token');
  };

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route 
            path="/signin" 
            element={
              user ? <Navigate to="/chat" replace /> : <SignIn onSignIn={handleSignIn} />
            } 
          />
          <Route 
            path="/chat" 
            element={
              user ? <Chat user={user} token={token} onSignOut={handleSignOut} /> : <Navigate to="/signin" replace />
            } 
          />
          <Route path="/" element={<Navigate to="/signin" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
