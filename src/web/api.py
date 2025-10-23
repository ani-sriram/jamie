from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from .sessions import SessionManager
from ..config import Config
from ..agent.clients import GeminiClient
import json

app = FastAPI(title="Jamie Food Agent", version="0.1.0")
session_manager = SessionManager()
gemini_client = GeminiClient()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    user_id: str


class EvalRequest(BaseModel):
    user_input: str
    llm_response: str


class EvalResponse(BaseModel):
    score: int
    reason: str

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


@app.post("/evals", response_model=EvalResponse)
async def evaluate_response(req: EvalRequest):
    system_prompt = (
        "You are an impartial evaluator for a food assistant's response. "
        "Given the user's input and the assistant's response, score the response from 1 to 5 "
        "where 1=unhelpful/incorrect/unsafe and 5=excellent in helpfulness, correctness, relevance, and safety. "
        "Return ONLY a compact JSON object with keys 'score' (integer 1-5) and 'reason' (short string)."
    )
    prompt = (
        f"User input:\n{req.user_input}\n\n"
        f"Assistant response:\n{req.llm_response}\n\n"
        "Provide the evaluation now."
    )

    raw = gemini_client.generate_response(prompt, system_prompt)
    try:
        data = json.loads(raw)
        score = int(data.get("score"))
        reason = str(data.get("reason", ""))
    except Exception:
        # Fallback: attempt to extract a number 1-5; default to 3
        import re
        m = re.search(r"[1-5]", raw)
        score = int(m.group()) if m else 3
        reason = raw.strip()[:500]

    # Clamp score to 1..5
    score = max(1, min(5, score))
    return EvalResponse(score=score, reason=reason)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)