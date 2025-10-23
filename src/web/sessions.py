from typing import Dict, List
from ..agent.graph import JamieAgent
from ..agent.schemas import ConversationMessage, MessageRole
from .storage import GCPSessionStorage
import logging
import os
import uuid
from datetime import datetime

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, JamieAgent] = {}  # Key: f"{user_id}:{session_id}"
        self.user_sessions: Dict[str, List[str]] = {}  # Key: user_id, Value: List[session_id]
        self.storage = GCPSessionStorage()
        self._setup_logging()
    
    def _setup_logging(self):
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.logs_dir = logs_dir
    
    def get_or_create_session(self, user_id: str, session_id: str = None) -> tuple[JamieAgent, str]:
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session_key = f"{user_id}:{session_id}"
        
        if session_key not in self.sessions:
            self.sessions[session_key] = JamieAgent()
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            if session_id not in self.user_sessions[user_id]:
                self.user_sessions[user_id].append(session_id)
            self._log_user_event(user_id, session_id, f"New session created: {session_id}")
        
        return self.sessions[session_key], session_id
    
    def process_message(self, user_id: str, message: str, session_id: str = None) -> tuple[str, str]:
        agent, session_id = self.get_or_create_session(user_id, session_id)
        self._log_user_event(user_id, session_id, f"Processing message: {message}")
        
        # Retrieve conversation history for this session
        conversation_history = self.storage.get_session_messages(user_id, session_id)
        self._log_user_event(user_id, session_id, f"Retrieved {len(conversation_history)} messages from history")
        
        # Save user message to GCS
        user_message = ConversationMessage(
            session_id=session_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=message,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        self.storage.save_message(user_message)
        
        try:
            # Pass conversation history to agent
            response = agent.process_message(user_id, message, session_id, conversation_history)
            
            # Save assistant response to GCS
            assistant_message = ConversationMessage(
                session_id=session_id,
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=response,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            self.storage.save_message(assistant_message)
            
            self._log_user_event(user_id, session_id, f"Response: {response}")
            return response, session_id
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self._log_user_event(user_id, session_id, error_msg)
            return "I'm sorry, I encountered an error processing your request. Please try again.", session_id
    
    def _log_user_event(self, user_id: str, session_id: str, event: str):
        log_file = os.path.join(self.logs_dir, f"{user_id}_{session_id}.log")
        with open(log_file, "a") as f:
            f.write(f"{event}\n")
    
    def get_session_count(self) -> int:
        return len(self.sessions)
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        # First try to get from GCS storage
        gcs_sessions = self.storage.list_user_sessions(user_id)
        if gcs_sessions:
            return gcs_sessions
        
        # Fallback to in-memory sessions
        return self.user_sessions.get(user_id, [])
    
    def get_session_history(self, user_id: str, session_id: str) -> List[ConversationMessage]:
        """Get conversation history for a specific session"""
        return self.storage.get_session_messages(user_id, session_id)
    
    def clear_session(self, user_id: str, session_id: str):
        session_key = f"{user_id}:{session_id}"
        
        # Remove from in-memory storage
        if session_key in self.sessions:
            del self.sessions[session_key]
            if user_id in self.user_sessions:
                self.user_sessions[user_id].remove(session_id)
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]
        
        # Remove from GCS storage
        self.storage.delete_session(user_id, session_id)
        self._log_user_event(user_id, session_id, f"Session cleared: {session_id}")
    
    def clear_all_user_sessions(self, user_id: str):
        # Clear from in-memory storage
        if user_id in self.user_sessions:
            session_ids = self.user_sessions[user_id].copy()
            for session_id in session_ids:
                session_key = f"{user_id}:{session_id}"
                if session_key in self.sessions:
                    del self.sessions[session_key]
            del self.user_sessions[user_id]
        
        # Clear from GCS storage
        self.storage.delete_all_user_sessions(user_id)