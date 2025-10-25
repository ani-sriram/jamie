from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
from agent.schemas import ConversationMessage
from agent_service.sessions import SessionManager
from config import Config
import os

app = FastAPI(title="Jamie Agent Service", version="0.1.0")

# Get user_id from environment (set by orchestrator)
USER_ID = os.getenv("USER_ID")
if not USER_ID:
    raise ValueError("USER_ID environment variable is required")

session_manager = SessionManager()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    user_id: str
    session_id: str

class SessionListResponse(BaseModel):
    user_id: str
    sessions: List[str]

class SessionHistoryResponse(BaseModel):
    user_id: str
    session_id: str
    messages: List[ConversationMessage]

def verify_service_auth(x_user_id: str = Header(None)) -> str:
    """Verify service-to-service authentication"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")
    
    if x_user_id != USER_ID:
        raise HTTPException(status_code=403, detail="User ID mismatch")
    
    return x_user_id

@app.get("/health")
async def health_check():
    return {"status": "healthy", "user_id": USER_ID}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(verify_service_auth)):
    """Process chat message for the assigned user"""
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        response, session_id = session_manager.process_message(
            USER_ID, 
            request.message, 
            request.session_id
        )
        return ChatResponse(response=response, user_id=USER_ID, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/chat/sessions", response_model=SessionListResponse)
async def list_user_sessions(user_id: str = Depends(verify_service_auth)):
    """List sessions for the assigned user"""
    sessions = session_manager.get_user_sessions(USER_ID)
    return SessionListResponse(user_id=USER_ID, sessions=sessions)

@app.get("/chat/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str, user_id: str = Depends(verify_service_auth)):
    """Get session history for the assigned user"""
    messages = session_manager.get_session_history(USER_ID, session_id)
    return SessionHistoryResponse(user_id=USER_ID, session_id=session_id, messages=messages)

@app.delete("/chat/sessions/{session_id}")
async def clear_session(session_id: str, user_id: str = Depends(verify_service_auth)):
    """Clear specific session for the assigned user"""
    session_manager.clear_session(USER_ID, session_id)
    return {"message": f"Session {session_id} cleared for user {USER_ID}"}

@app.delete("/chat/sessions")
async def clear_all_user_sessions(user_id: str = Depends(verify_service_auth)):
    """Clear all sessions for the assigned user"""
    session_manager.clear_all_user_sessions(USER_ID)
    return {"message": f"All sessions cleared for user {USER_ID}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
