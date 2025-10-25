from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
import base64
import json
import httpx
import os
from google.cloud import run_v2
from google.cloud.run_v2 import Service, Container, EnvVar, ResourceRequirements
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Jamie Orchestrator", version="0.1.0")
security = HTTPBearer()

# In-memory storage for user -> agent service mapping
# In production, this should be stored in a database
user_agent_services: Dict[str, str] = {}

class SignInRequest(BaseModel):
    username: str

class SignInResponse(BaseModel):
    token: str
    user_id: str

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
    messages: List[dict]

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract user from JWT token"""
    try:
        token_data = base64.b64decode(credentials.credentials).decode('utf-8')
        user_data = json.loads(token_data)
        return user_data['username']
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_user_agent_service(user_id: str) -> str:
    """Create a Cloud Run service for a specific user"""
    try:
        client = run_v2.ServicesClient()
        
        project_id = os.getenv("GCP_PROJECT_ID")
        region = os.getenv("GCP_REGION", "us-central1")
        agent_image = os.getenv("AGENT_SERVICE_IMAGE")
        
        service_name = f"jamie-agent-{user_id.lower().replace('_', '-')}"
        
        # Check if service already exists
        try:
            existing_service = client.get_service(
                name=f"projects/{project_id}/locations/{region}/services/{service_name}"
            )
            logger.info(f"Service {service_name} already exists")
            return existing_service.uri
        except Exception:
            # Service doesn't exist, create it
            pass
        
        # Create new service
        service = Service(
            template=run_v2.RevisionTemplate(
                containers=[
                    Container(
                        image=agent_image,
                        env=[
                            EnvVar(name="USER_ID", value=user_id),
                            EnvVar(name="GEMINI_API_KEY", value=os.getenv("GEMINI_API_KEY")),
                            EnvVar(name="PLACES_API_KEY", value=os.getenv("PLACES_API_KEY")),
                            EnvVar(name="BASE_BUCKET", value=os.getenv("BASE_BUCKET")),
                        ],
                        resources=ResourceRequirements(
                            limits={"memory": "512Mi", "cpu": "1"}
                        ),
                    )
                ],
                container_concurrency=1,  # Full isolation
                timeout="300s",
                service_account=os.getenv("AGENT_SERVICE_ACCOUNT"),
            ),
            traffic=[
                run_v2.TrafficTarget(
                    type_=run_v2.TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST,
                    percent=100,
                )
            ],
        )
        
        parent = f"projects/{project_id}/locations/{region}"
        
        operation = client.create_service(
            parent=parent,
            service=service,
            service_id=service_name,
        )
        
        # Wait for operation to complete
        result = operation.result()
        logger.info(f"Created service {service_name} with URI: {result.uri}")
        
        return result.uri
        
    except Exception as e:
        logger.error(f"Error creating agent service for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent service: {str(e)}")

def get_or_create_agent_url(user_id: str) -> str:
    """Get existing agent URL or create new one"""
    if user_id in user_agent_services:
        return user_agent_services[user_id]
    
    agent_url = create_user_agent_service(user_id)
    user_agent_services[user_id] = agent_url
    return agent_url

async def proxy_to_agent(user_id: str, endpoint: str, method: str, data: Optional[dict] = None) -> dict:
    """Proxy request to user's agent service"""
    try:
        agent_url = get_or_create_agent_url(user_id)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{agent_url}{endpoint}"
            headers = {"X-User-ID": user_id}  # Service-to-service auth
            
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=data, headers=headers)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise HTTPException(status_code=400, detail="Unsupported method")
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPError as e:
        logger.error(f"Error proxying to agent service: {e}")
        raise HTTPException(status_code=502, detail=f"Agent service error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error proxying to agent: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "active_users": len(user_agent_services)}

@app.post("/signin", response_model=SignInResponse)
async def signin(request: SignInRequest):
    """Sign in user and provision their agent service"""
    if not request.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    
    user_id = request.username.strip()
    
    # Generate JWT token
    token_data = {
        "username": user_id,
        "timestamp": str(int(__import__("time").time()))
    }
    token = base64.b64encode(json.dumps(token_data).encode()).decode()
    
    # Provision agent service
    try:
        agent_url = get_or_create_agent_url(user_id)
        logger.info(f"User {user_id} signed in, agent service: {agent_url}")
    except Exception as e:
        logger.error(f"Failed to provision agent service for {user_id}: {e}")
        # Don't fail sign-in if agent provisioning fails
        pass
    
    return SignInResponse(token=token, user_id=user_id)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """Proxy chat request to user's agent service"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    return await proxy_to_agent(user_id, "/chat", "POST", request.dict())

@app.get("/chat/sessions", response_model=SessionListResponse)
async def list_user_sessions(user_id: str = Depends(get_current_user)):
    """Proxy session list request to user's agent service"""
    return await proxy_to_agent(user_id, "/chat/sessions", "GET")

@app.get("/chat/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str, user_id: str = Depends(get_current_user)):
    """Proxy session history request to user's agent service"""
    return await proxy_to_agent(user_id, f"/chat/sessions/{session_id}/history", "GET")

@app.delete("/chat/sessions/{session_id}")
async def clear_session(session_id: str, user_id: str = Depends(get_current_user)):
    """Proxy session clear request to user's agent service"""
    return await proxy_to_agent(user_id, f"/chat/sessions/{session_id}", "DELETE")

@app.delete("/chat/sessions")
async def clear_all_user_sessions(user_id: str = Depends(get_current_user)):
    """Proxy clear all sessions request to user's agent service"""
    return await proxy_to_agent(user_id, "/chat/sessions", "DELETE")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
