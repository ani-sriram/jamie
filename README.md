# Jamie - LLM-Powered Food Recommendation Agent

Jamie is an LLM-powered conversational agent designed to help users make food choices by providing context-aware food recommendations across both restaurant and home-cooked recipe domains. Jamie leverages user modeling to personalize suggestions, adapting to individual dietary preferences, ingredient restrictions, and cuisine interests.

Key features include:
- **Personalized Meal Recommendations**: Jamie maintains per-user session data including dietary restrictions, allergies, and preferred cuisines, allowing for dynamic adaptation of responses.
- **Hybrid Suggestion Engine**: The agent can seamlessly suggest both local restaurant options (sourced via the Google Places API) and curated home-cooking recipes (indexed from a structured recipe database).
- **Conversational Context Management**: Jamie persists conversational state, enabling multi-turn dialog and user-specific context retention across sessions.
- **Tool Integration**: Via a tool-augmented LLM architecture, Jamie can query external APIs, filter results by time, difficulty, or ingredients, and synthesize actionable choices for the user.
- **User Isolation**: Each user operates within an isolated agent service instance for privacy and scalability.
- **Extensible Framework**: The agent’s design supports component-wise scalability and the integration of new data sources, recommendation strategies, or dialog tools as needed.

## Architecture

Jamie's architecture ensures user isolation and is deployed on Google Cloud Platform:

- **Frontend**: React app served from Cloud Run
- **Orchestrator**: Central FastAPI service handling authentication and routing
- **Agent Services**: Per-user Cloud Run services with complete isolation
- **External APIs**: Gemini (LLM) and Google Places (restaurant data)

## Quick Start

### Local Development

1. Install dependencies:
```bash
uv sync
cp env.example .env
# Edit .env with your API keys
```

1. Run backend:
```bash
uv run src/main.py
```

1. Run frontend:
```bash
cd frontend
npm install
npm start
```

### Production Deployment
```bash
# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-west1"
export BASE_BUCKET="your-storage-bucket"
export ORCHESTRATOR_SERVICE_ACCOUNT="your-service-account"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
export GEMINI_API_KEY="your-gemini-key"
export PLACES_API_KEY="your-places-key"

# Deploy all services to GCP (frontend, orchestrator, and agent)
./deployment/deploy.sh
```
More details can be found in `/deployment/README.md`.

## API Endpoints

- `POST /signin` - User authentication
- `POST /chat` - Send messages to Jamie
- `GET /chat/sessions` - List user sessions
- `GET /health` - Health check
- etc

## Development

- **Backend**: Python with FastAPI, LangGraph, and Google Cloud services
- **Frontend**: React with nginx on Cloud Run
- **Deployment**: Docker containers on Google Cloud Run
- **Storage**: Cloud Storage for user session data, Firestore for database (used in db search tools)

## AI usage in development

AI coding assistants helped in the development of this project.