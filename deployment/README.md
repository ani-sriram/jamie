# Deployment details

This document describes the deployment architecture and process for Jamie.

Jamie is deployed on GCP and maintains user isolation.

## Architecture Overview

The application is split into three components:

1. **Frontend**: Static React app served from Firebase
2. **Orchestrator Service**: Central FastAPI service handling authentication and routing
3. **Agent Service**: Per-user Cloud Run services for isolated agent execution

## Components

### Orchestrator Service (`src/orchestrator/`)
- Handles user authentication (sign-in endpoint)
- Provisions Cloud Run services for each user (user isolation)
- Proxies all chat requests to user-specific agent services

### Agent Service (`src/agent_service/`)
- Simplified FastAPI app without authentication
- **(WIP)**Accepts requests only from orchestrator via service-to-service auth
- Hosts agent using Gemini API with defined set of tools

### Frontend (`frontend/`)
- Static React application
- Communicates with orchestrator service
- Simple chat interface

## Deployment Steps

### Key Required Tools
- Google Cloud
- Firebase
- Docker
- Node.js and npm for frontend build

### 1. Configure Environment Variables

Set the following environment variables:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-west1"
export BASE_BUCKET="your-storage-bucket"
export ORCHESTRATOR_SERVICE_ACCOUNT="account-address-with-permissions"
export GEMINI_API_KEY="your-gemini-api-key"
export PLACES_API_KEY="your-places-api-key"
```

Note that the orchestrator will need a service account with permission to run operations as a service account on GCP. It will also need permission to manage Cloud Run (provision containers), access to read repository items (to pull docker image for agent), and permission to view storage objects (for attaching session storage to agents).

The API keys actually need not be set here. They should be set as secrets using the Secret Manager tool on GCP.

### 2. Deploy

There is a script to handle deploying the backend. The script will build and push docker images for the orchestrator and agent services, then deploy on GCP.

To run the script, at the root level:
```bash
./deployment/deploy.sh
```

Upon running the script and seeing a successful deployment, we will recieve a url for the orchestrator. This will need to be added to `frontend/.env.production` to deploy the frontend. Set the env variable `$REACT_APP_API_URL` to the orchestrator url.

Now run the following:
```bash
cd frontend
npm run build
firebase deploy
```


## Service Configuration

Refer to `agent-service-template.yaml` for details. The services are deployed on Cloud Run, which automatically scales instances with use. Containers are rather lightweight since model serving is done via API.