#!/bin/bash

# Deployment script for Jamie
set -e

# Source environment variables from .env file
ENV_FILE="${ENV_FILE:-$(dirname "$0")/../.env}"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from: $ENV_FILE"
    set -a  # automatically export all variables
    source "$ENV_FILE"
    set +a
else
    echo "Warning: .env file not found at $ENV_FILE"
    echo "Using environment variables or defaults"
fi

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


echo ""
echo "Verifying prerequisites..."

if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI is not installed or not in PATH"
    exit 1
fi
echo "gcloud CLI found: $(gcloud --version | head -n 1)"

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH"
    exit 1
fi
echo "Docker found: $(docker --version)"

# Verify service account key file exists
SERVICE_ACCOUNT_KEY="${GOOGLE_APPLICATION_CREDENTIALS:-./service-account-key.json}"
if [ ! -f "$SERVICE_ACCOUNT_KEY" ]; then
    echo "ERROR: Service account key file not found at: $SERVICE_ACCOUNT_KEY"
    echo "Please ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly in .env file"
    echo "Expected location: $SERVICE_ACCOUNT_KEY"
    exit 1
fi
echo "Service account key file found: $SERVICE_ACCOUNT_KEY"

echo ""

# GCP Auth

SERVICE_ACCOUNT_EMAIL=$(grep -o '"client_email":\s*"[^"]*"' "$SERVICE_ACCOUNT_KEY" | cut -d'"' -f4)
if [ -z "$SERVICE_ACCOUNT_EMAIL" ]; then
    echo "ERROR: Could not extract service account email from key file"
    echo "Please verify the key file format at: $SERVICE_ACCOUNT_KEY"
    exit 1
fi
echo "Service account: $SERVICE_ACCOUNT_EMAIL"

echo "Activating service account..."
if ! gcloud auth activate-service-account "$SERVICE_ACCOUNT_EMAIL" \
    --key-file="$SERVICE_ACCOUNT_KEY" \
    --project="$PROJECT_ID" 2>&1; then
    echo "ERROR: Failed to activate service account"
    exit 1
fi
echo "Service account activated"

echo "Setting active GCP project to: $PROJECT_ID"
if ! gcloud config set project "$PROJECT_ID" 2>&1; then
    echo "ERROR: Failed to set GCP project"
    exit 1
fi
echo "GCP project set"

echo "Configure Docker authentication for GCR..."
if ! gcloud auth configure-docker gcr.io --quiet 2>&1; then
    echo "ERROR: Failed to configure Docker credential helper"
    exit 1
fi
echo "Docker configured for GCR auth"

echo "GCR access test"
if ! gcloud container images list --repository=gcr.io/${PROJECT_ID} --limit=1 &>/dev/null; then
    echo "WARNING: Could not verify GCR access. This might be expected if no images exist yet."
    echo "Continuing with deployment..."
else
    echo "GCR access verified"
fi

echo ""

echo "Building and pushing Docker images..."

# Build orchestrator image
echo "Building orchestrator image..."
if ! docker build --platform linux/amd64 -f deployment/orchestrator.Dockerfile -t ${ORCHESTRATOR_IMAGE} .; then
    echo "ERROR: Failed to build orchestrator image"
    exit 1
fi

echo "Pushing orchestrator image to GCR..."
if ! docker push ${ORCHESTRATOR_IMAGE}; then
    echo "ERROR: Failed to push orchestrator image to GCR"
    echo "Image: ${ORCHESTRATOR_IMAGE}"
    echo "Please verify the service account has 'Storage Admin' or 'Artifact Registry Writer' role"
    exit 1
fi
echo "Orchestrator image pushed successfully"
echo ""

# Build agent image
echo "Building agent image..."
if ! docker build --platform linux/amd64 -f deployment/agent.Dockerfile -t ${AGENT_IMAGE} .; then
    echo "ERROR: Failed to build agent image"
    exit 1
fi

echo "Pushing agent image to GCR..."
if ! docker push ${AGENT_IMAGE}; then
    echo "ERROR: Failed to push agent image to GCR"
    echo "Image: ${AGENT_IMAGE}"
    echo "Please verify the service account has 'Storage Admin' or 'Artifact Registry Writer' role"
    exit 1
fi
echo "Agent image pushed successfully"
echo ""

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
if ! docker build --platform linux/amd64 -f deployment/frontend.Dockerfile -t ${FRONTEND_IMAGE} .; then
    echo "ERROR: Failed to build frontend image"
    exit 1
fi

echo "Pushing frontend image to GCR..."
if ! docker push ${FRONTEND_IMAGE}; then
    echo "ERROR: Failed to push frontend image to GCR"
    echo "Image: ${FRONTEND_IMAGE}"
    echo "Please verify the service account has 'Storage Admin' or 'Artifact Registry Writer' role"
    exit 1
fi
echo "Frontend image pushed successfully"
echo ""

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

echo "Updating orchestrator CORS settings with frontend URL: ${FRONTEND_URL}"
gcloud run services update ${ORCHESTRATOR_SERVICE} \
  --region=${REGION} \
  --update-env-vars "FRONTEND_URL=${FRONTEND_URL}"

# Verify the update was applied
echo "Verifying FRONTEND_URL was set..."
VERIFY_URL=$(gcloud run services describe ${ORCHESTRATOR_SERVICE} --region=${REGION} --format="value(spec.template.spec.containers[0].env[FRONTEND_URL])" 2>/dev/null || echo "")
if [ -z "${VERIFY_URL}" ]; then
    echo "WARNING: FRONTEND_URL may not have been set correctly. Please verify manually."
else
    echo "FRONTEND_URL successfully set to: ${VERIFY_URL}"
fi

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
