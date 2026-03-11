#!/bin/bash

# Deploy Generate Embeddings Pipeline to Cloud Run
# Usage: ./deploy.sh [dev|staging|prod]

set -e

# Validate environment argument
ENVIRONMENT=${1:-}
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Error: Invalid environment. Must be one of: dev, staging, prod"
    echo "Usage: ./deploy.sh [dev|staging|prod]"
    exit 1
fi

# Base configuration
PROJECT_ID="conpass-agent"
REGION="asia-northeast1"
BASE_SERVICE_NAME="generate-embeddings"
SERVICE_NAME="${BASE_SERVICE_NAME}-${ENVIRONMENT}"
IMAGE_NAME="gcr.io/$PROJECT_ID/${BASE_SERVICE_NAME}-${ENVIRONMENT}"
SERVICE_ACCOUNT="embeddings-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Secret Manager secret names (one per environment)
# Expected Secret Manager IDs:
#   - openai-api-key-dev / -staging / -prod
#   - redis-url-dev / -staging / -prod
#   - qdrant-api-key-dev / -staging / -prod
OPENAI_SECRET_NAME="openai-api-key-${ENVIRONMENT}"
REDIS_SECRET_NAME="redis-url-${ENVIRONMENT}"
QDRANT_SECRET_NAME="qdrant-api-key-${ENVIRONMENT}"

# Environment-specific configurations (including non-secret env vars)
case $ENVIRONMENT in
    dev)
        MEMORY="2Gi"
        CPU="1"
        MAX_INSTANCES="5"
        MIN_INSTANCES="0"
        CONCURRENCY="20"

        # Hard-coded env vars for dev
        CHUNK_SIZE="1000"
        CHUNK_OVERLAP="100"
        EMBEDDING_MODEL="text-embedding-3-large"
        EMBEDDING_DIM="1024"
        QDRANT_URL="https://24f4bcad-b4c2-4989-8ace-0016603c7435.us-east4-0.gcp.cloud.qdrant.io:6333"
        QDRANT_COLLECTION="contracts"
        ;;
    staging)
        MEMORY="2Gi"
        CPU="1"
        MAX_INSTANCES="5"
        MIN_INSTANCES="0"
        CONCURRENCY="20"

        # Hard-coded env vars for staging
        CHUNK_SIZE="1000"
        CHUNK_OVERLAP="100"
        EMBEDDING_MODEL="text-embedding-3-large"
        EMBEDDING_DIM="1024"
        QDRANT_URL="https://f5a5e32b-6fe7-4c21-886e-27e612ee2222.ap-northeast-1-0.aws.cloud.qdrant.io"
        QDRANT_COLLECTION="contracts"
        ;;
    prod)
        MEMORY="4Gi"
        CPU="2"
        MAX_INSTANCES="5"
        MIN_INSTANCES="0"
        CONCURRENCY="20"

        # Hard-coded env vars for prod
        CHUNK_SIZE="1000"
        CHUNK_OVERLAP="100"
        EMBEDDING_MODEL="text-embedding-3-large"
        EMBEDDING_DIM="1024"
        QDRANT_URL="https://6bb243c9-13ea-4424-a8ba-aa597a335481.ap-northeast-1-0.aws.cloud.qdrant.io"
        QDRANT_COLLECTION="contracts"
        ;;
esac

# Build env vars string for gcloud
ENV_VARS="ENVIRONMENT=${ENVIRONMENT},CHUNK_SIZE=${CHUNK_SIZE},CHUNK_OVERLAP=${CHUNK_OVERLAP},EMBEDDING_MODEL=${EMBEDDING_MODEL},EMBEDDING_DIM=${EMBEDDING_DIM},QDRANT_URL=${QDRANT_URL},QDRANT_COLLECTION=${QDRANT_COLLECTION}"

echo "================================================"
echo "Deploying Generate Embeddings to Cloud Run"
echo "Environment: $ENVIRONMENT"
echo "================================================"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo "Service Account: $SERVICE_ACCOUNT"
echo "Memory: $MEMORY"
echo "CPU: $CPU"
echo "Min Instances: $MIN_INSTANCES"
echo "Max Instances: $MAX_INSTANCES"
echo "================================================"

# Show configuration summary
echo ""
echo "Using the following non-secret env vars:"
echo "  CHUNK_SIZE=$CHUNK_SIZE"
echo "  CHUNK_OVERLAP=$CHUNK_OVERLAP"
echo "  EMBEDDING_MODEL=$EMBEDDING_MODEL"
echo "  EMBEDDING_DIM=$EMBEDDING_DIM"
echo "  QDRANT_URL=$QDRANT_URL"
echo "  QDRANT_COLLECTION=$QDRANT_COLLECTION"
echo ""
echo "Secrets will be loaded from Secret Manager:"
echo "  OPENAI_API_KEY -> $OPENAI_SECRET_NAME"
echo "  REDIS_URL      -> $REDIS_SECRET_NAME"
echo "  QDRANT_API_KEY -> $QDRANT_SECRET_NAME"
echo ""
read -p "Press enter to continue..."

# Build and push the Docker image
echo ""
echo "🔨 Building and pushing Docker image..."
gcloud builds submit --tag $IMAGE_NAME --project $PROJECT_ID

# Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Cloud Run ($ENVIRONMENT)..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory $MEMORY \
  --cpu $CPU \
  --concurrency $CONCURRENCY \
  --timeout 600 \
  --max-instances $MAX_INSTANCES \
  --min-instances $MIN_INSTANCES \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars "$ENV_VARS" \
  --set-secrets OPENAI_API_KEY=${OPENAI_SECRET_NAME}:latest,REDIS_URL=${REDIS_SECRET_NAME}:latest,QDRANT_API_KEY=${QDRANT_SECRET_NAME}:latest \
  --project $PROJECT_ID

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo "================================================"
echo "Environment: $ENVIRONMENT"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Test the health endpoint:"
echo "   curl $SERVICE_URL/"
echo ""
echo "2. Create a Pub/Sub push subscription:"
echo "   gcloud pubsub subscriptions create ${SERVICE_NAME}-sub \\"
echo "     --topic=YOUR_TOPIC_NAME \\"
echo "     --push-endpoint=$SERVICE_URL/ \\"
echo "     --project $PROJECT_ID"
echo ""
echo "3. Set environment variables in Cloud Run:"
echo "   gcloud run services update $SERVICE_NAME \\"
echo "     --region $REGION \\"
echo "     --update-env-vars CHUNK_SIZE=1024,CHUNK_OVERLAP=200,... \\"
echo "     --project $PROJECT_ID"
echo ""
echo "   Or use secrets:"
echo "   gcloud run services update $SERVICE_NAME \\"
echo "     --region $REGION \\"
echo "     --update-secrets OPENAI_API_KEY=openai-api-key:latest,... \\"
echo "     --project $PROJECT_ID"
echo ""
echo "================================================"

