#!/bin/bash

# Deploy Stats Checker Cloud Function
# Usage: ./deploy.sh

set -e  # Exit on error

# Base configuration
PROJECT_ID="conpass-agent"
FUNCTION_NAME="conpass-stats-checker"
REGION="asia-northeast1"
RUNTIME="python311"
SERVICE_ACCOUNT="embeddings-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Secret Manager secret names (these should already exist in your project)
# Expected Secret Manager IDs:
#   - redis-url-dev / -staging / -prod
#   - qdrant-api-key-dev / -staging / -prod
DEV_REDIS_SECRET="redis-url-dev"
STAGING_REDIS_SECRET="redis-url-staging"
PROD_REDIS_SECRET="redis-url-prod"

DEV_QDRANT_SECRET="qdrant-api-key-dev"
STAGING_QDRANT_SECRET="qdrant-api-key-staging"
PROD_QDRANT_SECRET="qdrant-api-key-prod"

# Environment-specific configurations (non-secret values)
# DEV Environment
DEV_QDRANT_URL="https://24f4bcad-b4c2-4989-8ace-0016603c7435.us-east4-0.gcp.cloud.qdrant.io:6333"

# STAGING Environment
STAGING_QDRANT_URL="https://f5a5e32b-6fe7-4c21-886e-27e612ee2222.ap-northeast-1-0.aws.cloud.qdrant.io"

# PROD Environment
PROD_QDRANT_URL="https://6bb243c9-13ea-4424-a8ba-aa597a335481.ap-northeast-1-0.aws.cloud.qdrant.io"

# Note: Collection name is hard-coded as "contracts" in main.py

# Build env vars string for gcloud
ENV_VARS="DEV_QDRANT_URL=${DEV_QDRANT_URL},STAGING_QDRANT_URL=${STAGING_QDRANT_URL},PROD_QDRANT_URL=${PROD_QDRANT_URL}"

echo "======================================"
echo "Deploying Stats Checker Cloud Function"
echo "======================================"
echo ""
echo "Configuration:"
echo "  Project ID:       $PROJECT_ID"
echo "  Function Name:    $FUNCTION_NAME"
echo "  Region:           $REGION"
echo "  Runtime:          $RUNTIME"
echo "  Service Account:  $SERVICE_ACCOUNT"
echo ""

# Show configuration summary
echo "================================================"
echo "Environment Configuration"
echo "================================================"
echo ""
echo "DEV Environment:"
echo "  QDRANT_URL:        $DEV_QDRANT_URL"
echo "  QDRANT_COLLECTION: contracts (hard-coded)"
echo "  REDIS_URL:         (from Secret Manager: $DEV_REDIS_SECRET)"
echo "  QDRANT_API_KEY:    (from Secret Manager: $DEV_QDRANT_SECRET)"
echo ""
echo "STAGING Environment:"
echo "  QDRANT_URL:        $STAGING_QDRANT_URL"
echo "  QDRANT_COLLECTION: contracts (hard-coded)"
echo "  REDIS_URL:         (from Secret Manager: $STAGING_REDIS_SECRET)"
echo "  QDRANT_API_KEY:    (from Secret Manager: $STAGING_QDRANT_SECRET)"
echo ""
echo "PROD Environment:"
echo "  QDRANT_URL:        $PROD_QDRANT_URL"
echo "  QDRANT_COLLECTION: contracts (hard-coded)"
echo "  REDIS_URL:         (from Secret Manager: $PROD_REDIS_SECRET)"
echo "  QDRANT_API_KEY:    (from Secret Manager: $PROD_QDRANT_SECRET)"
echo ""
echo "================================================"
echo ""
echo "⚠️  Make sure the following secrets exist in Secret Manager:"
echo "  - $DEV_REDIS_SECRET"
echo "  - $DEV_QDRANT_SECRET"
echo "  - $STAGING_REDIS_SECRET"
echo "  - $STAGING_QDRANT_SECRET"
echo "  - $PROD_REDIS_SECRET"
echo "  - $PROD_QDRANT_SECRET"
echo ""
read -p "Press enter to continue with deployment..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
gcloud config set project $PROJECT_ID

echo ""
echo "🚀 Deploying Cloud Function..."
echo ""

# Deploy the function with all environment variables and secrets
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime $RUNTIME \
  --region $REGION \
  --source . \
  --entry-point stats_http \
  --trigger-http \
  --allow-unauthenticated \
  --memory 512MB \
  --timeout 60s \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars "$ENV_VARS" \
  --set-secrets "DEV_REDIS_URL=${DEV_REDIS_SECRET}:latest,DEV_QDRANT_API_KEY=${DEV_QDRANT_SECRET}:latest,STAGING_REDIS_URL=${STAGING_REDIS_SECRET}:latest,STAGING_QDRANT_API_KEY=${STAGING_QDRANT_SECRET}:latest,PROD_REDIS_URL=${PROD_REDIS_SECRET}:latest,PROD_QDRANT_API_KEY=${PROD_QDRANT_SECRET}:latest" \
  --project $PROJECT_ID

echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""

# Get function URL
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --gen2 \
  --region $REGION \
  --format="value(serviceConfig.uri)" \
  --project $PROJECT_ID)

echo "Function URL: $FUNCTION_URL"
echo ""
echo "Test the function:"
echo "  curl $FUNCTION_URL"
echo ""
echo "Or with pretty JSON output:"
echo "  curl $FUNCTION_URL | jq"
echo ""
echo "================================================"
echo ""
