# Jamie - LLM-Powered Food Recommendation Agent

Jamie is a conversational assistant that helps users decide what to eat by suggesting restaurant meals, delivery options, or home-cooked recipes.

## Architecture

Jamie's architecture ensures user isolation and is deployed on Google Cloud Platform:

- **Frontend**: React app served from Firebase Hosting
- **Orchestrator**: Central FastAPI service handling authentication and routing
- **Agent Services**: Per-user Cloud Run services with complete isolation
- **External APIs**: Gemini (LLM) and Google Places (restaurant data)

## Quick Start

### Local Development
As described in the main repo:
1. Install dependencies:
```bash
uv sync
cp env.example .env
# Edit .env with your API keys
```

2. Run backend:
```bash
uv run src/main.py
```

3. Run frontend:
```bash
cd frontend
npm install
npm start
```

### Production Deployment
```bash
# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export GEMINI_API_KEY="your-gemini-key"
export PLACES_API_KEY="your-places-key"

# Deploy to GCP
./deployment/deploy.sh

# Deploy frontend to Firebase
cd frontend
npm run build
firebase deploy
```
More details can be found in `/deployment/README.md`.

## API Endpoints

- `POST /signin` - User authentication
- `POST /chat` - Send messages to Jamie
- `GET /chat/sessions` - List user sessions
- `GET /health` - Health check

## Development

- **Backend**: Python with FastAPI, LangGraph, and Google Cloud services
- **Frontend**: React with Firebase Hosting
- **Deployment**: Docker containers on Google Cloud Run
- **Storage**: Cloud Storage for user session data

## AI usage in development

AI coding assistants helped in the development of this project. They were particularly useful in understanding the orchestration and deployment process on GCP.