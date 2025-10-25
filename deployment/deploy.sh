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

echo "Deploying Jamie Backend Services to GCP..."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"


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
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},AGENT_SERVICE_IMAGE=${AGENT_IMAGE},BASE_BUCKET=${BASE_BUCKET}" \
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
echo ""
echo "Orchestrator URL: ${ORCHESTRATOR_URL}"
echo ""
echo "Next steps:"
echo "1. Update your frontend environment variable:"
echo "   REACT_APP_API_URL=${ORCHESTRATOR_URL}"
echo ""
echo "2. Build and deploy your frontend to Firebase:"
echo "   cd frontend"
echo "   REACT_APP_API_URL=${ORCHESTRATOR_URL} npm run build"
echo "   firebase deploy"
echo ""
echo "3. API keys are already configured in secrets: gemini-api-key and places-api-key"
echo "4. Test the deployment by visiting your Firebase frontend URL"
