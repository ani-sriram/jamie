#!/bin/bash

# Deployment script for Jamie
set -e

# Configuration using env variables
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
REGION=${GCP_REGION:-"us-west1"}
ORCHESTRATOR_SERVICE="jamie-orchestrator"
ORCHESTRATOR_SERVICE_ACCOUNT=${ORCHESTRATOR_SERVICE_ACCOUNT:-"jamie-orchestrator@${PROJECT_ID}.iam.gserviceaccount.com"}
AGENT_IMAGE="gcr.io/${PROJECT_ID}/jamie-agent"
ORCHESTRATOR_IMAGE="gcr.io/${PROJECT_ID}/jamie-orchestrator"
BASE_BUCKET=${BASE_BUCKET:-"jamie-storage-bucket"}

MIGRATE_RECIPES=${MIGRATE_RECIPES:-"false"}

echo "Deploying Jamie Backend Services to GCP..."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"

if [ "$MIGRATE_RECIPES" = "true" ]; then
    echo "Migrating recipes to Firestore..."
    if command -v uv &> /dev/null; then
        uv run python src/scripts/migrate_db.py
    else
        PYTHONPATH=src python src/scripts/migrate_db.py
    fi
    if [ $? -ne 0 ]; then
        echo "Error: Recipe migration failed"
        exit 1
    fi
    echo "Recipes migrated successfully to Firestore"
fi

echo "Building and pushing Docker images..."

# Build orchestrator image
echo "Building orchestrator image..."
docker build --platform linux/amd64 -f deployment/orchestrator.Dockerfile -t ${ORCHESTRATOR_IMAGE} .
docker push ${ORCHESTRATOR_IMAGE}

# Build agent image
echo "Building agent image..."
docker build --platform linux/amd64 -f deployment/agent.Dockerfile -t ${AGENT_IMAGE} .
docker push ${AGENT_IMAGE}

# Deploy orchestrator service
echo "Deploying orchestrator service..."
gcloud run deploy ${ORCHESTRATOR_SERVICE} \
  --image ${ORCHESTRATOR_IMAGE} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 20 \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},AGENT_SERVICE_IMAGE=${AGENT_IMAGE},BASE_BUCKET=${BASE_BUCKET},ORCHESTRATOR_SERVICE_ACCOUNT=${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --service-account ${ORCHESTRATOR_SERVICE_ACCOUNT}

# Verifying permissions for orchestrator
echo "Verifying service account permissions..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --role="roles/run.admin" \
  || echo "Run admin role already granted"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountUser" \
  || echo "Service account user role already granted"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --role="roles/run.admin" \
  || echo "Run admin role already granted (for IAM policy management)"

# Verifying permissions for secrets
echo "Verifying secret access..."
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor" \
  || echo "Gemini secret access already granted"

gcloud secrets add-iam-policy-binding places-api-key \
  --member="serviceAccount:${ORCHESTRATOR_SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor" \
  || echo "Places secret access already granted"

# Get orchestrator URL
ORCHESTRATOR_URL=$(gcloud run services describe ${ORCHESTRATOR_SERVICE} --region=${REGION} --format="value(status.url)")

echo ""
echo "Backend deployment complete!"
echo "Orchestrator URL: ${ORCHESTRATOR_URL}"
echo ""

# Build and deploy frontend
FRONTEND_SERVICE="jamie-frontend"
FRONTEND_IMAGE="gcr.io/${PROJECT_ID}/jamie-frontend"

echo "Building frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Building frontend with REACT_APP_API_URL=${ORCHESTRATOR_URL}..."
REACT_APP_API_URL=${ORCHESTRATOR_URL} npm run build

if [ ! -d "build" ]; then
    echo "Error: Frontend build failed. build directory not found."
    exit 1
fi

cd ..

echo "Building frontend Docker image..."
docker build --platform linux/amd64 -f deployment/frontend.Dockerfile -t ${FRONTEND_IMAGE} .
docker push ${FRONTEND_IMAGE}

echo "Deploying frontend service..."
gcloud run deploy ${FRONTEND_SERVICE} \
  --image ${FRONTEND_IMAGE} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --port 80

FRONTEND_URL=$(gcloud run services describe ${FRONTEND_SERVICE} --region=${REGION} --format="value(status.url)")

echo "Updating orchestrator CORS settings with frontend URL..."
gcloud run services update ${ORCHESTRATOR_SERVICE} \
  --region=${REGION} \
  --update-env-vars "FRONTEND_URL=${FRONTEND_URL}" \
  --quiet

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Backend Services:"
echo "  Orchestrator URL: ${ORCHESTRATOR_URL}"
echo ""
echo "Frontend:"
echo "  Frontend URL: ${FRONTEND_URL}"
echo ""
echo "API Configuration:"
echo "  API keys are configured in secrets: gemini-api-key and places-api-key"
echo ""
echo "Next steps:"
echo "  1. Visit your frontend at: ${FRONTEND_URL}"
echo "  2. Test the deployment by signing in and using the chat interface"
echo ""
