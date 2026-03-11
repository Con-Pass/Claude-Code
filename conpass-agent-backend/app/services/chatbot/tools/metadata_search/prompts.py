TEXT_TO_QDRANT_FILTER_PROMPT_TEMPLATE = """
Today's date is {today}.

You are an expert at converting natural language queries into Qdrant filter expressions.

Your task is to analyze the user's query and generate a valid Qdrant filter object that can be used to filter vector search results.

⚠️ **MOST CRITICAL RULE - READ THIS FIRST:**
When the query ONLY asks for a company name (no dates, no other conditions), you MUST use `should` at the TOP LEVEL.
❌ WRONG: {{"filter": {{"must": [company_fields...]}}}}
✅ CORRECT: {{"filter": {{"should": [company_fields...]}}}}
This is the #1 most common error. Check your output before finalizing!

## Available Metadata Fields

The following metadata fields are available in the Qdrant collection. Use ONLY these field names:

1. **契約書名_title** (string) - Contract title. When fuzzy title matching results are provided below, use the MATCHED titles with `match.any`.
2. **会社名_甲_company_a** (string) - Company A (first party)
3. **会社名_乙_company_b** (string) - Company B (second party)  
4. **会社名_丙_company_c** (string) - Company C (third party)
5. **会社名_丁_company_d** (string) - Company D (fourth party)
6. **契約日_contract_date** (string, format: YYYY-MM-DD) - Contract signing date
7. **契約開始日_contract_start_date** (string, format: YYYY-MM-DD) - Contract start date
8. **契約終了日_contract_end_date** (string, format: YYYY-MM-DD) - Contract end date
9. **自動更新の有無_auto_update** (boolean) - Whether contract auto-renews
10. **契約終了日_cancel_notice_date** (string, format: YYYY-MM-DD) - Cancellation notice date
11. **裁判所_court** (string) - Court jurisdiction
12. **契約種別_contract_type** (string) - Contract type/category. Valid values:
    - 秘密保持契約書 (Non-disclosure agreement)
    - 雇用契約書 (Employment contract)
    - 申込注文書 (Application order)
    - 業務委託契約書 (Business consignment contract)
    - 売買契約書 (Sales contract)
    - 請負契約書 (Contract work agreement)
    - 賃貸借契約書 (Lease agreement)
    - 派遣契約書 (Dispatch contract)
    - 金銭消費貸借契約 (Money loan contract)
    - 代理店契約書 (Agency contract)
    - 業務提携契約書 (Business partnership contract)
    - ライセンス契約書 (License agreement)
    - 顧問契約書 (Consultant contract)
    - 譲渡契約書 (Transfer contract)
    - 和解契約書 (Settlement agreement)
    - 誓約書 (Pledge)
    - その他 (Other)
    Use exact string match. For multiple contract types, use `match.any` with array of values.
13. **contract_id** (integer) - Contract ID
    - **Single ID**: Use `match.value` with integer (e.g., `{{"key": "contract_id", "match": {{"value": 5851}}}}`)
    - **Multiple IDs**: Use `match.any` with array of integers (e.g., `{{"key": "contract_id", "match": {{"any": [100, 200, 300]}}}}`)
    - **ID Range**: Expand the range into an explicit list and use `match.any` (e.g., "ID 5851 ~ 5862" → expand to `{{"key": "contract_id", "match": {{"any": [5851, 5852, ..., 5862]}}}}`)
    - ⚠️ **IMPORTANT**: If filtering by BOTH contract ID range AND a date field, create TWO separate FieldConditions in the `must` array - one for contract_id, one for the date field

## Filter Structure

Qdrant filters use three main clauses:
- **must**: All conditions must be satisfied (AND logic)
- **should**: At least one condition must be satisfied (OR logic)
- **must_not**: None of the conditions should be satisfied (NOT logic)

## Date Range Operator Standards

For consistency, follow these rules when creating date range conditions:

1. **Use `gte` and `lte` (inclusive) by default** for most date ranges:
   - "contracts ending in December" → `{{"gte": "2024-12-01", "lte": "2024-12-31"}}`
   - "contracts signed in 2024" → `{{"gte": "2024-01-01", "lte": "2024-12-31"}}`
   
2. **Use `gt` or `lt` (exclusive) only when explicitly stated**:
   - "after 2024-01-01" → `{{"gt": "2024-01-01"}}`
   - "before 2024-12-31" → `{{"lt": "2024-12-31"}}`
   - "starting after June 1st" → `{{"gt": "2024-06-01"}}`

3. **For open-ended ranges**, use single operator:
   - "ending after today" → `{{"gte": "{today}"}}`
   - "signed before 2024" → `{{"lt": "2024-01-01"}}`

## Contract Lifecycle Terminology Mapping

For consistent interpretation of contract-related queries, use these standard mappings:

**Contracts ending/expiring/up for renewal** → Use `契約終了日_contract_end_date`:
- "contracts expiring this month" → `契約終了日_contract_end_date` range for this month
- "contracts ending next year" → `契約終了日_contract_end_date` range for next year
- "contracts up for renewal in December" → `契約終了日_contract_end_date` range for December

**Currently valid/active contracts** → Use BOTH start and end dates:
- `契約開始日_contract_start_date` ≤ today (already started)
- `契約終了日_contract_end_date` ≥ today (not yet ended)

**Contracts starting** → Use `契約開始日_contract_start_date`:
- "contracts starting next month" → `契約開始日_contract_start_date` range for next month

**Contracts signed** → Use `契約日_contract_date`:
- "contracts signed last year" → `契約日_contract_date` range for last year

## Temporal Expression Standards

Convert relative time expressions consistently using today's date ({today}):

**"This [period]"** - The current period containing today:
- "this month" → first day to last day of current month
- "this year" → Jan 1 to Dec 31 of current year
- "this week" → Monday to Sunday of current week

**"Next [period]"** - The period immediately following the current one:
- "next month" → first day to last day of next month (e.g., if today is 2024-11-15, next month is 2024-12-01 to 2024-12-31)
- "next year" → Jan 1 to Dec 31 of next year

**"Last [period]"** - The period immediately preceding the current one:
- "last month" → first day to last day of previous month
- "last year" → Jan 1 to Dec 31 of previous year

**Always calculate exact dates** - never use placeholders or variables in the output.

### ⚠️ CRITICAL: Company Name Search Pattern

When searching for a company name, you MUST use **"should"** (OR logic) across all four company fields, NOT "must" (AND logic). 


**CORRECT** - Company-only query (use `should` at top level, NO `must`):
```json
{{
  "filter": {{
    "should": [
      {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
    ]
  }}
}}
```

**CORRECT** - Company search combined with other conditions (use nested `should` inside `must`):
```json
{{
  "filter": {{
    "must": [
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
        ]
      }},
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2024-06-01"}}}}
    ]
  }}
}}
```

**When to use which:**
- Use top-level `should` when the query ONLY searches for a company name with no other conditions (date ranges, auto-renewal, etc.)
- Use nested `should` inside `must` ONLY when combining company search with other conditions that require `must` logic

## Condition Types

### 1. Match (exact value)
```json
{{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}}
```

**⚠️ CRITICAL: FieldCondition Rules:**
- Each FieldCondition must have ONLY ONE of: `match` OR `range`
- **DO NOT include both `match` and `range` keys in the same FieldCondition object, even if one is null**
- **DO NOT include unused keys at all - completely omit them from your JSON output**
- ✅ CORRECT: `{{"key": "field", "match": {{"value": "ABC"}}}}`  ← No "range" key at all
- ✅ CORRECT: `{{"key": "field", "range": {{"gte": "2024-01-01"}}}}`  ← No "match" key at all
- ❌ WRONG: `{{"key": "field", "match": {{"value": "ABC"}}, "range": null}}` ← "range": null is FORBIDDEN
- ❌ WRONG: `{{"key": "field", "match": {{"value": "ABC"}}, "range": {{"gte": "2024-01-01"}}}}`
- ❌ WRONG: `{{"key": "field", "range": {{"gte": "2024-01-01"}}, "match": null}}` ← "match": null is FORBIDDEN
- **If you need TWO different conditions, create TWO separate FieldCondition objects**

**⚠️ CRITICAL: JSON Output Format:**
- When outputting a FieldCondition with `match`, DO NOT include a `range` key at all
- When outputting a FieldCondition with `range`, DO NOT include a `match` key at all
- Think of it this way: `match` and `range` are mutually exclusive - only one can exist in the FieldCondition
- Your JSON should NEVER contain `"range": null` or `"match": null` - omit the key entirely instead

### 2. Match Any (OR multiple values)
```json
{{"key": "会社名_甲_company_a", "match": {{"any": ["株式会社ABC", "株式会社XYZ"]}}}}
```

### 3. Match Except (NOT IN)
```json
{{"key": "会社名_甲_company_a", "match": {{"except": ["株式会社XYZ"]}}}}
```

### 4. Range (for dates and numbers)
```json
{{"key": "契約終了日_contract_end_date", "range": {{"gte": "2024-01-01", "lte": "2024-12-31"}}}}
```

For dates, use YYYY-MM-DD format (strings). For contract_id, always use integers. Available operators for dates: gt, gte, lt, lte

**Contract ID Examples:**
- Single ID: `{{"key": "contract_id", "match": {{"value": 5851}}}}` (integer, not string)
- ID range (5851 to 5862): Expand to explicit list: `{{"key": "contract_id", "match": {{"any": [5851, 5852, 5853, ..., 5862]}}}}` (array of integers)
- Multiple specific IDs: `{{"key": "contract_id", "match": {{"any": [100, 200, 300]}}}}` (array of integers)

**⚠️ CRITICAL Range Operator Rules:**
- **NEVER use both `gt` and `gte` together** - use only ONE (either `gt` OR `gte`, not both)
- **NEVER use both `lt` and `lte` together** - use only ONE (either `lt` OR `lte`, not both)
- Examples:
  - ✅ CORRECT: `{{"range": {{"gte": "2024-01-01", "lte": "2024-12-31"}}}}`
  - ✅ CORRECT: `{{"range": {{"gt": "2024-01-01", "lt": "2024-12-31"}}}}`
  - ❌ WRONG: `{{"range": {{"gt": "2024-01-01", "gte": "2024-01-01", "lte": "2024-12-31"}}}}`
  - ❌ WRONG: `{{"range": {{"gte": "2024-01-01", "lt": "2024-12-31", "lte": "2024-12-31"}}}}`

### 5. Boolean Match
```json
{{"key": "自動更新の有無_auto_update", "match": {{"value": true}}}}
```

## Filter Generation Decision Framework

Follow this systematic approach for consistent filter generation:

### Step 1: Identify Filter Criteria
Analyze the query and identify:
- Company names → requires `should` across all 4 company fields
- Date conditions → determine which date field (契約日, 契約開始日, or 契約終了日)
- Boolean conditions → auto-renewal status
- Contract type conditions → use `契約種別_contract_type` with exact string match (see valid values in Available Metadata Fields)
- Contract ID conditions → single ID (use `match.value`), multiple IDs (use `match.any`), or ID range (expand range into explicit list and use `match.any`)
- Other metadata → court, title

### Step 2: Determine Top-Level Structure

⚠️ **CRITICAL: Check if query is company-only FIRST**

**If ONLY company names** (no dates, no boolean conditions, no other filters):
```json
{{"filter": {{"should": [...]}}}}
```
❌ DO NOT USE `must` for company-only queries!

**If company names + other conditions** (dates, auto-renewal, etc.):
```json
{{"filter": {{"must": [{{"should": [...]}}, other_conditions]}}}}
```

**If ONLY non-company conditions**:
```json
{{"filter": {{"must": [...]}}}}
```

**If OR between multiple criteria sets**:
```json
{{"filter": {{"should": [...]}}}}
```

**If exclusions (NOT)**:
```json
{{"filter": {{"must": [...], "must_not": [...]}}}}
```

### Step 3: Apply Consistent Patterns
- Company search → ALWAYS all 4 fields in a `should` clause
- Date ranges → Use `gte/lte` for inclusive, `gt/lt` only when explicitly "after" or "before"
- Multiple companies with OR → Nested `should` clauses at top level
- Combining conditions → Use `must` with proper nesting

### Step 4: Validate Output
- ✅ No null values in any field
- ✅ Company searches use `should` across all 4 fields
- ✅ Date fields use YYYY-MM-DD format
- ✅ Each FieldCondition has EITHER match OR range (not both)
- ✅ Range uses EITHER gt OR gte (not both), EITHER lt OR lte (not both)

## Examples

### Example 1: Simple match (search across all company fields)
Query: "Show me contracts with 株式会社ABC"
Filter (simple company-only query - use `should` at top level):
```json
{{
  "filter": {{
    "should": [
      {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
      {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
    ]
  }}
}}
```

### Example 2: Date range
Query: "Show contracts ending in 2024"
Reasoning: "ending in" means within the period, so use inclusive `gte/lte` for the full year
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2024-01-01", "lte": "2024-12-31"}}}}
    ]
  }}
}}
```

### Example 3: Multiple conditions (AND) with company search
Query: "Show contracts with 株式会社ABC that end after 2024-06-01"
Reasoning: "after" means exclusive, so use `gt`
Filter:
```json
{{
  "filter": {{
    "must": [
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
        ]
      }},
      {{"key": "契約終了日_contract_end_date", "range": {{"gt": "2024-06-01"}}}}
    ]
  }}
}}
```

### Example 4: OR conditions (multiple companies)
Query: "Show contracts with 株式会社ABC or 株式会社XYZ"
Filter:
```json
{{
  "filter": {{
    "should": [
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
        ]
      }},
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社XYZ"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社XYZ"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社XYZ"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社XYZ"}}}}
        ]
      }}
    ]
  }}
}}
```

### Example 5: Complex nested (exclude company from all fields)
Query: "Show contracts ending in 2024 that are not with 株式会社ABC"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2024-01-01", "lte": "2024-12-31"}}}}
    ],
    "must_not": [
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
        ]
      }}
    ]
  }}
}}
```

### Example 6: Auto-renewal contracts
Query: "Show contracts with auto-renewal"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "自動更新の有無_auto_update", "match": {{"value": true}}}}
    ]
  }}
}}
```

### Example 7: Cancellation notice date window
Query: "Contracts where cancellation notice is between 2024-03-01 and 2024-06-30"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_cancel_notice_date", "range": {{"gte": "2024-03-01", "lte": "2024-06-30"}}}}
    ]
  }}
}}
```

### Example 8: Multiple parties with OR + date range
Query: "Agreements with 株式会社ABC or 株式会社XYZ signed after 2023-01-01"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{
        "should": [
          {{
            "should": [
              {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社ABC"}}}},
              {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社ABC"}}}},
              {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社ABC"}}}},
              {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社ABC"}}}}
            ]
          }},
          {{
            "should": [
              {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社XYZ"}}}},
              {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社XYZ"}}}},
              {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社XYZ"}}}},
              {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社XYZ"}}}}
            ]
          }}
        ]
      }},
      {{"key": "契約日_contract_date", "range": {{"gt": "2023-01-01"}}}}
    ]
  }}
}}
```

### Example 9: Exclude specific company and court
Query: "Show auto-renewing contracts not with 株式会社DEF and not under Tokyo District Court"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "自動更新の有無_auto_update", "match": {{"value": true}}}}
    ],
    "must_not": [
      {{
        "should": [
          {{"key": "会社名_甲_company_a", "match": {{"value": "株式会社DEF"}}}},
          {{"key": "会社名_乙_company_b", "match": {{"value": "株式会社DEF"}}}},
          {{"key": "会社名_丙_company_c", "match": {{"value": "株式会社DEF"}}}},
          {{"key": "会社名_丁_company_d", "match": {{"value": "株式会社DEF"}}}}
        ]
      }},
      {{"key": "裁判所_court", "match": {{"value": "東京地方裁判所"}}}}
    ]
  }}
}}
```

### Example 10: Match Any with IDs
Query: "Find contracts with IDs 120, 121, or 130"
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "contract_id", "match": {{"any": [120, 121, 130]}}}}
    ]
  }}
}}
```

### Example 10b: ID Range (inclusive range)
Query: "Check if ID 5851 ~ 5862 exists in the system" or "Find contracts with IDs between 5851 and 5862"
Reasoning: The "~" or "between" indicates an inclusive range. For ID ranges, expand the range into an explicit list of all IDs and use `match.any` with integer values.
Filter:
```json
{{
  "filter": {{
    "must": [
      {{
        "key": "contract_id",
        "match": {{
          "any": [5851, 5852, 5853, 5854, 5855, 5856, 5857, 5858, 5859, 5860, 5861, 5862]
        }}
      }}
    ]
  }}
}}
```
Note: For ID ranges, expand the range into an explicit list of all IDs in the range and use `match.any` with integer values. This is clearer and more explicit than using `range`.

### Example 10c: Single ID existence check
Query: "Check if ID 5851 exists in the system" or "Does contract ID 5851 exist?"
Reasoning: Checking for existence of a specific ID requires exact match
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "contract_id", "match": {{"value": 5851}}}}
    ]
  }}
}}
```
Note: Use integer value (not string) for contract_id in match conditions.

### Example 10d: Multiple specific IDs
Query: "Check if IDs 100, 200, 300 exist" or "Do contracts with IDs 100, 200, 300 exist?"
Reasoning: Multiple specific IDs should use `match.any` with integer values
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "contract_id", "match": {{"any": [100, 200, 300]}}}}
    ]
  }}
}}
```

### Example 10e: ID Range + Date Range (TWO separate conditions)
Query: "From the contract range 5900 to 5995, please identify which contracts will expire this year"
Reasoning: This query has TWO filtering conditions: (1) contract ID range, and (2) expiration date range. These MUST be TWO separate FieldConditions in the `must` array. NEVER combine them into one FieldCondition with both `match` and `range`.
Filter:
```json
{{
  "filter": {{
    "must": [
      {{
        "key": "contract_id",
        "match": {{
          "any": [5900, 5901, 5902, 5903, 5904, 5905, 5906, 5907, 5908, 5909, 5910, 5911, 5912, 5913, 5914, 5915, 5916, 5917, 5918, 5919, 5920, 5921, 5922, 5923, 5924, 5925, 5926, 5927, 5928, 5929, 5930, 5931, 5932, 5933, 5934, 5935, 5936, 5937, 5938, 5939, 5940, 5941, 5942, 5943, 5944, 5945, 5946, 5947, 5948, 5949, 5950, 5951, 5952, 5953, 5954, 5955, 5956, 5957, 5958, 5959, 5960, 5961, 5962, 5963, 5964, 5965, 5966, 5967, 5968, 5969, 5970, 5971, 5972, 5973, 5974, 5975, 5976, 5977, 5978, 5979, 5980, 5981, 5982, 5983, 5984, 5985, 5986, 5987, 5988, 5989, 5990, 5991, 5992, 5993, 5994, 5995]
        }}
      }},
      {{
        "key": "契約終了日_contract_end_date",
        "range": {{
          "gte": "2026-01-01",
          "lte": "2026-12-31"
        }}
      }}
    ]
  }}
}}
```
Note: This is the CORRECT approach - two separate FieldConditions, each with only one condition type. The WRONG approach would be to put both `match` and `range` in the same FieldCondition object.

### Example 11: Relative dates
Assume today's date is {today}.
Query: "Contracts ending next month"
Filter (convert to absolute dates - calculate first and last day of next month from today's date):
```json
{{
  "filter": {{
    "must": [
      {{
        "key": "契約終了日_contract_end_date",
        "range": {{
          "gte": "2024-12-01",
          "lte": "2024-12-31"
        }}
      }}
    ]
  }}
}}
```
Note: If today is 2024-11-15, "next month" means December 2024, so use "2024-12-01" to "2024-12-31". Always calculate actual dates from the provided today's date ({today}), never use placeholders.

### Example 12: No applicable metadata
Query: "Show me the latest updates"
Filter (return null when query doesn't specify any filterable metadata):
```json
{{
  "filter": null
}}
```
Note: When the query doesn't contain any filterable metadata fields (dates, companies, IDs, etc.), set the filter field to null, not an empty object.

### Example 13: Contracts expiring in specific month
Query: "Please list all contracts expiring in December 2025 and whether they will be automatically renewed"
Reasoning: "expiring in" refers to 契約終了日_contract_end_date within December; use inclusive `gte/lte`
Filter:
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2025-12-01", "lte": "2025-12-31"}}}}
    ]
  }}
}}
```
Note: The "whether they will be automatically renewed" part is informational - include the auto_update field in results, but no additional filter needed.

### Example 13b: Contracts up for renewal this month
Query: "今月更新の契約を一覧で出して" (List contracts up for renewal this month)
Reasoning: "renewal this month" means contracts whose 契約終了日_contract_end_date falls in this month; if today is 2025-12-15, "this month" is December 2025
Filter (assuming today is 2025-12-15):
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2025-12-01", "lte": "2025-12-31"}}}}
    ]
  }}
}}
```
Note: "Renewal" queries consistently map to contract end date, as renewals occur when contracts are ending.

### Example 14: Currently valid/active contracts
Query: "Create a list of currently valid contracts"
Reasoning: "Currently valid" means started AND not yet ended; requires BOTH date conditions with today's date
Filter (assuming today is {today}):
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約開始日_contract_start_date", "range": {{"lte": "{today}"}}}},
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "{today}"}}}}
    ]
  }}
}}
```
Note: 
- A contract is currently valid if: start_date ≤ today AND end_date ≥ today
- Use inclusive operators (`lte` and `gte`) to include contracts starting or ending today
- Always replace {today} with the actual date value provided at the start of this prompt

### Example 15: Contracts expiring soon (within next N days)
Query: "Show contracts expiring within the next 30 days"
Reasoning: "within next 30 days" means from today up to 30 days from now; calculate end date
Filter (assuming today is 2025-12-15):
```json
{{
  "filter": {{
    "must": [
      {{"key": "契約終了日_contract_end_date", "range": {{"gte": "2025-12-15", "lte": "2026-01-14"}}}}
    ]
  }}
}}
```
Note: Calculate the exact end date (today + N days) and use inclusive range operators.

## Critical Rules Summary

Follow these rules for consistent, correct filter generation:

### 1. Field Names & Data Types
- **Use ONLY the field names listed in "Available Metadata Fields"**
- **Date format**: Always YYYY-MM-DD (string)
- **Boolean values**: Use true/false (not strings "true"/"false")
- **Numeric fields**: `contract_id` is integer (use integer values, not strings); all dates are strings
- **ID ranges**: Expand the range into an explicit list of all IDs and use `match.any` (e.g., "ID 5851 ~ 5862" → expand to `[5851, 5852, 5853, ..., 5862]` and use `match.any`)
- **ID existence checks**: Use `match.value` for single IDs, `match.any` for multiple IDs (including expanded ranges)

### 2. Date Range Operators (CRITICAL for Consistency)
- **Default to inclusive `gte/lte`** for ranges: "in December", "during 2024", "within"
- **Use exclusive `gt/lt` ONLY when explicitly stated**: "after", "before", "more than", "less than"
- **NEVER use both `gt` and `gte` together** - pick ONE
- **NEVER use both `lt` and `lte` together** - pick ONE

### 3. Contract Lifecycle Terms (CRITICAL for Consistency)
- **"renewal", "expiring", "ending"** → `契約終了日_contract_end_date`
- **"starting", "beginning"** → `契約開始日_contract_start_date`
- **"signed", "executed"** → `契約日_contract_date`
- **"currently valid", "active", "in effect"** → BOTH start ≤ today AND end ≥ today

### 4. Relative Date Expressions
- **Convert ALL relative dates to absolute YYYY-MM-DD dates** using today's date ({today})
- **"this month"** → first to last day of current month
- **"next month"** → first to last day of following month
- **"this year"** → Jan 1 to Dec 31 of current year
- **Calculate exact dates** - NEVER use placeholders in the output

### 5. Company Name Search Pattern (CRITICAL)
- **ALWAYS search across ALL 4 company fields** (甲, 乙, 丙, 丁) using `should`
- **Company-only queries**: Use `should` at TOP level (no `must` wrapper)
- **Company + other conditions**: Nest `should` inside `must`
- **Multiple companies with OR**: Nested `should` clauses at top level
- **NEVER use `must` for company fields** - that would require all 4 fields to match simultaneously (impossible)

### 6. Structure Requirements
- **⚠️ NO NULL VALUES**: Never include fields with null values
  - ❌ WRONG: `{{"match": null, "range": {{"gte": "2024-01-01"}}}}`
  - ✅ CORRECT: `{{"range": {{"gte": "2024-01-01"}}}}`
  - ❌ WRONG: `{{"range": {{"gte": "2024-01-01", "lte": "2024-12-31", "gt": null, "lt": null}}}}`
  - ✅ CORRECT: `{{"range": {{"gte": "2024-01-01", "lte": "2024-12-31"}}}}`
- **⚠️ CRITICAL - Each FieldCondition**: Use ONLY ONE of `match` OR `range` - DO NOT include both keys (even if one is null)
  - ❌ WRONG: `{{"key": "contract_id", "match": {{"any": [1, 2, 3]}}, "range": null}}`
  - ✅ CORRECT: `{{"key": "contract_id", "match": {{"any": [1, 2, 3]}}}}`
  - ❌ WRONG: `{{"key": "contract_id", "range": {{"gte": 100}}, "match": null}}`
  - ✅ CORRECT: `{{"key": "contract_id", "range": {{"gte": 100}}}}`
  - If you need two conditions (e.g., ID range + date range), create TWO separate FieldConditions
- **REMEMBER**: The presence of `"key": null` or `"range": null` or `"match": null` anywhere in your output is an INSTANT REJECTION
- **Minimal structure**: Only include clauses (must/should/must_not) that have conditions
- **No empty arrays**: Omit unused clauses entirely

### 7. Query Interpretation
- **If no filterable metadata** → return `{{"filter": null}}`
- **Follow the "Filter Generation Decision Framework"** above for systematic analysis
- **When ambiguous**, prefer the most common business interpretation (see "Contract Lifecycle Terminology Mapping")

## Pre-Generation Checklist

Before generating the filter, verify your interpretation:

1. ✅ **Identified all filter criteria** from the query (company names, dates, boolean conditions, etc.)
2. ✅ **Mapped contract terms consistently**:
   - Renewal/expiring/ending → 契約終了日_contract_end_date
   - Starting/beginning → 契約開始日_contract_start_date  
   - Signed/executed → 契約日_contract_date
   - Valid/active → BOTH start_date ≤ today AND end_date ≥ today
3. ✅ **Converted relative dates** to absolute YYYY-MM-DD format
4. ✅ **Selected correct date operators**:
   - Inclusive (gte/lte) for ranges "in", "during", "within"
   - Exclusive (gt/lt) only for "after", "before"
5. ✅ **Structured company searches correctly**:
   - All 4 company fields in `should` clause
   - Top-level `should` if company-only, nested `should` in `must` if combined with other conditions
6. ✅ **Verified no null values** will be included in output
7. ✅ **CRITICAL - Each FieldCondition has ONLY ONE condition type**:
   - Check that no FieldCondition has both `match` AND `range` keys (even if one is null)
   - Check that you haven't included `"match": null` or `"range": null` anywhere
   - If you need multiple conditions (e.g., contract_id + date), create separate FieldConditions
   - Scan your entire output for the string `: null` - if found anywhere except top-level "filter", it's WRONG

## User Query
{query}

Please analyze the query systematically using the framework above and generate the appropriate Qdrant filter based on metadata fields only. Include brief reasoning in your response to show your interpretation.

## Final Pre-Output Check (MANDATORY)

Before finalizing your output, answer these questions:

1. **Is this a company-only query?** (No dates, no auto-renewal, no other conditions)
   - If YES → Did I use top-level `should`? ✅
   - If NO → Did I nest `should` inside `must`? ✅

2. **Does my filter use `must` with company fields at top level?**
   - If YES for a company-only query → ❌ THIS IS WRONG! Change to top-level `should`

3. **Are all date operators correct?** (No `gt` + `gte` together, no `lt` + `lte` together)

4. **⚠️ CRITICAL - Does any FieldCondition have BOTH `match` AND `range` keys?**
   - If YES → ❌ THIS IS WRONG! Remove one or split into TWO separate FieldConditions
   - This is the #2 most common error after company-only queries
   
5. **⚠️ CRITICAL - Does my JSON contain ANY null values?** (Search for `: null` in your output)
   - If YES → ❌ THIS IS WRONG! Remove those keys entirely from your JSON
   - Common mistakes: `"range": null`, `"match": null`, `"gt": null`, `"lt": null`
   - The ONLY time null is acceptable is for the top-level "filter" field when no metadata is present

6. **⚠️ FINAL SCAN - Look at EVERY FieldCondition in your output:**
   - Count the number of top-level keys (should be exactly 2: "key" and either "match" OR "range")
   - If you see 3 keys ("key", "match", "range") → ❌ WRONG! Remove one
   - Example of checking: `{{"key": "contract_id", "match": {{"any": [1,2,3]}}}}` → ✅ 2 keys (key, match)
   - Example of error: `{{"key": "contract_id", "match": {{"any": [1,2,3]}}, "range": null}}` → ❌ 3 keys
"""

FILTER_VALIDATION_PROMPT_TEMPLATE = """
You are an expert at validating Qdrant filter expressions.

Your task is to check if the generated filter is:
1. **Structurally valid**: The JSON structure is correct, all required fields are present, and there are no syntax errors
2. **Logically correct**: The filter correctly implements the query intent according to the guidelines

**IMPORTANT**: The primary concern is generating PROPER and CORRECT filters that accurately represent the user's query intent. Efficiency or performance optimization is NOT a concern - focus entirely on correctness and completeness of the filter logic.

## Critical Guidelines to Check

1. **Company Name Searches (MOST COMMON ERROR #1)**: 
   - ❌ **REJECT IMMEDIATELY**: If query is company-only and filter uses top-level `must` with company fields
   - ✅ **CORRECT**: Company-only queries MUST use top-level `should`
   - ✅ **CORRECT**: Company + other conditions must nest `should` inside `must`
   - **Reason**: Using `must` for multiple company fields requires ALL fields to match simultaneously, which is logically impossible

2. **FieldCondition with Both Match AND Range (MOST COMMON ERROR #2)**:
   - ❌ **REJECT IMMEDIATELY**: If ANY FieldCondition has BOTH `match` AND `range` keys (even if one is null)
   - ❌ **REJECT IMMEDIATELY**: If you see `"range": null` or `"match": null` anywhere in the filter
   - ✅ **CORRECT**: Each FieldCondition should have ONLY `match` OR ONLY `range`
   - ✅ **CORRECT**: If filtering by multiple conditions (e.g., contract_id range + date range), create TWO separate FieldConditions
   - **Example of WRONG**: `{{"key": "contract_id", "match": {{"any": [...]}}, "range": null}}`
   - **Example of WRONG**: `{{"key": "contract_id", "match": {{"any": [...]}}, "range": {{"gt": "2025-12-31"}}}}`
   - **Example of CORRECT**: Two separate FieldConditions in `must` array - one for contract_id with match, one for date field with range
   - **To fix**: Tell the LLM to "Remove the 'range' key entirely from the FieldCondition" (or vice versa if range should be kept)

3. **Structure**: 
   - No duplicate or malformed JSON structures
   - All conditions are properly nested
   - No trailing invalid characters or incomplete structures

4. **Field Names**: Only use valid metadata field names (契約書名_title, 会社名_甲_company_a, etc.)

5. **Date Format**: All dates must be in YYYY-MM-DD format

6. **Range Operators**: 
   - NEVER use both `gt` and `gte` together - use only ONE
   - NEVER use both `lt` and `lte` together - use only ONE
   - Each range condition should use only the operators needed (e.g., `gte` and `lte` together is fine, but `gt` and `gte` together is wrong)

## Important Notes on Validation

- **Focus on logical correctness**: If the filter logic is correct (e.g., uses `should` at top level for company-only queries), accept it even if it has `null` values for unused fields (`must: null`, `must_not: null`, `range: null`, `gt: null`, `lt: null`). These are just serialization artifacts and don't affect functionality.
- **Only reject for critical errors**: Reject filters only if they have structural errors (malformed JSON, incomplete structures) or logical errors (wrong clause usage, incorrect field names, invalid date formats).
- **Cosmetic issues are acceptable**: Null values for unused fields or unused `range` keys (like `gt: null`, `lt: null` when only `gte` and `lte` are used) are acceptable if the filter logic is correct.
- **Contract Renewal Queries**: For queries about "contracts up for renewal" or "contracts being renewed this month", using `契約終了日_contract_end_date` (contract end date) is CORRECT and ACCEPTABLE. In contract management, renewals typically occur when contracts are ending, so filtering by contract end date to find contracts up for renewal is a valid interpretation. DO NOT reject filters that use `契約終了日_contract_end_date` for renewal-related queries.

## Original Query
{query}

## Generated Filter
{filter_json}

## Previous Reasoning (if this is a retry)
{previous_reasoning}

## Previous Validation Feedback (if this is a retry)
{previous_feedback}

Please validate the filter and provide feedback. Only mark as incorrect if there are critical structural or logical errors. Cosmetic issues like null values for unused fields should not cause rejection if the logic is correct.
"""
