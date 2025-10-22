import pytest
from src.web.sessions import SessionManager

class TestSessionManager:
    def test_get_or_create_session(self):
        manager = SessionManager()
        agent = manager.get_or_create_session("test_user")
        assert agent is not None
        assert manager.get_session_count() == 1
    
    def test_clear_session(self):
        manager = SessionManager()
        manager.get_or_create_session("test_user")
        assert manager.get_session_count() == 1
        manager.clear_session("test_user")
        assert manager.get_session_count() == 0

if __name__ == "__main__":
    pytest.main([__file__])
