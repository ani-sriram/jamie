from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from .sessions import SessionManager
from ..agent.schemas import ConversationMessage
from ..config import Config

app = FastAPI(title="Jamie Food Agent", version="0.1.0")
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_sessions": session_manager.get_session_count()}

@app.post("/chat/{user_id}", response_model=ChatResponse)
async def chat(user_id: str, request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        response, session_id = session_manager.process_message(
            user_id, 
            request.message, 
            request.session_id
        )
        return ChatResponse(response=response, user_id=user_id, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/chat/{user_id}/sessions", response_model=SessionListResponse)
async def list_user_sessions(user_id: str):
    sessions = session_manager.get_user_sessions(user_id)
    return SessionListResponse(user_id=user_id, sessions=sessions)

@app.get("/chat/{user_id}/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(user_id: str, session_id: str):
    messages = session_manager.get_session_history(user_id, session_id)
    return SessionHistoryResponse(user_id=user_id, session_id=session_id, messages=messages)

@app.delete("/chat/{user_id}/sessions/{session_id}")
async def clear_session(user_id: str, session_id: str):
    session_manager.clear_session(user_id, session_id)
    return {"message": f"Session {session_id} cleared for user {user_id}"}

@app.delete("/chat/{user_id}/sessions")
async def clear_all_user_sessions(user_id: str):
    session_manager.clear_all_user_sessions(user_id)
    return {"message": f"All sessions cleared for user {user_id}"}

@app.get("/stats")
async def get_stats():
    return {
        "active_sessions": session_manager.get_session_count(),
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)