from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import base64
import json
from .sessions import SessionManager
from agent.schemas import ConversationMessage
from config import Config

app = FastAPI(title="Jamie Food Agent", version="0.1.0")
session_manager = SessionManager()
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract user from JWT token"""
    try:
        # Decode the JWT token (simple base64 for testing)
        token_data = base64.b64decode(credentials.credentials).decode("utf-8")
        user_data = json.loads(token_data)
        return user_data["username"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        response, session_id = session_manager.process_message(
            user_id, request.message, request.session_id
        )
        return ChatResponse(response=response, user_id=user_id, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/chat/sessions", response_model=SessionListResponse)
async def list_user_sessions(user_id: str = Depends(get_current_user)):
    sessions = session_manager.get_user_sessions(user_id)
    return SessionListResponse(user_id=user_id, sessions=sessions)


@app.get("/chat/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str, user_id: str = Depends(get_current_user)
):
    messages = session_manager.get_session_history(user_id, session_id)
    return SessionHistoryResponse(
        user_id=user_id, session_id=session_id, messages=messages
    )


@app.delete("/chat/sessions/{session_id}")
async def clear_session(session_id: str, user_id: str = Depends(get_current_user)):
    session_manager.clear_session(user_id, session_id)
    return {"message": f"Session {session_id} cleared for user {user_id}"}


@app.delete("/chat/sessions")
async def clear_all_user_sessions(user_id: str = Depends(get_current_user)):
    session_manager.clear_all_user_sessions(user_id)
    return {"message": f"All sessions cleared for user {user_id}"}


@app.get("/stats")
async def get_stats():
    return {
        "active_sessions": session_manager.get_session_count(),
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
