from typing import Dict
from ..agent.graph import JamieAgent
from ..agent.schemas import UserMessage
import logging
import os

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, JamieAgent] = {}
        self._setup_logging()
    
    def _setup_logging(self):
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.logs_dir = logs_dir
    
    def get_or_create_session(self, user_id: str) -> JamieAgent:
        if user_id not in self.sessions:
            self.sessions[user_id] = JamieAgent()
            self._log_user_event(user_id, f"New session created for user {user_id}")
        return self.sessions[user_id]
    
    def process_message(self, user_id: str, message: str) -> str:
        agent = self.get_or_create_session(user_id)
        self._log_user_event(user_id, f"Processing message: {message}")
        
        try:
            response = agent.process_message(user_id, message)
            self._log_user_event(user_id, f"Response: {response}")
            return response
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self._log_user_event(user_id, error_msg)
            return "I'm sorry, I encountered an error processing your request. Please try again."
    
    def _log_user_event(self, user_id: str, event: str):
        log_file = os.path.join(self.logs_dir, f"{user_id}.log")
        with open(log_file, "a") as f:
            f.write(f"{event}\n")
    
    def get_session_count(self) -> int:
        return len(self.sessions)
    
    def clear_session(self, user_id: str):
        if user_id in self.sessions:
            del self.sessions[user_id]
            self._log_user_event(user_id, f"Session cleared for user {user_id}")