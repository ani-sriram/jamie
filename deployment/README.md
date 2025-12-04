# Deployment details

This document describes the deployment architecture and process for Jamie.

Jamie is deployed on GCP and maintains user isolation.

## Architecture Overview

The application is split into three components:

1. **Frontend**: Static React app served from Cloud Run (nginx)
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
- Google Cloud Platform (GCP)
- Docker
- Node.js and npm for frontend build
- gcloud CLI

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

The deployment script handles building and deploying all components (frontend, orchestrator, and agent services) to GCP Cloud Run.

To run the deployment script, at the root level:
```bash
./deployment/deploy.sh
```

The script will:
1. Build and push Docker images for orchestrator and agent services
2. Deploy the orchestrator service to Cloud Run
3. Configure service account permissions and secrets access
4. Build the frontend React app with the orchestrator URL
5. Build and push the frontend Docker image
6. Deploy the frontend service to Cloud Run

Upon successful deployment, you will receive URLs for both the orchestrator and frontend services. The frontend is automatically configured to connect to the orchestrator.


## Service Configuration

All services are deployed on Cloud Run, which automatically scales instances with use. Containers are lightweight since model serving is done via API.

### Frontend Service
- **Service Name**: `jamie-frontend`
- **Notes**: single instance, publicly accessible, only communicates with orchestrator

### Orchestrator Service
- **Service Name**: `jamie-orchestrator`
- **Notes**: single instance, publicly accessible, requires JWT authentication

### Agent Service
- **Service Name**: `jamie-agent-{USERNAME}`
- **Notes**: multiple instances dynamicaly provisioned per user, only accessible via orchestrator, refer to `agent-service-template.yaml` for container details