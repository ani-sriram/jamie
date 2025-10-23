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
        print(f"[DEBUG] Processing message for user {user_id}: {request.message}")
        response = session_manager.process_message(user_id, request.message)
        print(f"[DEBUG] Got response: {response}")
        return ChatResponse(response=response, user_id=user_id)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Failed to process message:\n{error_trace}")
        raise HTTPException(status_code=500, detail={
            "error": str(e),
            "traceback": error_trace,
            "user_id": user_id,
            "message": request.message
        })

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