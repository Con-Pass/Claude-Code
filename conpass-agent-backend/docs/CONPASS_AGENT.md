# ConPass AI Agent - Comprehensive Documentation

## Overview

The ConPass AI Agent is an intelligent contract management assistant designed for the ConPass platform. It helps users search, analyze, understand, and manage their contract portfolio through advanced AI capabilities including natural language processing, vector search (RAG), and AI-powered risk analysis.

## Agent Modes

The agent operates in two distinct modes based on the session type:

### 1. General Mode

Provides comprehensive contract management capabilities with all five tools available:

- `metadata_search` - Contract metadata search
- `semantic_search` - Contract content search (RAG)
- `read_contracts_tool` - Full contract text retrieval
- `risk_analysis_tool` - AI-powered risk assessment
- `web_search_tool` - External information research

### 2. CONPASS_ONLY Mode

A streamlined mode with limited capabilities, providing only:

- `metadata_search` - Contract metadata search
- `semantic_search` - Contract content search (RAG)

This mode is designed for scenarios where risk analysis, full contract reading, and web search are not required.

## Core Capabilities

### Expertise Areas

- **Contract Search & Retrieval**: Advanced metadata-based contract discovery
- **Contract Content Understanding**: RAG-based semantic search across contract documents
- **Risk Analysis**: AI-powered identification and assessment of contract risks
- **Full Document Reading**: Complete contract text retrieval for detailed review
- **Web Research**: External information gathering for legal and business context
- **Japanese Business Contracts**: Specialized support for Japanese legal terminology and contract structures

## Tools & Capabilities

### 1. metadata_search (PRIMARY TOOL)

**Purpose**: Retrieve contracts based on natural language queries using metadata filters.

**When to Use**:

- User asks to find, show, fetch, get, list, or search for contracts
- User specifies criteria like company names, dates, contract types, or other metadata
- User wants a list or overview of contracts matching certain conditions
- **CRITICAL**: This should be the FIRST tool choice for any contract search or listing request

**Technical Implementation**:

- Converts natural language queries to precise Qdrant vector database filters
- Uses `text_to_qdrant_filters` module to parse user queries into structured filters
- Searches Qdrant collection with metadata filters
- Retrieves documents from Redis document store
- Maximum limit: 20 contracts per query (configurable)

**Search Capabilities**:

- **Company Names**: Search by party designations (甲/乙/丙/丁 - Party A/B/C/D)
- **Dates**: Filter by contract date (契約日), start date (契約開始日), end date (契約終了日), cancel notice date
- **Contract Metadata**: Search by title, court (裁判所), contract type (契約種別)
- **Auto-Renewal**: Find contracts with automatic renewal (自動更新の有無)
- **Other Fields**: Person in charge, amount ranges, and other metadata fields

**Returns**:

```python
{
    "success": bool,
    "query": str,
    "filter_reasoning": str,  # Explanation of filters applied
    "filter_used": dict,      # Qdrant filter dictionary
    "contracts": [
        {
            "contract_id": int,  # Essential for other tools
            "metadata": {
                "title": str,
                "company_a": str,
                "company_b": str,
                "company_c": str,
                "company_d": str,
                "contract_type": str,
                "contract_date": str,
                "contract_start_date": str,
                "contract_end_date": str,
                "auto_update": str,
                "cancel_notice_date": str,
                "court": str
            },
            "url": str  # Frontend URL to contract
        }
    ],
    "contracts_found": int,  # Total matching contracts
    "contracts_shown": int  # Contracts returned in response
}
```

**Important Notes**:

- Automatically filters by user's `directory_ids` for permission-based access
- Uses today's date for relative date queries (e.g., "contracts ending this month")
- Provides `filter_reasoning` to explain how the query was interpreted

### 2. semantic_search (CONTENT SEARCH ONLY)

**Purpose**: Answer questions about contract content using Retrieval-Augmented Generation (RAG) with vector search.

**When to Use ONLY**:

- User asks CONTENT questions: "what does the contract say about X", "explain clause Y", "what are the terms for Z"
- User wants to understand specific provisions, clauses, or obligations WITHIN contracts
- User asks about specific contract language or wording
- User needs to search INSIDE contract text for specific information

**DO NOT USE** for finding or listing contracts - use `metadata_search` instead.

**Technical Implementation**:

- Uses LlamaIndex query engine with vector similarity search
- Searches across indexed contract document chunks
- Applies metadata filters for directory permissions automatically
- Returns source nodes with relevance scores and excerpts
- Configurable `TOP_K` setting for number of results

**Capabilities**:

- Semantic search across all indexed contract documents
- Retrieves relevant passages and text chunks
- Provides context-aware answers with source citations
- Filters by directory permissions automatically
- Returns source nodes with metadata, scores, and URLs

**Returns**:

```python
[
    {
        "source_number": int,
        "contract_id": int,
        "contract_url": str,
        "metadata": dict,  # Contract metadata
        "excerpt": str     # Relevant text snippet
    }
]
```

**Important Notes**:

- Searches actual contract content, not metadata
- Results include source citations that should be referenced in responses
- Automatically filters by user permissions via `directory_ids`

### 3. read_contracts_tool

**Purpose**: Read the full text body of specific contracts.

**When to Use**:

- User explicitly asks to read, show the full text, or display the entire contract
- User asks to explain the contract
- User wants complete contract content for detailed review
- User wants to read specific sections that need full context

**DO NOT USE** for risk analysis - use `risk_analysis_tool` instead.

**Technical Implementation**:

- Retrieves complete contract text from Redis document store
- Hard limit: Maximum 4 contracts at a time
- Returns full text as stored in document store

**Returns**:

```python
[
    {
        "contract_id": int,
        "contract_body": str  # Full contract text
    }
]
```

**Important Notes**:

- Hard limit of 4 contracts per call
- Only use when user explicitly wants full text
- For large contracts, consider summarizing key sections
- Automatically enforces directory permission filtering

### 4. risk_analysis_tool

**Purpose**: Perform comprehensive AI-powered risk analysis on contracts.

**When to Use**:

- User asks to analyze risks, assess, evaluate, or check for problems
- User wants to understand legal, financial, operational, compliance, reputational, or strategic risks
- User needs recommendations for contract negotiation or mitigation
- User wants to identify high-risk clauses

**Technical Implementation**:

- Fetches full contract text from document store
- Calls `perform_risk_analysis` function with contract body
- Uses AI model to analyze contract content
- Hard limit: Maximum 2 contracts at a time
- Results returned in Japanese (designed for Japanese contracts)

**Capabilities**:

- Analyzes up to 2 contracts at a time (hard limit)
- Identifies clause-level risks with categories:
  - Legal
  - Financial
  - Operational
  - Compliance
  - Reputational
  - Strategic
- Provides risk ratings: Low, Medium, High, Critical
- Evaluates likelihood and impact for each risk
- Generates recommendations and next steps

**Returns**:

```python
[
    {
        "contract_id": int,
        "contract_name": str,
        "parties": list,
        "summary": {
            "purpose": str,
            "key_obligations": list
        },
        "risks": [
            {
                "clause": str,
                "snippet": str,
                "risk_type": str,  # Legal, Financial, etc.
                "description": str,
                "likelihood": str,  # High/Medium/Low
                "impact": str,      # High/Medium/Low
                "risk_level": str,  # Critical/High/Medium/Low
                "recommendation": str,
                "confidence_score": float
            }
        ],
        "category_summary": dict,  # Overview by risk category
        "overall_risk_rating": str,  # Critical/High/Medium/Low
        "summary_comment": str,      # Executive summary
        "high_risk_clauses": list,
        "next_steps": list
    }
]
```

**Important Notes**:

- Automatically fetches and analyzes full contract text
- Results are in Japanese (designed for Japanese business contracts)
- Hard limit of 2 contracts per analysis
- Should highlight critical and high risks prominently in responses

### 5. web_search_tool

**Purpose**: Search the web for external information and context.

**When to Use**:

- User asks questions that require current/external information
- User wants to research legal precedents, regulations, or industry standards
- User needs context about companies, laws, or market conditions
- User asks about topics not covered in contracts (e.g., "what is the latest labor law?")

**Technical Implementation**:

- Uses OpenAI's web search capability
- Configured for Japan-focused searches (Tokyo timezone, JP country)
- Uses GPT-4o-mini model with temperature 0.3
- Returns formatted, easy-to-read search results

**Capabilities**:

- Searches the web using OpenAI's web search API
- Japan-focused: Tokyo timezone, JP country code
- Retrieves current information and external sources
- Supplements contract data with real-world context

**Returns**:

```python
{
    "feedback": str,    # Status message
    "results": str      # Formatted web search results
}
```

**Important Notes**:

- Use when contract data alone is insufficient
- Good for legal research, company background checks, regulatory updates
- Should be combined with contract tools for comprehensive analysis
- Results are formatted for easy reading

## Workflow & Decision Making

### Tool Selection Priority

The agent follows a strict decision tree for tool selection:

1. **ALWAYS CHECK FIRST**: Is the user asking to find, list, or identify contracts?

   - **YES** → Use `metadata_search` FIRST
   - **NO** → Continue to step 2

2. **What type of query is it?**
   - Ask about contract content/clauses → `semantic_search`
   - Read full contract text → `read_contracts_tool` (max 4)
   - Analyze risks → `risk_analysis_tool` (max 2)
   - Research external info → `web_search_tool`
   - Complex multi-part query → Combine tools in sequence

### Sequential Workflows

1. **Find contracts first** (`metadata_search`) → Get `contract_ids`
2. **Then read, analyze, or query** those specific contracts
3. **Supplement with web search** if needed

### Tool Combinations

Common workflow patterns:

- **Find all NDAs and analyze their risks**: `metadata_search` + `risk_analysis_tool`
- **Show contracts ending soon and renewal terms**: `metadata_search` + `semantic_search`
- **Analyze contract and research similar cases**: `risk_analysis_tool` + `web_search_tool`
- **Find contracts and read full text**: `metadata_search` + `read_contracts_tool`

## Response Formatting

### Critical Formatting Rules

All responses MUST be in well-formatted markdown with predictable structure:

1. **Always use markdown tables** for contract lists and risk summaries
2. **Always use headers** (##, ###) to organize sections
3. **Always use bullet points** for lists and key points
4. **Always bold** important information (dates, risk levels, counts, warnings)
5. **Always cite sources** with clear references
6. **Always separate major sections** with horizontal rules (---) when appropriate

### Contract Lists Format

```markdown
## Contracts Found

| Contract ID | Title             | Company A | Company B | Contract Date | Start Date | End Date   | Auto-Renewal | Court                |
| ----------- | ----------------- | --------- | --------- | ------------- | ---------- | ---------- | ------------ | -------------------- |
| 123         | Service Agreement | ABC Corp  | XYZ Ltd   | 2024-01-15    | 2024-02-01 | 2025-01-31 | Yes          | Tokyo District Court |

**Total contracts found: X**

### Key Findings

- [Important observation 1]
- [Important observation 2]
```

### Risk Analysis Format

```markdown
## Risk Analysis Results

### Overall Assessment

- **Overall Risk Rating**: [Critical/High/Medium/Low]
- **Contracts Analyzed**: X
- **High/Critical Risks Found**: Y

---

## Contract [ID]: [Name]

### Risk Summary

- **Overall Risk**: [Critical/High/Medium/Low]
- **Total Risks Identified**: X
- **Critical/High Risks**: Y

### Critical Risks

| Clause | Risk Type | Likelihood     | Impact         | Recommendation |
| ------ | --------- | -------------- | -------------- | -------------- |
| [X]    | [Type]    | [High/Med/Low] | [High/Med/Low] | [Action]       |

### Next Steps

1. [Action 1]
2. [Action 2]
```

### Content Query Format

```markdown
## Answer

[Clear answer to the question]

### Key Points

- Point 1
- Point 2
- Point 3

### Sources

- Contract ID: [ID] - [Title]
- Contract ID: [ID] - [Title]
```

## Important Constraints

### Tool Limits

- **read_contracts_tool**: Max 4 contracts at a time (hard limit)
- **risk_analysis_tool**: Max 2 contracts at a time (hard limit)
- **metadata_search**: Max 20 contracts per query (configurable)
- If user requests more, inform them of the limit

### Tool Usage Rules

- **Do NOT** use `read_contracts_tool` for risk analysis → use `risk_analysis_tool`
- **Do NOT** use `semantic_search` for metadata search → use `metadata_search`
- **Do NOT** guess information → use `web_search_tool` to research

### Privacy and Permissions

- Only access contracts within user's `directory_ids`
- Tools automatically filter by permissions
- All tools respect directory-based access control

### Data Accuracy

- Never fabricate contract information
- If uncertain, say so and offer to search more
- Distinguish between contract data and web-sourced information

### Response Guidelines

- **Answer the query**: Provide exactly what the user asked for
- **State facts**: Mention important findings found in the data
- **No suggestions**: Do NOT ask if they want additional analysis, exports, or other actions
- **No feature offers**: Do NOT offer capabilities that may not be implemented

## Date Awareness

Today's date is automatically provided to all tools. The agent uses it for:

- Contracts ending this year → calculate date range
- Expired contracts → filter by `end_date < today`
- Upcoming renewals → filter by near-future dates
- Contracts older than 2 years → calculate from today
- Relative queries: "last month", "next quarter", "within 30 days"

## Technical Architecture

### Data Storage

- **Qdrant**: Vector database for contract embeddings and metadata filtering
- **Redis**: Document store for full contract text and metadata
- **LlamaIndex**: RAG framework for semantic search and query processing

### Permission Model

- All tools filter by `directory_ids` parameter
- Users can only access contracts in their authorized directories
- Permission filtering is automatic and enforced at the tool level

### Query Processing

- Natural language queries are converted to Qdrant filters via `text_to_qdrant_filters`
- Vector similarity search for content queries via LlamaIndex
- Metadata filtering for structured searches via Qdrant

### Error Handling

- **No results found**: Suggest alternative search criteria or broader filters
- **Query ambiguous**: Ask clarifying questions
- **Tool errors**: Explain issue clearly, suggest alternatives
- **Limit exceeded**: Inform user and offer to process in batches
- **Outside capabilities**: Explain limitations professionally and suggest what can be done

## Success Criteria

The agent excels when:

1. ✅ User quickly finds and understands their contracts
2. ✅ Risk analyses are thorough, accurate, and actionable
3. ✅ Information is well-organized and professionally presented
4. ✅ Tool usage is efficient and appropriate
5. ✅ Sources are clearly cited
6. ✅ Critical issues are prominently highlighted when found
7. ✅ Responses are focused and concise without unnecessary suggestions
8. ✅ Does NOT suggest features, exports, or actions that are not implemented

## Example Use Cases

### Use Case 1: Risk-Focused Workflow

**User Query**: "Find all contracts ending in 2025 and analyze their risks"

**Tool Sequence**:

1. `metadata_search` - Find contracts ending in 2025
2. `risk_analysis_tool` - Analyze up to 2 contracts (inform user if more found)

**Response**: Contract list table + Risk analysis with structured tables and recommendations

### Use Case 2: Comprehensive Due Diligence

**User Query**: "Analyze all contracts with ABC Corp and research their financial status"

**Tool Sequence**:

1. `metadata_search` - Find ABC Corp contracts
2. `risk_analysis_tool` - Analyze contracts
3. `web_search_tool` - Research ABC Corp financial status

**Response**: Contract list + Risk analysis + External research with integrated assessment

### Use Case 3: Renewal Management

**User Query**: "Show contracts requiring action this month"

**Tool Sequence**:

1. `metadata_search` - Find contracts with upcoming deadlines
2. `semantic_search` - Find renewal/termination procedures

**Response**: Contract list with deadlines + Required actions with procedures

### Use Case 4: Content Understanding

**User Query**: "What do our NDAs say about confidentiality periods?"

**Tool Sequence**:

1. `metadata_search` - Find NDA contracts (optional, if user wants list)
2. `semantic_search` - Search for confidentiality period clauses

**Response**: Structured answer with key points and source citations

## Implementation Details

### Tool Registration

Tools are registered based on session type in `app/services/chatbot/tools/tools.py`:

- **CONPASS_ONLY**: `semantic_search` + `metadata_search`
- **Full Mode**: All five tools

### System Prompts

Two system prompts are defined in `app/services/chatbot/system_prompts.py`:

- `SYSTEM_PROMPT`: Full mode with all capabilities
- `CONPASS_ONLY_SYSTEM_PROMPT`: Limited mode with basic search

### Directory Filtering

All tools receive `directory_ids` parameter and automatically filter results:

- Qdrant queries include directory_id filters
- Document store queries check directory permissions
- Vector search filters by directory metadata

### Date Handling

Today's date is injected into tool descriptions at runtime, allowing tools to:

- Calculate relative date ranges
- Filter expired contracts
- Identify upcoming deadlines
- Process relative queries ("this month", "next quarter")

## Bilingual Support

The agent supports both Japanese and English:

- **Risk analysis results**: Returned in Japanese (designed for Japanese contracts)
- **User queries**: Can be in Japanese or English
- **Responses**: Can be in Japanese or English based on user preference
- **Metadata fields**: Support Japanese field names (契約日, 契約種別, etc.)

## Best Practices

1. **Always start with metadata_search** when finding contracts
2. **Use semantic_search for content questions**, not metadata searches
3. **Respect tool limits** and inform users when limits are reached
4. **Format responses consistently** using markdown tables and structured sections
5. **Cite sources** for all information provided
6. **Highlight critical issues** prominently when found
7. **Do not suggest unimplemented features** or capabilities
8. **Combine tools effectively** for comprehensive analysis
9. **Use date awareness** for relative queries
10. **Maintain professional tone** as a trusted legal-business advisor
