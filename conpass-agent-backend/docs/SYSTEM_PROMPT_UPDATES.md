# System Prompt Updates Summary

## Issues Fixed

### 1. Query Engine Tool Always Triggering First ❌ → ✅

**Problem**: The semantic_search tool was being selected by default even when users wanted to find/list contracts.

**Solution**: Multiple layers of fixes applied:

#### A. Tool Descriptions Updated

- **metadata_search**: Now marked as **PRIMARY TOOL - USE THIS FIRST**
- **semantic_search**: Now marked as **CONTENT SEARCH ONLY** with explicit DO NOT USE warnings
- Added clear decision-making criteria in tool descriptions

#### B. System Prompts Enhanced

Both CONPASS_ONLY_SYSTEM_PROMPT.txt and SYSTEM_PROMPT.txt now include:

**Tool Selection Priority (Step 1)**:

```
ALWAYS CHECK FIRST: Is the user asking to find, list, or identify contracts?
- YES → Use metadata_search FIRST
- NO → What type of query is it?
  - Ask about contract content/clauses → semantic_search
  - Read full contract text → read_contracts_tool
  - Analyze risks → risk_analysis_tool
  - Research external info → web_search_tool
```

**Clear Decision Tree**:

- Find/list/search contracts → **metadata_search**
- What does contract say about X → **semantic_search**
- Show me full text of contract → **read_contracts_tool**
- Analyze risks in contract → **risk_analysis_tool**
- Research external information → **web_search_tool**

#### C. Tool Code Updated

**query_engine_tool.py**:

- Changed vague description from: Use this tool to retrieve information about the text corpus from an index
- To explicit: Use this tool ONLY to search for specific information WITHIN contract content and text... DO NOT use this tool to find or list contracts by metadata

**contract_fetcher_tool.py**:

- Added: **PRIMARY TOOL for finding contracts** - Use this tool FIRST when the user wants to find, list, search, or identify contracts
- Added explicit When to use list
- Added DO NOT use semantic_search for finding contracts warning

---

### 2. Inconsistent Markdown Formatting ❌ → ✅

**Problem**: Responses were not consistently formatted in well-structured markdown, especially for contract lists.

**Solution**: Explicit formatting requirements and templates added:

#### A. Formatting Rules Section Added

```markdown
### Formatting Rules:

1. **Always use markdown tables** for contract lists and risk summaries
2. **Always use headers** (##, ###) to organize sections
3. **Always use bullet points** for lists and key points
4. **Always bold** important information (dates, risk levels, counts, warnings)
5. **Always cite sources** with clear references
6. **Always separate major sections** with horizontal rules (---) when appropriate
```

#### B. Response Templates Provided

**For Contract Lists** (metadata_search results):

```markdown
## Contracts Found

| Contract ID | Title             | Company A | Company B | Contract Date | End Date   | Auto-Renewal |
| ----------- | ----------------- | --------- | --------- | ------------- | ---------- | ------------ |
| 123         | Service Agreement | ABC Corp  | XYZ Ltd   | 2024-01-15    | 2025-01-31 | Yes          |

**Total contracts found: X**

### Key Findings

- [Important observation 1]
- [Important observation 2]
```

**For Risk Analysis Results**:

```markdown
## Risk Analysis Results

### Overall Assessment

- **Overall Risk Rating**: [Critical/High/Medium/Low]
- **Contracts Analyzed**: X

### Critical Risks

[Table with clause, risk type, likelihood, impact, recommendation]

### Next Steps

1. [Action 1]
2. [Action 2]
```

**For Content Queries** (semantic_search results):

```markdown
## Answer

[Direct answer to question]

### Key Points

- Point 1
- Point 2

### Sources

- Contract ID [X]: [Title]
```

#### C. Complete Example Interactions Added

Both system prompts now include full example responses showing:

- Exact markdown table format for contract lists
- Proper header hierarchy
- Use of bold for emphasis
- Source citations
- Section separators

---

## Files Modified

1. **docs/CONPASS_ONLY_SYSTEM_PROMPT.txt**

   - Added tool selection priority with decision tree
   - Added mandatory markdown formatting section
   - Added complete formatted examples
   - Marked metadata_search as PRIMARY TOOL
   - Marked semantic_search as CONTENT SEARCH ONLY

2. **docs/SYSTEM_PROMPT.txt**

   - Same updates as above
   - Extended examples for all 5 tools
   - Added risk analysis formatting templates
   - Added multi-tool workflow examples with formatting

3. **app/services/chatbot/tools/query_engine/query_engine_tool.py**

   - Updated tool description to be more restrictive
   - Added explicit DO NOT USE for finding contracts
   - Clarified it is for content search only

4. **app/services/chatbot/tools/contract_fetcher/contract_fetcher_tool.py**
   - Marked as PRIMARY TOOL
   - Added explicit when to use criteria
   - Added warning not to use semantic_search for finding contracts
   - Added note about markdown table formatting

---

## Expected Behavior Now

### When user asks: Find all contracts with ABC Corp

✅ **metadata_search** will be triggered first
✅ Results will be in markdown table format
✅ Summary will include total count and key findings

### When user asks: What does contract 1234 say about termination?

✅ **semantic_search** will be triggered (content question)
✅ Response will have structured sections with sources
✅ Clear markdown formatting with headers and bullets

### When user asks: Find all NDAs and analyze risks

✅ **metadata_search** triggered first (find contracts)
✅ **risk_analysis_tool** triggered second (analyze them)
✅ Both results formatted in predictable markdown structure

---

## Testing Recommendations

1. Test contract search queries:

   - Find contracts ending in 2025
   - Show me all NDAs
   - Which contracts have ABC Corp

2. Test content queries:

   - What does contract 1234 say about payment terms?
   - Explain the termination clause
   - What are the renewal conditions?

3. Test combined queries:

   - Find all contracts with XYZ and tell me about their terms
   - Show contracts expiring soon and analyze their risks

4. Verify markdown formatting:
   - All contract lists should be in tables
   - Headers should be used consistently
   - Bold should highlight important info
   - Sources should be clearly cited

---

## Additional Notes

- The system prompts now have **CRITICAL** warnings about formatting requirements
- Tool descriptions in code now align with system prompt instructions
- Multiple layers of guidance ensure correct tool selection
- Predictable structure makes responses easier to parse and display
- Examples show exact expected output format

---

## Success Criteria

✅ metadata_search is selected first for finding/listing contracts
✅ semantic_search is only used for content questions
✅ All contract lists appear as markdown tables
✅ All responses follow predictable structure
✅ Important information is properly emphasized with bold
✅ Sources are clearly cited in every response
✅ Agent does NOT suggest additional features, exports, or actions
✅ Agent respects correct tool limits (2 for risk analysis, 4 for reading)

---

## Update 2: Removed Proactive Suggestions & Fixed Tool Limits

### Issues Fixed

#### 1. Agent Making Unwanted Suggestions ❌ → ✅

**Problem**: Agent was suggesting features not implemented (exports, calendar reminders, analyzing 10 contracts, etc.)

**Solution**:

- Added **No proactive suggestions** constraint to both system prompts
- Removed PROACTIVE ASSISTANCE section
- Changed to RESPONSE GUIDELINES focused on answering only what is asked
- Updated SUCCESS CRITERIA to emphasize not suggesting unimplemented features
- Changed style from helpful to concise (no additional suggestions)

#### 2. Incorrect Tool Limits ❌ → ✅

**Problem**: System prompts and examples said risk analysis supports 10 contracts (actual limit: 2)

**Solution**:

- Fixed risk_analysis_tool limit: 10 → **2 contracts**
- Verified read_contracts_tool limit: **4 contracts** (correct)
- Updated all examples to show 2 contracts for risk analysis
- Updated tool descriptions in code to reflect correct limits

### Files Modified

1. **docs/CONPASS_ONLY_SYSTEM_PROMPT.txt**

   - Added constraint: No proactive suggestions
   - Changed style guideline from helpful to concise
   - Updated SUCCESS CRITERIA to forbid suggesting unimplemented features

2. **docs/SYSTEM_PROMPT.txt**

   - Fixed risk_analysis_tool: max 2 contracts (was 10)
   - Added constraint: No proactive suggestions with specific examples
   - Replaced PROACTIVE ASSISTANCE with RESPONSE GUIDELINES
   - Updated all examples to show 2 contracts max
   - Updated SUCCESS CRITERIA

3. **app/services/chatbot/tools/risk_analysis/risk_analysis_tool.py**

   - Enhanced description with clear when to use guidance
   - Shows MAX_CONTRACTS_TO_ANALYZE (2) in description
   - Added note about Japanese output and markdown formatting

4. **app/services/chatbot/tools/read_contracts/read_contracts_tool.py**
   - Enhanced description with clear when to use guidance
   - Shows MAX_CONTRACTS_TO_READ (4) in description
   - Added warning not to use for risk analysis

### Expected Behavior Now

**Agent will NOT suggest**:

- ❌ Would you like me to analyze risks?
- ❌ Export these results (CSV/PDF)?
- ❌ Add calendar reminders?
- ❌ Check specific contracts for deadlines?
- ❌ Any features not explicitly implemented

**Agent will correctly limit**:

- ✅ Risk analysis: max 2 contracts at a time
- ✅ Reading contracts: max 4 contracts at a time
- ✅ If user requests more, inform them of the limit

**Agent will**:

- ✅ Answer exactly what is asked
- ✅ State important findings found in data
- ✅ Not ask follow-up questions about additional actions
- ✅ Not suggest capabilities that may not exist
