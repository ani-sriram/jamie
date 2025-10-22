from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from .sessions import SessionManager
from ..config import Config

app = FastAPI(title="Jamie Food Agent", version="0.1.0")
session_manager = SessionManager()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    user_id: str

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_sessions": session_manager.get_session_count()}

@app.post("/chat/{user_id}", response_model=ChatResponse)
async def chat(user_id: str, request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        response = session_manager.process_message(user_id, request.message)
        return ChatResponse(response=response, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/chat/{user_id}")
async def clear_session(user_id: str):
    session_manager.clear_session(user_id)
    return {"message": f"Session cleared for user {user_id}"}

@app.get("/stats")
async def get_stats():
    return {
        "active_sessions": session_manager.get_session_count(),
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)