# Generate Embeddings Pipeline - Cloud Run

This service processes contract documents and generates embeddings using LlamaIndex, storing them in Pinecone vector database. It's designed to run on Google Cloud Run and receive messages from Google Cloud Pub/Sub.

## Architecture

- **Runtime**: Cloud Run (containerized FastAPI application)
- **Trigger**: Pub/Sub push subscription
- **Vector Store**: Pinecone
- **Document Store**: Redis
- **Embeddings**: OpenAI

## Prerequisites

- Google Cloud Project with Cloud Run and Pub/Sub enabled
- Pinecone account and index
- Redis instance (for document store)
- OpenAI API key

## Environment Variables

The following environment variables need to be set:

```bash
CHUNK_SIZE=1024
CHUNK_OVERLAP=200
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
OPENAI_API_KEY=your_openai_api_key
REDIS_URL=redis://your-redis-host:6379
```

## Qdrant Metadata Indexes

Each batch run invokes `ensure_payload_indexes()` to create/verify the payload indexes that power metadata filtering in Qdrant.  
Indexed fields (english aliases) include `title`, `company_a`–`company_d`, `contract_type`, `contract_date`, `contract_start_date`, `contract_end_date`, `cancel_notice_date`, `auto_update`, and `court`.  
If the upstream metadata schema changes, update `metadata_map.py` (to populate the alias) and `qdrant_indexes.py` (to index it) before ingesting new data.

## Local Development

1. Create a `.env` file with the required environment variables:

```bash
cp .env.example .env
# Edit .env with your actual values
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run locally:

```bash
python main.py
```

The service will start on `http://localhost:8080`.

## Docker Build and Test

Build the Docker image:

```bash
docker build -t generate-embeddings .
```

Run locally with Docker:

```bash
docker run -p 8080:8080 --env-file .env generate-embeddings
```

## Deployment to Cloud Run

The service supports deployment to three separate environments: **dev**, **staging**, and **prod**. Each environment will be deployed as a separate Cloud Run service with environment-specific configurations.

### Option 1: Using the deploy.sh script (Recommended)

The `deploy.sh` script handles building and deploying to the specified environment:

```bash
# Deploy to dev environment
./deploy.sh dev

# Deploy to staging environment
./deploy.sh staging

# Deploy to prod environment
./deploy.sh prod
```

The script will:
- Build and push the Docker image to Google Container Registry
- Deploy to Cloud Run with environment-specific service names:
  - `generate-embeddings-dev`
  - `generate-embeddings-staging`
  - `generate-embeddings-prod`
- Apply environment-specific resource configurations:
  - **dev**: 2Gi memory, 1 CPU, 0-2 instances
  - **staging**: 2Gi memory, 1 CPU, 0-3 instances
  - **prod**: 4Gi memory, 2 CPU, 1-5 instances

**Important**: After deployment, you need to set environment variables and secrets for each service. You can do this via:

1. **Using gcloud CLI**:
```bash
# Set environment variables
gcloud run services update generate-embeddings-dev \
  --region asia-northeast1 \
  --update-env-vars CHUNK_SIZE=1024,CHUNK_OVERLAP=200,EMBEDDING_MODEL=text-embedding-3-small,EMBEDDING_DIM=1536 \
  --project conpass-agent

# Set secrets
gcloud run services update generate-embeddings-dev \
  --region asia-northeast1 \
  --update-secrets OPENAI_API_KEY=openai-api-key:latest,QDRANT_API_KEY=qdrant-api-key:latest,REDIS_URL=redis-url:latest \
  --project conpass-agent
```

2. **Using GCP Console**: Navigate to Cloud Run → Select service → Edit & Deploy New Revision → Variables & Secrets

### Option 2: Using gcloud CLI directly

For manual deployment:

```bash
# Build and push
gcloud builds submit --tag gcr.io/conpass-agent/generate-embeddings --project conpass-agent

# Deploy to specific environment (example: dev)
gcloud run deploy generate-embeddings-dev \
  --image gcr.io/conpass-agent/generate-embeddings \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 600 \
  --max-instances 2 \
  --min-instances 0 \
  --service-account embeddings-sa@conpass-agent.iam.gserviceaccount.com \
  --set-env-vars ENVIRONMENT=dev,CHUNK_SIZE=1024,CHUNK_OVERLAP=200,EMBEDDING_MODEL=text-embedding-3-small,EMBEDDING_DIM=1536 \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest,QDRANT_API_KEY=qdrant-api-key:latest,REDIS_URL=redis-url:latest \
  --project conpass-agent
```

### Option 2: Using Cloud Build with cloudbuild.yaml

Create a `cloudbuild.yaml` file:

```yaml
steps:
  - name: "gcr.io/cloud-builders/docker"
    args: ["build", "-t", "gcr.io/$PROJECT_ID/generate-embeddings", "."]
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/generate-embeddings"]
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    entrypoint: gcloud
    args:
      - "run"
      - "deploy"
      - "generate-embeddings"
      - "--image=gcr.io/$PROJECT_ID/generate-embeddings"
      - "--region=us-central1"
      - "--platform=managed"
images:
  - "gcr.io/$PROJECT_ID/generate-embeddings"
```

## Setting up Pub/Sub Push Subscription

After deploying to Cloud Run, create environment-specific Pub/Sub push subscriptions:

```bash
# For dev environment
export SERVICE_NAME="generate-embeddings-dev"
export REGION="asia-northeast1"
export PROJECT_ID="conpass-agent"
export SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' --project $PROJECT_ID)

gcloud pubsub subscriptions create generate-embeddings-dev-sub \
  --topic=your-topic-name \
  --push-endpoint=$SERVICE_URL/ \
  --push-auth-service-account=embeddings-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --project $PROJECT_ID

# Repeat for staging and prod with appropriate service names
```

**Note**: Each environment should have its own Pub/Sub topic/subscription to route messages to the correct service.

## API Endpoints

### GET /

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "service": "generate-embeddings"
}
```

### POST /

Main endpoint for processing Pub/Sub push messages.

**Expected Pub/Sub Message Format:**

```json
{
  "message": {
    "data": "base64-encoded-batch-data",
    "messageId": "message-id",
    "publishTime": "2024-01-01T00:00:00Z"
  },
  "subscription": "projects/project/subscriptions/sub"
}
```

**Batch Data Format (decoded):**

```json
{
  "batch_number": 1,
  "contracts_count": 10,
  "contracts": [
    {
      "id": "contract-id",
      "name": "Contract Name",
      "body": "URL-encoded HTML content",
      "metadata": [{ "key": "key1", "value": "value1" }]
    }
  ]
}
```

## Resource Configuration

- **Memory**: 2Gi (recommended, adjust based on batch size)
- **CPU**: 2 (recommended)
- **Timeout**: 3600 seconds (1 hour, for large batches)
- **Concurrency**: 1-10 (start with 1 to avoid rate limits)

## Monitoring

Monitor your Cloud Run service:

```bash
# View logs
gcloud logs tail --service=$SERVICE_NAME

# View metrics in Cloud Console
https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME/metrics
```

## Troubleshooting

### Common Issues

1. **Timeout errors**: Increase the timeout or reduce batch size
2. **Memory errors**: Increase memory allocation
3. **Rate limiting**: Reduce concurrency and add backoff logic
4. **Redis connection issues**: Check REDIS_URL and network access

### Debug Locally

To test with a sample Pub/Sub message:

```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "base64-encoded-data",
      "messageId": "test-message-id",
      "publishTime": "2024-01-01T00:00:00Z"
    }
  }'
```

## Differences from Cloud Functions Version

- Uses FastAPI instead of functions-framework
- Receives Pub/Sub messages as HTTP POST requests
- Runs as a containerized service with configurable resources
- Can handle longer-running tasks (up to 60 minutes)
- Better support for custom dependencies and system packages

## Performance Tuning

1. **Batch Size**: Adjust the batch size in your upstream pipeline
2. **Concurrency**: Set Cloud Run concurrency based on your workload
3. **Instance Count**: Configure min/max instances for auto-scaling
4. **Redis Connection Pooling**: Already implemented via RedisKVStore
5. **Embedding Batch Size**: Modify in the pipeline configuration

## Security

- Use Secret Manager for sensitive environment variables
- Enable authentication for the Cloud Run service
- Use service accounts with minimal required permissions
- Enable VPC connector for private network access to Redis

## Cost Optimization

- Use Cloud Run's scale-to-zero capability
- Set minimum instances to 0 for development
- Use appropriate instance sizes (don't over-provision)
- Monitor and optimize batch sizes
- Consider using Spot VMs for cost savings
