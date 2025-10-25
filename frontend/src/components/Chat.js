import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './Chat.css';

const Chat = ({ user, token, onSignOut }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const messagesEndRef = useRef(null);

  const getBackendUrl = () => {
    const backendUrl = process.env.REACT_APP_API_URL;
    if (!backendUrl) {
      throw new Error('Backend API URL not configured');
    }
    return backendUrl;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const response = await axios.get(`${getBackendUrl()}/chat/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSessions(response.data.sessions);
      
      // If no current session and we have sessions, load the first one
      if (!currentSessionId && response.data.sessions.length > 0) {
        loadSessionHistory(response.data.sessions[0]);
      }
    } catch (error) {
      console.error('Error loading sessions:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const loadSessionHistory = async (sessionId) => {
    try {
      const response = await axios.get(`${getBackendUrl()}/chat/sessions/${sessionId}/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setMessages(response.data.messages.map(msg => ({
        id: `${msg.timestamp}-${msg.role}`,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp
      })));
      setCurrentSessionId(sessionId);
    } catch (error) {
      console.error('Error loading session history:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${getBackendUrl()}/chat`, {
        message: userMessage.content,
        session_id: currentSessionId
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
      
      // Update current session ID if it's a new session
      if (response.data.session_id !== currentSessionId) {
        setCurrentSessionId(response.data.session_id);
        loadSessions(); // Refresh sessions list
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  const clearCurrentSession = async () => {
    if (!currentSessionId) return;
    
    try {
      await axios.delete(`${getBackendUrl()}/chat/sessions/${currentSessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setMessages([]);
      setCurrentSessionId(null);
      loadSessions();
    } catch (error) {
      console.error('Error clearing session:', error);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="header-left">
          <span className="user-name">{user}</span>
        </div>
        <div className="header-right">
          <button className="sign-out-button" onClick={onSignOut}>
            Sign Out
          </button>
        </div>
      </div>

      <div className="chat-main">
        <div className="sessions-sidebar">
          <h3>Past Sessions</h3>
          <div className="sessions-list">
            {isLoadingSessions ? (
              <div className="loading">Loading sessions...</div>
            ) : (
              sessions.map((sessionId, index) => (
                <div
                  key={sessionId}
                  className={`session-item ${sessionId === currentSessionId ? 'active' : ''}`}
                  onClick={() => loadSessionHistory(sessionId)}
                  title={sessionId}
                >
                  {sessionId}
                </div>
              ))
            )}
          </div>
          {currentSessionId && (
            <button className="clear-session-button" onClick={clearCurrentSession}>
              Clear Current Session
            </button>
          )}
          <button className="new-chat-button" onClick={startNewChat}>
            Start New Chat
          </button>
        </div>

        <div className="chat-panel">
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="empty-state">
                <p>Start a conversation with Jamie!</p>
                <p>I can help you find restaurants, recipes, and more.</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
                >
                  <div className="message-content">
                    {message.role === 'assistant' ? (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="message assistant-message">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-container">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type a message..."
              disabled={isLoading}
              className="message-input"
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !inputMessage.trim()}
              className="send-button"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Chat;
