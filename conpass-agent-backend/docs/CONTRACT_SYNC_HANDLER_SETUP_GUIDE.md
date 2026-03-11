# Contract Sync Handler Setup Guide: Cloud Function & API Gateway

This guide provides step-by-step instructions for creating the Contract Sync Handler Cloud Function and configuring API Gateway from the Google Cloud Console.

---

## Prerequisites

- Google Cloud Project with billing enabled
- Required APIs enabled (see **Enabling Required APIs** section below)
- Appropriate IAM permissions (Editor or Cloud Functions Admin, API Gateway Admin)
- Access to MySQL database credentials
- Pub/Sub topic created (same topic used by CF1)

### Enabling Required APIs

If you encounter `PERMISSION_DENIED: API ... is not enabled for the project` errors, enable the following APIs:

#### Step 1: Enable General APIs

1. Navigate to **APIs & Services** → **Library** in Google Cloud Console
2. Search for and enable each of the following:
   - **API Gateway API** (`apigateway.googleapis.com`)
   - **Service Management API** (`servicemanagement.googleapis.com`)
   - **Service Usage API** (`serviceusage.googleapis.com`)
   - **Cloud Functions API** (`cloudfunctions.googleapis.com`)
   - **Pub/Sub API** (`pubsub.googleapis.com`)
   - **Cloud Build API** (`cloudbuild.googleapis.com`)
   - **Cloud Run Admin API** (`run.googleapis.com`) - if using Cloud Run backend

**Quick Enable via gcloud CLI**:

```bash
gcloud services enable \
  apigateway.googleapis.com \
  servicemanagement.googleapis.com \
  serviceusage.googleapis.com \
  cloudfunctions.googleapis.com \
  pubsub.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  --project=conpass-agent
```

#### Step 2: Enable Managed Service API (After Gateway Creation)

After creating your API Gateway, you'll also need to enable the specific **managed service API** that gets created. This is the service that appears in the error message.

**Find your managed service API name**:

- Check the error message: `API records-sync-api-v2-2hrvnr9ehz7pk.apigateway.conpass-agent.cloud.goog is not enabled`
- Or find it in **API Gateway** → Your Gateway → **API Details** → **Managed Service**

**Enable the managed service API**:

```bash
gcloud services enable \
  records-sync-api-v2-2hrvnr9ehz7pk.apigateway.conpass-agent.cloud.goog \
  --project=conpass-agent
```

**Replace with your actual managed service name** if different.

**Note**:

- It may take a few minutes for APIs to be fully enabled. Wait 2-3 minutes after enabling before retrying.
- The managed service API name is unique to your API Gateway and will be different for each gateway you create.

---

## Part 1: Create Cloud Function (Contract Sync Handler)

### Step 1: Navigate to Cloud Functions

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project (`conpass-agent`)
3. Navigate to **Cloud Functions** from the left sidebar
4. Click **CREATE FUNCTION**

### Step 2: Basic Settings

1. **Function name**: `contract-sync-handler` (or `records-sync-handler`)
2. **Region**: Select the same region as your existing CF1/CF2 (e.g., `us-central1`, `asia-northeast1`)
3. **Environment**: Choose **2nd gen** (recommended) or **1st gen**
4. Click **NEXT**

### Step 3: Trigger Configuration

1. **Trigger type**: Select **HTTPS (Trigger)**
2. **Authentication**: Select **Require authentication** (we'll secure via API Gateway)
3. **Allow unauthenticated invocations**: **Unchecked** (API Gateway will handle auth)
4. Click **NEXT**

### Step 4: Runtime Configuration

1. **Runtime**: Select **Python 3.12** (or latest Python 3.x)
2. **Entry point**: `records_sync_handler` (or your function name)
3. **Memory**: `512 MB` (adjust based on needs)
4. **Timeout**: `540 seconds` (max for Cloud Functions)
5. **CPU**: `1` (default)

### Step 5: Code Configuration

#### Option A: Inline Editor (for testing)

1. Select **Inline editor**
2. **main.py**: Upload or paste your Contract Sync Handler code
3. **requirements.txt**: Include dependencies:

   ```text
   functions-framework==3.*
   google-cloud-pubsub==2.*
   pymysql==1.*
   httpx==0.*
   ```

#### Option B: Source Repository (recommended for production)

1. Select **Source code**
2. Choose **Cloud Source Repositories**, **GitHub**, or **Bitbucket**
3. Select your repository and branch
4. Specify **Source directory**: `cloud/cloud_run/contract_sync_automation/` (if code is in subdirectory)

### Step 6: Environment Variables

Add the following environment variables:

```env
DB_HOST=your-mysql-host
DB_USER=your-mysql-user
DB_PASS=your-mysql-password
DB_NAME=conpass
```

**Note**: For sensitive values (DB_PASS), consider using **Secret Manager**:

1. Create secrets in **Secret Manager**
2. Reference them as: `DB_PASS=projects/PROJECT_ID/secrets/DB_PASSWORD/versions/latest`

### Step 7: Advanced Settings

1. **Service account**: Select or create a service account with:
   - `Pub/Sub Publisher` role
   - `Secret Manager Secret Accessor` (if using secrets)
2. **VPC Connector**: If MySQL is in a VPC, configure connector
3. **Ingress settings**: `Allow all traffic` (API Gateway will handle routing)
4. **Egress settings**: `Route all traffic through VPC` (if using VPC)

### Step 8: Deploy

1. Click **DEPLOY**
2. Wait for deployment (typically 2-5 minutes)
3. Note the **Trigger URL** (HTTPS endpoint) - you'll need this for API Gateway

---

## Part 2: Configure API Gateway

### Step 1: Create API Gateway API

1. Navigate to **API Gateway** from the left sidebar
2. Click **CREATE GATEWAY**
3. **Gateway name**: `contract-sync-gateway`
4. **API Config**: Select **CREATE NEW API CONFIG**
5. **API Config name**: `contract-sync-api-config`
6. **Backend type**: Select **Cloud Functions** (or **Cloud Run** if using Cloud Run)
7. Click **CREATE AND CONTINUE**

### Step 2: Define API Specification

You can use the YAML spec file or define manually:

#### Option A: Upload YAML Spec

1. Click **UPLOAD API CONFIG**
2. Upload your `api-gateway-spec.yaml` file
3. Click **CONTINUE**

#### Option B: Manual Configuration

1. **API name**: `contract-sync-api`
2. **Backend service**: Select your Cloud Function (`contract-sync-handler`)
3. **Path**: `/v1/sync`
4. **Method**: `POST`
5. Click **ADD PATH** if needed
6. Click **CONTINUE**

### Step 3: Gateway Configuration

1. **Region**: Select same region as Cloud Function
2. **Gateway ID**: `contract-sync-gateway` (auto-filled)
3. Click **CREATE GATEWAY**

### Step 4: Wait for Deployment

- Deployment typically takes 5-10 minutes
- Status will show **Active** when ready
- Note the **Gateway URL** (e.g., `https://record-sync-gateway-4jwt0xcj.an.gateway.dev`)

---

## Part 3: Configure Authentication

### Option A: API Key Authentication (Recommended for ConPass Backend)

1. Navigate to **APIs & Services** → **Credentials**
2. Click **CREATE CREDENTIALS** → **API Key**
3. **Restrict key**:
   - **Application restrictions**: Select **IP addresses**
   - Add ConPass backend IP addresses
   - **API restrictions**: Select **Restrict key**
   - Choose **API Gateway API**
4. Copy and save the API key securely
5. Share with ConPass backend team

### Option B: Service Account Authentication

1. Navigate to **IAM & Admin** → **Service Accounts**
2. Create or select service account for ConPass backend
3. Grant role: **API Gateway Invoker**
4. ConPass backend will use service account key to generate JWT tokens

### Option C: IAM-based Authentication

1. In API Gateway config, enable **Require authentication**
2. Grant **Cloud Functions Invoker** role to:
   - Service account used by ConPass backend
   - Or specific users/service accounts

---

## Part 4: Update API Gateway Spec (if using YAML)

If you're using the YAML spec file, ensure it references your Cloud Function:

```yaml
swagger: '2.0'
info:
  title: Contract Sync Handler API
  description: API Gateway for Contract Sync Handler Cloud Function
  version: 1.0.0
host: record-sync-gateway-4jwt0xcj.an.gateway.dev
schemes:
  - https
paths:
  /v1/sync:
    post:
      summary: Process contract sync event
      operationId: processSync
      x-google-backend:
        address: https://REGION-PROJECT_ID.cloudfunctions.net/contract-sync-handler
      security:
        - api_key: []
      responses:
        '200':
          description: Success
        '401':
          description: Unauthorized
        '500':
          description: Internal Server Error
securityDefinitions:
  api_key:
    type: apiKey
    name: x-api-key
    in: header
```

**Replace placeholders**:

- `REGION`: Your Cloud Function region (e.g., `us-central1`)
- `PROJECT_ID`: Your GCP project ID
- `host`: Your actual Gateway URL

---

## Part 5: Testing

### Test 1: Direct Cloud Function Call

1. Navigate to **Cloud Functions** → Select `contract-sync-handler`
2. Go to **TESTING** tab
3. **Triggering event**: Select **HTTPS trigger**
4. **HTTP method**: `POST`
5. **Request body**:

   ```json
   {
     "contract_ids": [123],
     "event_type": "created"
   }
   ```

6. Click **TEST THE FUNCTION**
7. Check logs for execution results

### Test 2: API Gateway Call

**Using curl**:

```bash
curl -X POST \
  https://record-sync-gateway-4jwt0xcj.an.gateway.dev/v1/sync \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "contract_ids": [123, 456],
    "event_type": "created"
  }'
```

**Using Postman**:

1. Method: `POST`
2. URL: `https://record-sync-gateway-4jwt0xcj.an.gateway.dev/v1/sync`
3. Headers:
   - `Content-Type: application/json`
   - `x-api-key: YOUR_API_KEY`
4. Body (raw JSON):

   ```json
   {
     "contract_ids": [123, 456],
     "event_type": "created"
   }
   ```

### Test 3: Verify Pub/Sub Message

1. Navigate to **Pub/Sub** → **Topics**
2. Select your topic (`conpass-agent-pubsub`)
3. Click **VIEW MESSAGES**
4. Verify message was published by Contract Sync Handler

---

## Part 6: Monitoring & Logging

### View Logs

1. Navigate to **Cloud Functions** → `contract-sync-handler` → **LOGS** tab
2. Filter by execution time, severity, or search terms
3. Check for errors or warnings

### Set Up Alerts

1. Navigate to **Monitoring** → **Alerting**
2. Create alert policy:
   - **Metric**: Cloud Function execution count
   - **Condition**: Error rate > threshold
   - **Notification**: Email/Slack channel

### API Gateway Monitoring

1. Navigate to **API Gateway** → Select your gateway
2. View **Metrics** tab for:
   - Request count
   - Latency
   - Error rate

---

## Part 7: Troubleshooting

### Common Issues

**Issue**: Cloud Function deployment fails

- **Solution**: Check Cloud Build logs, verify dependencies in `requirements.txt`

**Issue**: API Gateway returns 404

- **Solution**: Verify API config path matches Cloud Function trigger path

**Issue**: Authentication errors (401)

- **Solution**: Check API key is valid, service account has correct permissions

**Issue**: Cloud Function can't connect to MySQL

- **Solution**: Verify VPC connector, firewall rules, database credentials

**Issue**: Pub/Sub publish fails

- **Solution**: Check service account has `Pub/Sub Publisher` role

---

## Part 8: Integration with ConPass Backend

### Webhook Configuration in ConPass

Provide the following to ConPass backend team:

1. **Webhook URL**: `https://record-sync-gateway-4jwt0xcj.an.gateway.dev/v1/sync`
2. **Authentication**: API key (header: `x-api-key`)
3. **Expected Payload**:

   ```json
   {
     "contract_ids": [123, 456],
     "event_type": "created" | "updated"
   }
   ```

4. **Expected Response**: `200 OK` with success message

### ConPass Backend Implementation (Django)

ConPass backend should call the webhook on:

- Contract creation
- Contract update (body version change, metadata change, directory change)

#### Basic Webhook Call Example

```python
import httpx
from django.conf import settings

# In your Django view, signal, or model method
webhook_url = "https://record-sync-gateway-4jwt0xcj.an.gateway.dev/v1/sync"
api_key = settings.CONPASS_AGENT_API_KEY  # Store in settings.py

payload = {
    "contract_ids": [123, 456],  # List of contract IDs
    "event_type": "created"  # or "updated"
}

headers = {
    "Content-Type": "application/json",
    "x-api-key": api_key
}

try:
    response = httpx.post(webhook_url, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    # Success - contract sync triggered
except httpx.RequestError as e:
    # Handle error (log, retry, etc.)
    pass
```

**Document Version**: 1.0  
**Last Updated**: 2025-11-13
**Author**: H. M. Atahar Nur
