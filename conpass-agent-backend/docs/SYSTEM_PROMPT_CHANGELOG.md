# System Prompt Changelog

## Summary of All Updates

This document tracks all changes made to the ConPass AI Agent system prompts and tool configurations.

---

## Update 1: Tool Selection Priority & Markdown Formatting

**Date**: Initial update
**Issue**: Query engine tool always triggering first, inconsistent markdown formatting

### Changes Made:

1. **Tool Selection Priority**

   - Marked `metadata_search` as PRIMARY TOOL in both code and prompts
   - Marked `semantic_search` as CONTENT SEARCH ONLY with explicit warnings
   - Added decision tree in system prompts
   - Updated tool descriptions in code

2. **Markdown Formatting**
   - Added mandatory formatting rules section
   - Provided response templates for all tool outputs
   - Added complete formatted examples
   - Required markdown tables for all contract lists

---

## Update 2: Removed Proactive Suggestions & Fixed Tool Limits

**Date**: Second update
**Issue**: Agent suggesting unimplemented features, incorrect tool limits in documentation

### Changes Made:

1. **Removed Proactive Suggestions**

   - Added No proactive suggestions constraint
   - Removed PROACTIVE ASSISTANCE section
   - Replaced with RESPONSE GUIDELINES
   - Updated style from helpful to concise
   - Agent will NOT suggest:
     - Exports (CSV/PDF)
     - Calendar reminders
     - Additional analysis not requested
     - Features that may not be implemented

2. **Fixed Tool Limits**
   - Corrected risk_analysis_tool: 10 → **2 contracts max**
   - Verified read_contracts_tool: **4 contracts max** (was correct)
   - Updated all examples and documentation
   - Enhanced tool descriptions with correct limits

---

## Current Tool Limits

| Tool                | Max Items                                 | Enforced In Code             |
| ------------------- | ----------------------------------------- | ---------------------------- |
| metadata_search     | Unlimited (with optional limit parameter) | N/A                          |
| semantic_search         | N/A (retrieves top_k results)             | settings.TOP_K               |
| read_contracts_tool | **4 contracts**                           | MAX_CONTRACTS_TO_READ = 4    |
| risk_analysis_tool  | **2 contracts**                           | MAX_CONTRACTS_TO_ANALYZE = 2 |
| web_search_tool     | N/A (single query)                        | N/A                          |

---

## Files Modified (All Updates)

### System Prompts

- `docs/CONPASS_ONLY_SYSTEM_PROMPT.txt` - ConPass-only mode (2 tools)
- `docs/SYSTEM_PROMPT.txt` - General mode (5 tools)

### Tool Implementations

- `app/services/chatbot/tools/query_engine/query_engine_tool.py`
- `app/services/chatbot/tools/contract_fetcher/contract_fetcher_tool.py`
- `app/services/chatbot/tools/risk_analysis/risk_analysis_tool.py`
- `app/services/chatbot/tools/read_contracts/read_contracts_tool.py`

### Documentation

- `docs/SYSTEM_PROMPT_UPDATES.md` - Detailed update summary
- `docs/SYSTEM_PROMPT_CHANGELOG.md` - This file

---

## Key Behavioral Changes

### Before Updates:

- ❌ semantic_search triggered for contract search queries
- ❌ Inconsistent response formatting
- ❌ Agent suggested unimplemented features
- ❌ Documentation showed wrong limits (10 contracts for risk analysis)
- ❌ Agent asked follow-up questions about additional actions

### After Updates:

- ✅ metadata_search triggers first for finding contracts
- ✅ All contract lists in markdown tables
- ✅ Predictable response structure
- ✅ Agent answers only what is asked
- ✅ Correct tool limits (2 for risk, 4 for reading)
- ✅ No suggestions for unimplemented features
- ✅ No proactive follow-up questions

---

## Testing Checklist

### Tool Selection

- [ ] Find contracts by company name → metadata_search used
- [ ] Find contracts by date range → metadata_search used
- [ ] What does contract say about X → semantic_search used
- [ ] Read contract full text → read_contracts_tool used
- [ ] Analyze contract risks → risk_analysis_tool used
- [ ] Research external info → web_search_tool used

### Formatting

- [ ] Contract lists appear as markdown tables
- [ ] Headers used consistently (##, ###)
- [ ] Bold used for important info
- [ ] Sources clearly cited
- [ ] Risk analysis has structured sections

### Constraints

- [ ] Risk analysis limited to 2 contracts
- [ ] Reading limited to 4 contracts
- [ ] Agent does NOT suggest exports
- [ ] Agent does NOT suggest calendar reminders
- [ ] Agent does NOT ask Would you like me to...
- [ ] Agent does NOT suggest unimplemented features

---

## Rollback Instructions

If issues arise, revert these files to previous versions:

1. System prompts:

   - `docs/CONPASS_ONLY_SYSTEM_PROMPT.txt`
   - `docs/SYSTEM_PROMPT.txt`

2. Tool descriptions:
   - `app/services/chatbot/tools/query_engine/query_engine_tool.py`
   - `app/services/chatbot/tools/contract_fetcher/contract_fetcher_tool.py`
   - `app/services/chatbot/tools/risk_analysis/risk_analysis_tool.py`
   - `app/services/chatbot/tools/read_contracts/read_contracts_tool.py`

Note: Tool limits (MAX_CONTRACTS_TO_READ = 4, MAX_CONTRACTS_TO_ANALYZE = 2) are correct and should NOT be changed.

---

## Future Considerations

### If Adding New Features:

1. Update relevant tool descriptions
2. Update both system prompts
3. Add to response templates section
4. Update examples
5. Test tool selection logic
6. Update this changelog

### If Changing Tool Limits:

1. Update constants in tool files
2. Update both system prompts
3. Update all examples
4. Update tool descriptions
5. Test limit enforcement
6. Update documentation

---

## Notes

- System prompts use no double quotes (single quotes or plain text only)
- All responses must be in markdown
- Agent operates in two modes: CONPASS_ONLY (2 tools) and GENERAL (5 tools)
- Tool selection is hierarchical: metadata_search → other tools
- Risk analysis outputs are in Japanese
- All other outputs support both Japanese and English
