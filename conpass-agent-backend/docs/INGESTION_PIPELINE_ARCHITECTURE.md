# Contract Ingestion Pipeline Architecture

## Table of Contents

1. [Overview](#overview)
2. [Architecture Overview](#architecture-overview)
3. [High-Level Design](#high-level-design)
4. [Component Details](#component-details)
5. [Data Flow](#data-flow)
6. [Technical Implementation](#technical-implementation)
7. [Message Structure](#message-structure)
8. [Error Handling & Resilience](#error-handling--resilience)
9. [Performance Considerations](#performance-considerations)
10. [Scalability](#scalability)
11. [Future Enhancements](#future-enhancements)
12. [Next Steps](#next-steps)

## Related Documentation

- [Contract Sync Handler Context](CONTRACT_SYNC_HANDLER_CONTEXT.md) - Architecture and design for incremental contract updates
- [Contract Sync Handler Setup Guide](CONTRACT_SYNC_HANDLER_SETUP_GUIDE.md) - Step-by-step deployment instructions

---

## Overview

The Contract Ingestion Pipeline is a serverless, event-driven system designed to efficiently extract contract data from a MySQL database, process it in batches, and index it for downstream consumption. The pipeline is built on Google Cloud Platform using Cloud Functions, Pub/Sub, and is designed to scale automatically with the volume of contract data.

### Key Objectives

- **Efficient Batch Processing**: Process contracts in batches to optimize throughput and reduce overhead
- **Decoupled Architecture**: Separate data fetching from processing to enable independent scaling
- **Resilience**: Handle failures gracefully with at-least-once delivery semantics
- **Scalability**: Automatically scale based on message volume
- **Future-Proof**: Designed to extend to Cloud Storage and other data sources

---

## Architecture Overview

The pipeline consists of three main stages:

1. **Data Fetching & Publishing (CF1)**: Fetches contract data from MySQL and publishes batches to Pub/Sub
2. **Processing & Indexing (CF2)**: Consumes batches from Pub/Sub, processes them, and stores embeddings in Qdrant Vector DB
3. **Contract Sync Handler**: Handles incremental contract updates via webhook from ConPass backend (see [Contract Sync Handler Documentation](CONTRACT_SYNC_HANDLER_CONTEXT.md))

```text
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   MySQL     │◄────────│     CF1      │────────►│   Pub/Sub   │
│   Database  │  Query  │  (Fetcher)   │ Publish │   (Topic)   │
└─────────────┘         └──────────────┘         └──────┬──────┘
                                                         │
                                                         │ Trigger
                                                         ▼
                                                 ┌──────────────┐
                                                 │     CF2      │────────►┌──────────────┐
                                                 │  (Processor) │  Store  │   Qdrant     │
                                                 └──────────────┘         │  Vector DB   │
                                                                          └──────────────┘

┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  ConPass    │────────►│   API        │────────►│  Contract   │────────►┌─────────────┐
│  Backend    │ Webhook │   Gateway    │  HTTP   │  Sync       │ Publish │   Pub/Sub   │
│  (Django)   │         │              │         │  Handler    │         │   (Topic)   │
└─────────────┘         └──────────────┘         └──────────────┘         └─────────────┘
```

### Components

| Component | Type | Purpose |
|-----------|------|---------|
| **CF1** | Cloud Function (HTTP) | Fetch contracts from MySQL and publish to Pub/Sub |
| **Pub/Sub** | Message Broker | Decouple CF1 and CF2, enable async processing |
| **CF2** | Cloud Function (Pub/Sub Trigger) | Process batches and create embeddings |
| **Contract Sync Handler** | Cloud Function (HTTP via API Gateway) | Handle incremental contract updates via webhook |
| **Qdrant Vector DB** | Vector Database | Store processed contract embeddings |
| **MySQL** | External Database | Source of contract data |

---

## High-Level Design

### Design Principles

1. **Separation of Concerns**: Data fetching (CF1) and processing (CF2) are completely independent
2. **Event-Driven**: Asynchronous processing using Pub/Sub for decoupling
3. **Batch Processing**: Group contracts into batches to optimize throughput
4. **Idempotency**: CF2 must handle duplicate messages gracefully
5. **Connection Management**: Use connection pooling and context managers for database connections

### Flow Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Independent task to populate queue                    │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐           │
│  │   CF1    │───────►│   MySQL  │───────►│  Pub/Sub │           │
│  │ (Fetcher)│ Query  │   DB     │ Publish│  Topic   │           │
│  └──────────┘        └──────────┘        └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Messages (batches of 10)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Independent task to make embeddings                   │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐           │
│  │  Pub/Sub │───────►│   CF2    │───────►│  Qdrant  │           │
│  │  Topic   │ Pull   │(Processor)│ Store │ Vector DB│           │
│  └──────────┘        └──────────┘        └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### CF1: Data Fetcher & Publisher

**Trigger**: HTTP (can be invoked manually or via Cloud Scheduler)

**Responsibilities**:

- Connect to external MySQL database
- Count total contracts in the database
- Fetch contracts in batches of 10
- Join related data from multiple tables
- Serialize data to JSON
- Publish batches to Pub/Sub topic

**Database Queries**:
Fetches contracts with joins to:

- `conpass_contract`: Main contract table (filtered by `type = 1` AND `status = 1`)
- `conpass_contractbody`: Latest version of contract body text only
- `conpass_metadata`: Metadata entries (joined with `conpass_metakey`, filtered by `mk.type = 1` AND `md.status = 1`)
- `conpass_directory`: Directory information

**Filtering Criteria**:

- Contracts: `type = 1` AND `status = 1`
- Contract Bodies: Only the latest version (using MAX version per contract)
- Metadata: `mk.type = 1` AND `md.status = 1`

**Key Features**:

- **Connection Pooling**: Uses context managers (`with` statements) for efficient database connection management
- **Batch Processing**: Groups 10 contracts per Pub/Sub message
- **JSON Serialization**:  
  - Datetime values converted to ISO format
  - UTF-8 encoding with `ensure_ascii=False`
  - Nested structure with batch metadata
- **Error Handling**: Each batch is published independently, ensuring partial failures don't affect entire operation

**Optimizations**:

- **Filtered Queries**: Only fetches contracts with `type = 1` and `status = 1` to reduce data volume
- **Latest Version Only**: Fetches only the latest version of each contract body using MAX(version) subquery
- **Filtered Metadata**: Only includes metadata entries with `mk.type = 1` and `md.status = 1`
- **Minimal Fields**: Removes unnecessary fields (score, offsets, status, lock) from metadata output
- **Batch Queries**: Uses batch queries to minimize database round trips
- **Async Publishing**: Collects all publish futures and waits for completion after processing all batches
- **Efficient JSON Serialization**: UTF-8 encoding with `ensure_ascii=False` for international characters
- **Scheduled Trigger**: Use `manual=true` query string parameter to schedule subsequent cloud function invocation
**Output**:  

- Publishes structured JSON messages to Pub/Sub topic
- Each message contains one batch (10 contracts) with full metadata

### Pub/Sub

**Topic**: Acts as message broker between CF1 and CF2

**Trigger Type**: Push-based (Pub/Sub → CF2)

**Behavior**:

- Each published batch from CF1 triggers one independent CF2 execution
- Automatic message delivery to CF2
- Supports parallel processing of multiple batches

**Delivery Semantics**:

- **At-least-once**: Messages may be delivered multiple times
- **Implications**: CF2 must be idempotent to handle duplicates

**Message Limits**:

- Maximum message size: 10 MB
- Supports larger batch sizes (100-200 contracts) if message size allows

### CF2: Consumer / Processor

**Trigger**: Pub/Sub event (automatic)

**Responsibilities**:

- Receive Pub/Sub message
- Decode Base64-encoded message payload
- Parse JSON to extract batch and contract details
- Decode HTML/URL-encoded contract body content
- Process contracts (e.g., create embeddings, validate data)
- Store embeddings in Qdrant Vector DB

**Decoding Process**:

1. Base64 decode Pub/Sub message data
2. JSON decode into Python object
3. Extract contract body text
4. Decode URL-encoded content using `urllib.parse.unquote` (e.g., `%3Cp%3E` → `<p>`)

**Logging**:

- Batch number
- Contract count per batch
- Contract details for debugging
- Processing status and errors

**Scalability**:

- Automatically scales with Pub/Sub message throughput
- Each batch processed independently
- Multiple CF2 instances can run in parallel

**Future Enhancements**:

- Add idempotency checks to handle duplicate deliveries
- Implement retry logic for failed batches
- Add validation and data quality checks

### Contract Sync Handler

**Trigger**: HTTP via API Gateway (webhook from ConPass backend)

**Responsibilities**:

- Receive webhook events from ConPass backend when contracts are created or updated
- Fetch latest contract data from MySQL for specified contract IDs
- Publish contract updates to the same Pub/Sub topic as CF1
- Enable incremental processing without full re-ingestion

**Key Features**:

- **Webhook Integration**: Receives contract sync requests via API Gateway
- **Selective Fetching**: Only fetches contracts specified in the webhook payload
- **Same Data Format**: Publishes to Pub/Sub using the same message structure as CF1
- **Authentication**: Secured via API Gateway with API key authentication
- **Filtered Queries**: Applies same filters as CF1 (`type = 1`, `status = 1`)

**Payload Format**:

```json
{
  "contract_ids": [123, 456],
  "event_type": "created" | "updated"
}
```

**Integration Flow**:

1. ConPass backend sends webhook on contract create/update
2. API Gateway authenticates and routes request
3. Contract Sync Handler fetches latest contract data from MySQL
4. Publishes to Pub/Sub topic (same as CF1)
5. CF2 processes the update and updates Qdrant Vector DB

**Documentation**:

- [Contract Sync Handler Context](CONTRACT_SYNC_HANDLER_CONTEXT.md) - Architecture and design overview
- [Contract Sync Handler Setup Guide](CONTRACT_SYNC_HANDLER_SETUP_GUIDE.md) - Deployment and configuration instructions

### Qdrant Vector DB

**Purpose**: Store processed contract embeddings for retrieval and search

**Storage**:

- Receives processed contract data from CF2
- Stores vector embeddings along with metadata
- Enables semantic search and retrieval

---

## Data Flow

### Step-by-Step Process

1. **CF1 Initialization**
   - CF1 receives HTTP request (manual or scheduled)
   - Establishes connection to MySQL database using connection pooling

2. **Contract Counting**
   - CF1 queries database to count total contracts
   - Determines number of batches (total_contracts / batch_size)

3. **Batch Fetching**
   - CF1 fetches contracts in batches of 10
   - For each batch, joins:
     - `conpass_contract` (main contract data)
     - `conpass_contractbody` (body text)
     - `conpass_metadata` (joined with `conpass_metakey`)
     - `conpass_directory` (directory info)

4. **Data Serialization**
   - Converts datetime values to ISO format
   - Serializes to JSON with UTF-8 encoding (`ensure_ascii=False`)
   - Creates structured message with batch metadata

5. **Publishing to Pub/Sub**
   - Each batch published as separate Pub/Sub message
   - Messages include:
     - `batch_number`: Sequential batch identifier
     - `contracts`: Array of 10 contracts with full metadata

6. **Pub/Sub Delivery**
   - Pub/Sub delivers message to CF2
   - Each message triggers independent CF2 execution

7. **CF2 Processing**
   - CF2 receives Pub/Sub event
   - Base64 decodes message data
   - JSON parses into Python object
   - Iterates through contracts in batch
   - Decodes URL/HTML-encoded contract body text
   - Processes each contract (creates embeddings, validates data)

8. **Storage in Qdrant**
   - CF2 stores processed embeddings in Qdrant Vector DB
   - Includes metadata for search and retrieval

### Example Flow

```text
100 contracts in database
  ↓
CF1 creates 10 batches (10 contracts each)
  ↓
10 separate Pub/Sub messages published
  ↓
10 independent CF2 executions triggered (can run in parallel)
  ↓
Each CF2 processes its batch and stores in Qdrant
```

---

## Technical Implementation

### CF1 Implementation Details

**Database Connection**:

```python
# Pseudo-code structure
with mysql_connection_pool.get_connection() as conn:
    with conn.cursor() as cursor:
        # Count total contracts
        cursor.execute("SELECT COUNT(*) FROM conpass_contract")
        total_count = cursor.fetchone()[0]
        
        # Fetch in batches
        for batch_num in range(0, total_count, batch_size):
            contracts = fetch_batch(cursor, batch_num, batch_size)
            message = create_message(batch_num, contracts)
            publish_to_pubsub(message)
```

**Query Structure**:

- **Contract Query**: Fetches contracts filtered by `type = 1` AND `status = 1`, joins with directory table
- **Body Query**: Uses subquery with MAX(version) to fetch only the latest contract body version per contract
- **Metadata Query**: Fetches metadata filtered by `mk.type = 1` AND `md.status = 1`, includes only key, label, and value fields
- **Optimized Fields**: Removed unnecessary fields (type, status from contract; score, offsets, status, lock from metadata)

**JSON Serialization**:

- Datetime objects converted to ISO format strings
- UTF-8 encoding with `ensure_ascii=False` for international characters
- Nested structure preserving relationships

### CF2 Implementation Details

**Message Decoding**:

```python
# Pseudo-code structure
import base64
import json
from urllib.parse import unquote

def process_pubsub_message(event):
    # Decode Pub/Sub message
    message_data = base64.b64decode(event.data)
    batch_data = json.loads(message_data)
    
    # Extract batch info
    batch_number = batch_data['batch_number']
    contracts = batch_data['contracts']
    
    # Process each contract
    for contract in contracts:
        # Decode URL-encoded body text
        body_text = unquote(contract['body']['text'])
        
        # Process contract (create embeddings, etc.)
        process_contract(contract, body_text)
        
        # Store in Qdrant
        store_embedding(contract)
```

**Encoding Handling**:

- Contract body may contain HTML-encoded or URL-encoded content
- Example: `%3Cp%3EContract%20Body%3C%2Fp%3E` → `<p>Contract Body</p>`
- Uses `urllib.parse.unquote()` for decoding

### Error Handling

**CF1**:

- Each batch published independently
- If one batch fails to publish, others continue
- Database connection errors handled with retries
- Logging for debugging failed batches

**CF2**:

- Individual contract processing failures logged but don't stop batch
- Retry logic for transient errors (Pub/Sub automatic retries)
- Idempotency checks (to be implemented) to handle duplicate messages

**Pub/Sub**:

- Automatic retries for failed deliveries
- Dead letter queue for messages that fail repeatedly
- At-least-once delivery semantics

---

## Message Structure

### JSON Message Format

Each Pub/Sub message contains a JSON object with the following structure:

```json
{
  "batch_number": 3,
  "contracts": [
    {
      "id": 42,
      "name": "Business Agreement",
      "directory": {
        "id": 5,
        "name": "Client Contracts"
      },
      "body": "%3Cp%3EContract%20Body%20Text%3C%2Fp%3E",
      "metadata": [
        {
          "key": "party_name",
          "label": "Party Name",
          "value": "ABC Corp"
        },
        {
          "key": "contract_date",
          "label": "Contract Date",
          "value": "2024-01-15T00:00:00"
        }
      ]
    }
  ]
}
```

### Field Descriptions

**Top Level**:

- `batch_number` (integer): Sequential batch identifier
- `contracts` (array): Array of contract objects (typically 10 per batch)

**Contract Object**:

- `id` (integer): Unique contract identifier
- `name` (string): Contract name
- `directory` (object): Directory information
  - `id` (integer): Directory ID
  - `name` (string): Directory name
- `body` (string): Contract body text (latest version only, may be URL/HTML encoded)
- `metadata` (array): Array of metadata entries (filtered by `mk.type = 1` AND `md.status = 1`)
  - `key` (string): Metadata key
  - `label` (string): Human-readable label
  - `value` (string): Metadata value (from `value` or `date_value` field, ISO format for dates)

---

## Error Handling & Resilience

### CF1 Error Handling

**Database Connection Failures**:

- Connection pooling with automatic retry
- Context managers ensure connections are properly closed
- Log errors and continue with remaining batches

**Publishing Failures**:

- Each batch published independently
- Failed batches logged but don't prevent other batches from publishing
- Retry logic for transient Pub/Sub errors

**Data Serialization Errors**:

- JSON serialization errors caught and logged
- Datetime conversion errors handled gracefully
- Invalid data skipped with error logging

### CF2 Error Handling

**Message Decoding Errors**:

- Base64 decode errors caught and logged
- JSON parse errors handled with error messages
- Invalid message structure logged and skipped

**Processing Errors**:

- Individual contract processing failures don't stop batch
- Errors logged with contract ID for debugging
- Retry logic for transient errors (embedding generation, storage)

**Duplicate Message Handling** (To Be Implemented):

- Idempotency checks using message IDs or contract IDs
- Skip processing if contract already processed
- Ensure idempotent operations in Qdrant storage

### Pub/Sub Resilience

**At-Least-Once Delivery**:

- Messages may be delivered multiple times
- CF2 must handle duplicates gracefully
- Idempotency is critical for correctness

**Dead Letter Queue**:

- Messages that fail repeatedly are sent to dead letter queue
- Manual review and reprocessing capability
- Monitoring and alerting on dead letter queue

---

## Performance Considerations

### Batch Size Optimization

**Current**: 10 contracts per batch

**Considerations**:

- **Smaller batches** (5-10): Lower memory usage, more Pub/Sub messages, better parallelization
- **Larger batches** (50-200): Fewer Pub/Sub messages, higher throughput, but larger message size

**Constraints**:

- Pub/Sub message size limit: 10 MB
- Each contract includes full metadata and body text
- Estimate message size per contract to determine optimal batch size

**Recommendation**:

- Start with 10 contracts per batch (current)
- Monitor message sizes and processing times
- Increase to 50-100 if message size allows and throughput improves

### Throughput Analysis

**Example Scenario**: 1000 contracts

**With 10 contracts per batch**:

- 100 Pub/Sub messages
- 100 CF2 executions (can run in parallel)
- Higher parallelization, more Pub/Sub overhead

**With 100 contracts per batch**:

- 10 Pub/Sub messages
- 10 CF2 executions
- Lower parallelization, less Pub/Sub overhead

**Optimal Strategy**:

- Balance between parallelization and message overhead
- Consider contract size variation
- Monitor CF2 execution times and Pub/Sub message delivery rates

### Database Query Optimization

**Connection Pooling**:

- Reuse connections across batches
- Minimize connection overhead
- Context managers ensure proper cleanup

**Query Optimization**:

- Use efficient JOINs
- Index on frequently queried columns
- Limit data fetched to necessary fields

**Batch Queries**:

- Fetch multiple contracts per query
- Reduce database round trips
- Use LIMIT and OFFSET for pagination
- Use subqueries for latest version selection (MAX version per contract)
- Filter at database level to reduce data transfer

### Memory Management

**CF1**:

- Process one batch at a time
- Release memory after each batch
- Limit concurrent operations
- Async publishing: Collect all publish futures, wait for completion after all batches processed
- Filtered queries reduce memory footprint by excluding unnecessary data

**CF2**:

- Process contracts sequentially within batch
- Release embeddings after storage
- Monitor memory usage per batch

---

## Scalability

### Automatic Scaling

**CF1**:

- HTTP-triggered Cloud Function
- Can be invoked concurrently for multiple ingestion jobs
- Scales based on HTTP request volume

**CF2**:

- Pub/Sub-triggered Cloud Function
- Automatically scales with message volume
- Each message triggers independent execution
- Multiple instances can run in parallel

**Scaling Characteristics**:

- **Linear scaling**: Throughput increases linearly with message volume
- **Parallel processing**: Multiple batches processed simultaneously
- **No shared state**: Each execution is independent

### Scaling Limits

**Pub/Sub**:

- Maximum message size: 10 MB
- High throughput (millions of messages per second)
- Automatic scaling based on subscription backlog

**Cloud Functions**:

- Concurrent executions: Up to 1000 per region (default)
- Can be increased for higher throughput
- Memory and CPU limits per function instance

**Database**:

- External MySQL database may become bottleneck
- Consider connection pooling and query optimization
- Future: Migrate to Cloud SQL or use Cloud Storage exports

### Monitoring & Observability

**Key Metrics**:

- CF1 execution time and success rate
- Number of batches published
- Pub/Sub message delivery rate
- CF2 execution time and success rate
- Qdrant storage success rate
- Error rates and dead letter queue size

**Logging**:

- Batch numbers and contract counts
- Processing times per batch
- Error details with contract IDs
- Performance metrics

---

## Future Enhancements

### Immediate Improvements

1. **Idempotency in CF2**
   - Implement duplicate message detection
   - Use message IDs or contract IDs for deduplication
   - Ensure idempotent Qdrant operations

2. **Enhanced Error Handling**
   - Dead letter queue processing
   - Retry logic with exponential backoff
   - Error notification and alerting

3. **Monitoring & Observability**
   - Cloud Monitoring dashboards
   - Alerting on errors and performance degradation
   - Log aggregation and analysis

### Medium-Term Enhancements

1. **Cloud Storage Integration**
   - Export contract data to Cloud Storage
   - CF1 reads from Cloud Storage instead of direct MySQL
   - Reduces load on production database
   - Enables batch processing of historical data

2. **Cloud SQL Migration**
   - Migrate from external MySQL to Cloud SQL
   - Better integration with GCP services
   - Automated backups and high availability

3. **Incremental Processing** ✅ **Implemented**
   - Contract Sync Handler handles incremental updates via webhook
   - See [Contract Sync Handler Documentation](CONTRACT_SYNC_HANDLER_CONTEXT.md) for details
   - Reduces processing time for regular updates without full re-ingestion

4. **Data Validation**
   - Validate contract data structure
   - Check required fields
   - Data quality metrics and reporting

### Long-Term Enhancements

1. **Multi-Source Ingestion**
   - Support multiple data sources (APIs, files, databases)
   - Unified ingestion pipeline
   - Source-specific adapters

2. **Streaming Processing**
   - Real-time processing of new contracts
   - Event-driven architecture
   - Near-instant indexing

3. **Advanced Processing**
   - Multi-stage processing pipeline
   - Content enrichment and analysis
   - Automatic metadata extraction

4. **Performance Optimization**
   - Caching layer for frequently accessed data
   - Batch optimization based on historical data
   - Predictive scaling

---

## Next Steps

### Priority 1: Implementation

1. **Complete CF1 Implementation**
   - Implement database connection and query logic
   - Add batch fetching with joins
   - Implement Pub/Sub publishing
   - Add error handling and logging

2. **Complete CF2 Implementation**
   - Implement Pub/Sub message decoding
   - Add contract processing logic
   - Implement Qdrant storage
   - Add error handling and logging

3. **Add Idempotency**
   - Implement duplicate detection in CF2
   - Add idempotency checks for Qdrant operations
   - Test with duplicate messages

### Priority 2: Testing & Validation

1. **Unit Tests**
   - Test CF1 batch fetching and publishing
   - Test CF2 message decoding and processing
   - Test error handling scenarios

2. **Integration Tests**
   - End-to-end pipeline testing
   - Test with sample contract data
   - Validate message structure and data flow

3. **Performance Testing**
   - Test with various batch sizes
   - Measure throughput and latency
   - Identify bottlenecks

### Priority 3: Deployment & Monitoring

1. **Deploy Cloud Functions**
   - Deploy CF1 (HTTP trigger)
   - Deploy CF2 (Pub/Sub trigger)
   - Configure Pub/Sub topic and subscription

2. **Set Up Monitoring**
   - Configure Cloud Monitoring dashboards
   - Set up alerting for errors
   - Monitor performance metrics

3. **Documentation**
   - API documentation for CF1
   - Deployment guide
   - Operational runbook

---

## Appendix

### Database Schema (Inferred)

**conpass_contract**:

- `id`: Primary key
- `name`: Contract name
- `type`: Contract type
- `status`: Status code

**conpass_contractbody**:

- `contract_id`: Foreign key to conpass_contract
- `text`: Contract body text
- `version`: Version identifier

**conpass_metadata**:

- `contract_id`: Foreign key to conpass_contract
- `key_id`: Foreign key to conpass_metakey
- `value`: Metadata value
- `score`: Confidence score
- `offset`: Character offsets

**conpass_metakey**:

- `id`: Primary key
- `key`: Metadata key
- `label`: Human-readable label
- `type`: Data type

**conpass_directory**:

- `id`: Primary key
- `name`: Directory name

### Configuration Requirements

**Environment Variables**:

- MySQL connection string
- Pub/Sub topic name
- Qdrant connection details
- Logging configuration

**Cloud Function Configuration**:

- Memory allocation
- Timeout settings
- Retry policies
- IAM permissions

---

**Document Version**: 1.0  
**Last Updated**: 07/11/2025
**Author**: H. M. Atahar Nur
