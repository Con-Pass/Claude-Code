# Contract Sync Handler Context

## Goal

Handle incremental Conpass contract changes automatically so downstream systems
stay in sync without full re-ingestion runs.

## Current Baseline

- **CF1**: Batch fetch from MySQL → publish to Pub/Sub.
- **CF2**: Consume Pub/Sub → extract/embed → store in vector DB.
- Flow covers bulk ingestion only; deltas require manual intervention today.

## New Component: Contract Sync Handler

| Aspect          | Details                                                                 |
|-----------------|-------------------------------------------------------------------------|
| Trigger         | HTTP via Google API Gateway (webhook from Conpass app).                 |
| Payload         | `{ "contract_ids": [<int>], "event_type": "created" \| "updated" }`.        |
| Responsibility  | Fetch latest contract/body from MySQL, publish same Pub/Sub topic as CF1.|
| Optional Checks | Detect duplicate versions before publishing to reduce redundant work.   |

## Endpoint Security

- Use API Gateway to front Contract Sync Handler.
- Conpass backend calls endpoint using either:
  - IAM service account JWT, or
  - Restricted API key (preferred if simpler to deploy).
- API Gateway enforces HTTPS and request auth.

## Update Handling Expectations

- **New Contract** → publish for CF2 to index.
- **Existing Contract**:
  - Body version change → re-ingest; CF2 replaces/updates vector record.
  - Metadata/directory change → update stored metadata in downstream systems.
- Consider keeping local version tracking table to skip duplicates.

## Optional Enhancements

- MySQL trigger/change table for offline reconciliation.
- Pub/Sub dead-letter topic + retry policy for robustness.
- Lightweight cache (e.g., Cloud Memorystore) to dedupe repeated webhook events.

## Resulting Flow

```text
Conpass App
    └─ contract_created/updated webhook
        └─ API Gateway (auth, routing)
            └─ Contract Sync Handler
                └─ Fetch latest contract/body from MySQL
                └─ Publish to ingestion Pub/Sub topic
                    └─ CF2
                        └─ Update embeddings / vector DB
```

## Next Steps

1. Implement Contract Sync Handler function with MySQL + Pub/Sub access.
2. Deploy API Gateway configuration & authenticate Conpass calls.
3. Extend CF2 (or auxiliary services) to upsert vector entries on updates.
4. Set up monitoring + alerts for webhook failures and Pub/Sub DLQs.

