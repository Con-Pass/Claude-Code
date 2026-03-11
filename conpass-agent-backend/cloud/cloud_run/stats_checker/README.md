# ConPass Stats Checker

Cloud Function to check Redis contract counts and Qdrant point counts across all environments (dev, staging, prod).

## Quick Deploy

All secrets already exist in Secret Manager ✅

```bash
cd cloud/cloud_run/stats_checker

chmod +x deploy.sh
./deploy.sh
```

## What It Does

Returns statistics for all 3 environments in one call:

```json
{
  "environments": {
    "dev": {
      "redis_contract_count": 150,
      "qdrant_point_count": 4500,
      "collection_name": "contracts"
    },
    "staging": { ... },
    "prod": { ... }
  }
}
```

## Files

```
stats_checker/
├── main.py                    # Cloud Function code
├── requirements.txt           # Dependencies
├── deploy.sh                  # Deployment script
└── README.md                  # This file
```

## Configuration

### Secrets (from Secret Manager)

Already created and managed in GCP Secret Manager:

- `redis-url-dev`, `redis-url-staging`, `redis-url-prod`
- `qdrant-api-key-dev`, `qdrant-api-key-staging`, `qdrant-api-key-prod`

### Environment Variables (in deploy.sh)

Edit `deploy.sh` if Qdrant URLs or collection names change:

- `DEV_QDRANT_URL` - Currently: `https://24f4bcad-b4c2-4989-8ace-0016603c7435.us-east4-0.gcp.cloud.qdrant.io:6333`
- `STAGING_QDRANT_URL` - Currently: `https://cd89cdd4-30e7-4a36-a09c-0e716a28326b.ap-northeast-1-0.aws.cloud.qdrant.io`
- `PROD_QDRANT_URL` - Currently: `https://6bb243c9-13ea-4424-a8ba-aa597a335481.ap-northeast-1-0.aws.cloud.qdrant.io`
- Collection names: `contracts` (all environments)

## Usage

### After Deployment

```bash
# Get function URL
FUNCTION_URL=$(gcloud functions describe conpass-stats-checker \
  --region asia-northeast1 --gen2 \
  --format="value(serviceConfig.uri)")

# Call function
curl $FUNCTION_URL | jq
```

### Local Testing

```bash
# Set environment variables
export DEV_REDIS_URL="redis://..."
export DEV_QDRANT_URL="https://..."
export DEV_QDRANT_API_KEY="..."
# ... repeat for STAGING and PROD

# Run locally
python main.py
```

## Troubleshooting

### Wrong Results

Check if configuration in `deploy.sh` is correct, then redeploy:

```bash
./deploy.sh
```

### View Logs

```bash
gcloud functions logs read conpass-stats-checker \
  --region asia-northeast1 \
  --limit 50
```

### Verify Configuration

```bash
# Check environment variables
gcloud functions describe conpass-stats-checker \
  --region asia-northeast1 --gen2 \
  --format="value(serviceConfig.environmentVariables)"

# Check secrets
gcloud functions describe conpass-stats-checker \
  --region asia-northeast1 --gen2 \
  --format="value(serviceConfig.secretEnvironmentVariables)"
```

## Architecture

```
Cloud Function (stats_http)
  ↓
  ├─ DEV: Redis + Qdrant
  ├─ STAGING: Redis + Qdrant
  └─ PROD: Redis + Qdrant
  ↓
JSON Response
```

## Updating

### Update Secrets

```bash
# Update a secret value
echo -n "new-value" | gcloud secrets versions add redis-url-dev --data-file=-

# Redeploy to use new version
./deploy.sh
```

### Update Configuration

1. Edit `deploy.sh` (update Qdrant URLs if needed)
2. To change collection name, edit `main.py` line 125
3. Run `./deploy.sh`

## Notes

- Function timeout: 60 seconds
- Memory: 512MB
- Service account: `embeddings-sa@conpass-agent.iam.gserviceaccount.com`
- Region: `asia-northeast1`
- Project: `conpass-agent`
