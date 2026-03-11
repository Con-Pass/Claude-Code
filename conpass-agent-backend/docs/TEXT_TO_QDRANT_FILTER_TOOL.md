# Text to Qdrant Filter Tool

## Overview

The **Text to Qdrant Filter Tool** is an intelligent tool that converts natural language queries into Qdrant filter expressions and executes them to retrieve relevant contract documents. It uses LLM-powered query understanding to automatically generate appropriate metadata filters.

## Features

- **Natural Language Understanding**: Converts user queries in natural language (English or Japanese) into structured Qdrant filters
- **Complex Query Support**: Handles AND, OR, NOT logic, ranges, exact matches, and more
- **Metadata-Only Filtering**: Focuses on efficient metadata filtering without semantic search overhead
- **Native Qdrant Format**: Uses Qdrant's official filter format (not LlamaIndex wrappers) for maximum flexibility
- **Direct HTTP Endpoint**: Executes queries directly via Qdrant scroll API

## Architecture

```
User Query (Natural Language)
    ↓
LLM (OpenAI with structured output)
    ↓
Qdrant Filter Object
    ↓
Qdrant Scroll API (Metadata Filtering)
    ↓
Formatted Results
```

## Available Metadata Fields

The tool can filter on the following contract metadata fields:

| Field Name            | Type                | Description              | Example          |
| --------------------- | ------------------- | ------------------------ | ---------------- |
| `title`               | string              | Contract title/name      | "売買契約書"     |
| `company_a`           | string              | Company A (first party)  | "株式会社 ABC"   |
| `company_b`           | string              | Company B (second party) | "株式会社 XYZ"   |
| `company_c`           | string              | Company C (third party)  | "株式会社 DEF"   |
| `company_d`           | string              | Company D (fourth party) | "株式会社 GHI"   |
| `contract_date`       | string (YYYY-MM-DD) | Contract signing date    | "2024-03-15"     |
| `contract_start_date` | string (YYYY-MM-DD) | Contract start date      | "2024-04-01"     |
| `contract_end_date`   | string (YYYY-MM-DD) | Contract end date        | "2025-03-31"     |
| `auto_update`         | boolean             | Auto-renewal status      | true/false       |
| `cancel_notice_date`  | string (YYYY-MM-DD) | Cancellation notice date | "2024-12-31"     |
| `court`               | string              | Court jurisdiction       | "東京地方裁判所" |
| `contract_type`       | string              | Contract type            | "売買契約"       |

## Query Examples

### Simple Metadata Queries

```python
# Company match
"Show me contracts with 株式会社ABC"
"Find all contracts where company A is 株式会社ABC"

# Date filters
"Find contracts ending in 2024"
"Show contracts that start after 2024-06-01"
"Get contracts ending between 2024-01-01 and 2024-12-31"

# Boolean filters
"Show contracts with auto-renewal"
"Find contracts without auto-renewal"

# Contract type
"Show me all 売買契約 contracts"
"Find 賃貸借契約 contracts"
```

### Complex Queries

```python
# Multiple conditions (AND)
"Show contracts with 株式会社ABC that end after 2024-06-01"
"Find auto-renewal contracts with company ABC ending in 2024"

# OR conditions
"Find contracts with 株式会社ABC or 株式会社XYZ"
"Show contracts ending in 2024 or 2025"

# NOT conditions
"Show contracts ending in 2024 but not with 株式会社ABC"
"Find contracts that don't have auto-renewal"

# Nested conditions
"Show contracts with (company A as ABC or company B as XYZ) and ending after 2024-06-01"
```

## Generated Filter Format

The tool generates filters in Qdrant's native format:

### Example 1: Simple Match

**Query**: "Show me contracts with 株式会社 ABC"

**Generated Filter**:

```json
{
  "filter": {
    "must": [{ "key": "company_a", "match": { "value": "株式会社ABC" } }]
  }
}
```

### Example 2: Date Range

**Query**: "Show contracts ending in 2024"

**Generated Filter**:

```json
{
  "filter": {
    "must": [
      {
        "key": "contract_end_date",
        "range": { "gte": "2024-01-01", "lte": "2024-12-31" }
      }
    ]
  }
}
```

### Example 3: Complex AND Conditions

**Query**: "Show contracts with 株式会社 ABC that end after 2024-06-01"

**Generated Filter**:

```json
{
  "filter": {
    "must": [
      { "key": "company_a", "match": { "value": "株式会社ABC" } },
      { "key": "contract_end_date", "range": { "gte": "2024-06-01" } }
    ]
  }
}
```

### Example 4: OR Conditions

**Query**: "Show contracts with 株式会社 ABC or 株式会社 XYZ"

**Generated Filter**:

```json
{
  "filter": {
    "should": [
      { "key": "company_a", "match": { "value": "株式会社ABC" } },
      { "key": "company_a", "match": { "value": "株式会社XYZ" } }
    ]
  }
}
```

### Example 5: NOT Conditions

**Query**: "Show contracts ending in 2024 that are not with 株式会社 ABC"

**Generated Filter**:

```json
{
  "filter": {
    "must": [
      {
        "key": "contract_end_date",
        "range": { "gte": "2024-01-01", "lte": "2024-12-31" }
      }
    ],
    "must_not": [{ "key": "company_a", "match": { "value": "株式会社ABC" } }]
  }
}
```

## Usage

### As a Standalone Function

```python
from app.services.chatbot.tools.text_to_qdrant_filter_tool import query_contracts_by_metadata

# Simple query
result = await query_contracts_by_metadata(
    query="Show me contracts with 株式会社ABC",
    limit=10
)

# With custom limit
result = await query_contracts_by_metadata(
    query="Find contracts ending in 2024",
    limit=5
)
```

### As an Agent Tool

The tool is automatically registered with the agent in `tools.py`:

```python
from app.services.chatbot.tools.text_to_qdrant_filter_tool import get_text_to_qdrant_filter_tool

# Get the tool
tool = get_text_to_qdrant_filter_tool()

# The agent can now use this tool automatically
```

### Testing

Run the test script to see examples:

```bash
python scripts/test_qdrant_filter_tool.py
```

This will:

1. Test filter conversion from natural language
2. Show example filters for various query types
3. Execute full queries (if Qdrant is configured)

## Configuration

Required environment variables:

```bash
# Qdrant connection
QDRANT_URL=https://your-qdrant-instance.com
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION=your-collection-name

# LLM for filter generation
MODEL_PROVIDER=openai
MODEL=gpt-4
OPENAI_API_KEY=your-openai-key
LLM_TEMPERATURE=0.3
```

## How It Works

### 1. Query Analysis

The LLM analyzes the user's query and extracts:

- Metadata conditions (company names, dates, etc.)
- Required logical operators (AND, OR, NOT)
- Date range specifications

### 2. Filter Generation

The LLM generates a structured `QdrantFilterResponse` with:

- `filter`: The Qdrant filter object with `must`, `should`, `must_not` clauses
- `reasoning`: Explanation of how the query was interpreted

### 3. Query Execution

Uses Qdrant's `scroll` API for efficient metadata-only filtering:

- No embedding generation needed
- Fast execution
- Retrieves documents matching metadata filters

### 4. Result Formatting

Results include:

- All metadata fields
- Content excerpt (first 300 characters)
- Reasoning for the filter applied

## Filter Clauses Explained

### `must` (AND Logic)

All conditions must be satisfied:

```json
{
  "must": [
    { "key": "company_a", "match": { "value": "ABC" } },
    { "key": "contract_end_date", "range": { "gte": "2024-01-01" } }
  ]
}
```

This matches contracts where company_a is "ABC" **AND** end date is >= 2024-01-01.

### `should` (OR Logic)

At least one condition must be satisfied:

```json
{
  "should": [
    { "key": "company_a", "match": { "value": "ABC" } },
    { "key": "company_a", "match": { "value": "XYZ" } }
  ]
}
```

This matches contracts where company_a is "ABC" **OR** "XYZ".

### `must_not` (NOT Logic)

None of the conditions should be satisfied:

```json
{
  "must_not": [{ "key": "company_a", "match": { "value": "ABC" } }]
}
```

This matches contracts where company_a is **NOT** "ABC".

### Combining Clauses

You can combine multiple clauses:

```json
{
  "must": [
    {
      "key": "contract_end_date",
      "range": { "gte": "2024-01-01", "lte": "2024-12-31" }
    }
  ],
  "must_not": [{ "key": "company_a", "match": { "value": "ABC" } }]
}
```

This matches contracts ending in 2024 **AND NOT** with company ABC.

## Condition Types

### Match (Exact Value)

```json
{ "key": "company_a", "match": { "value": "株式会社ABC" } }
```

### Match Any (IN Operator)

```json
{ "key": "contract_type", "match": { "any": ["売買契約", "賃貸借契約"] } }
```

### Match Except (NOT IN Operator)

```json
{ "key": "company_a", "match": { "except": ["株式会社ABC", "株式会社XYZ"] } }
```

### Range (Numeric/Date Comparisons)

```json
{
  "key": "contract_end_date",
  "range": { "gte": "2024-01-01", "lte": "2024-12-31" }
}
```

Available operators: `gt`, `gte`, `lt`, `lte`

## Benefits

1. **User-Friendly**: Users can query in natural language without knowing filter syntax
2. **Flexible**: Handles both simple and complex queries
3. **Efficient**: Metadata-only filtering without embedding generation overhead
4. **Accurate**: Uses LLM to accurately interpret user intent
5. **Extensible**: Easy to add new metadata fields or conditions
6. **Fast**: No semantic search = faster query execution

## Limitations

1. Requires LLM API access (OpenAI)
2. LLM-generated filters may need validation for critical applications
3. Relative date expressions depend on LLM's date understanding
4. Metadata-only: Cannot search by content or semantic meaning

## Best Practices

1. **Be Specific**: More specific queries generate better filters

   - Good: "Show contracts with 株式会社 ABC ending after 2024-06-01"
   - Less Good: "Show some contracts"

2. **Use Metadata Fields**: Query based on available metadata fields

   - Supported: Company names, dates, contract type, auto-renewal
   - Not supported: Contract content, semantic queries

3. **Check Reasoning**: Review the `reasoning` field in results to understand filter logic

4. **Set Appropriate `limit`**: Control number of results
   - Default: 10 results
   - Can be adjusted based on needs

## Comparison with contract_fetch_tool

| Feature           | query_contracts_by_metadata (Qdrant) | contract_fetch_tool (ConPass API) |
| ----------------- | ------------------------------------ | --------------------------------- |
| Data Source       | Vector Database (Qdrant)             | ConPass Database (API)            |
| Filter Complexity | Complex (AND/OR/NOT)                 | API parameters                    |
| Natural Language  | Yes (LLM-powered)                    | No (structured params)            |
| Content Search    | No (metadata only)                   | No                                |
| Use Case          | Complex metadata queries             | Simple API-based queries          |
| Response Format   | Formatted text with excerpts         | Structured JSON                   |
| Agent Integration | Automatic                            | Manual parameter extraction       |

## Future Enhancements

Potential improvements:

- [ ] Caching of common filter patterns
- [ ] Filter validation and suggestion
- [ ] Support for nested object filters
- [ ] Aggregation queries (count, group by, etc.)
- [ ] Query result ranking
- [ ] Multi-language query support optimization

## References

- [Qdrant Filtering Documentation](https://qdrant.tech/documentation/concepts/filtering/)
- [Qdrant Python Client](https://github.com/qdrant/qdrant-client)
- Project files:
  - `app/services/chatbot/tools/text_to_qdrant_filter_tool.py`
  - `app/schemas/qdrant_filter.py`
  - `app/services/chatbot/tools/tool_prompts.py`
  - `app/services/chatbot/qdrant_client.py`
