# v3 System Prompt Fix: Excessive Questioning Issue

**Date**: December 19, 2024  
**Issue**: Agent asking too many follow-up questions without taking action
**Status**: ✅ FIXED

## Problem Description

Users reported that the v3 agent was constantly asking follow-up questions instead of taking action. Every user query resulted in the agent requesting clarification about scope, dates, companies, or other details, rather than making reasonable inferences and proceeding with tool usage.

## Root Cause Analysis

Upon investigation, I discovered that **v3 prompts removed critical instructions from v2** that prevented excessive questioning:

### What v2 Had (but v3 Lost):

**v2 English** - Lines 154-171:
```
## 【Scope Estimation Rules】

1. Automatic scope estimation from user query:
   * Company names, business units
   * Contract types (NDA, License, etc.)
   * Date ranges
   * Partner names, countries
     → If determinable, use directly.

2. Ask only once if ambiguous:
   "Which scope should I search?
   1. Filter by company/date
   2. Specify custom conditions
   3. Search all contracts and documents"

3. Do not ask if conditions are clear.
```

**v2 Japanese** - Lines 154-176: Similar explicit scope estimation rules

### What v3 Had (Insufficient):

**v3 English** - Line 316 (buried in Response Style):
```
- **No unnecessary questions**: Infer what the user wants and proceed
```

**v3 Japanese** - Line 357 (buried in Response Style):
```
- **不要な質問をしない**: 意図を推測して進める
```

This was just a brief bullet point, easily overlooked by the LLM, resulting in the agent defaulting to asking clarifying questions.

## Solution Implemented

### 1. Added Prominent "DO NOT ASK UNNECESSARY QUESTIONS" Section

Created a new **highly visible section** after the tool selection strategy and **before** the tool descriptions, with:

- ❌ Clear examples of BAD behavior (asking unnecessary questions)
- ✓ Clear examples of GOOD behavior (taking immediate action)
- Explicit rules for when to ask (RARELY) vs when to act (ALWAYS)
- Strong emphasis with formatting (**bold**, CAPS, emojis)

### 2. Strengthened Response Style Directive

Updated the Response Style bullet point from a weak suggestion to a strong command:

**Before:**
```
- **No unnecessary questions**: Infer what the user wants and proceed
```

**After:**
```
- **NO UNNECESSARY QUESTIONS - CRITICAL**: **NEVER ask clarifying questions unless 
  the request is completely impossible to interpret. Always infer what the user 
  wants and take immediate action.** Use tools first, present results. Do NOT ask 
  about scope, dates, companies, or other details - just make reasonable inferences 
  and proceed.
```

## Files Modified

1. ✅ `app/services/chatbot/prompts/system_prompts_en_v3.py` - English version
   - Main SYSTEM_PROMPT (line ~118)
   - CONPASS_ONLY_SYSTEM_PROMPT (line ~530)

2. ✅ `app/services/chatbot/prompts/system_prompts_jp_v3.py` - Japanese version
   - Main SYSTEM_PROMPT (line ~93)
   - CONPASS_ONLY_SYSTEM_PROMPT (line ~537)

## New Section Added (Example from English version)

```markdown
## CRITICAL: DO NOT ASK UNNECESSARY QUESTIONS

**You must take action immediately without asking follow-up questions unless the 
request is truly ambiguous.**

### When to Ask Questions (RARELY):
- **ONLY** when the user's question is completely unclear and cannot be interpreted 
  in any reasonable way
- **ONLY** when there are multiple equally valid interpretations and no context to 
  guide you
- **NEVER** ask about scope, company names, date ranges, or other details you can 
  infer from context

### When to Act Immediately (ALWAYS):
- User provides ANY specific information (company names, dates, contract IDs, topics)
- User's intent is clear even if some details are vague
- You can make a reasonable inference from context
- The query is actionable with available tools

### Examples:

❌ **BAD - Unnecessary questions:**
- User: "Show me contracts ending soon"
- Agent: "What date range would you like me to search?"
- **WRONG!** Just interpret "soon" as next 30-60 days and proceed with search

✓ **GOOD - Take action immediately:**
- User: "Show me contracts ending soon"
- Agent: *Immediately searches for contracts ending in next 60 days*

❌ **BAD - Asking for clarification when intent is clear:**
- User: "Find contracts with ABC Corp"
- Agent: "Would you like me to search by company A or company B?"
- **WRONG!** Just search both fields and show results

✓ **GOOD - Take action with reasonable interpretation:**
- User: "Find contracts with ABC Corp"  
- Agent: *Immediately searches for ABC Corp in any company field*

**REMEMBER: Action over questions. The user wants results, not conversations. Use 
tools proactively and present findings. Only ask if truly impossible to proceed.**
```

## Expected Behavior After Fix

### Before (Problematic):
```
User: "Show me contracts ending soon"
Agent: "Could you please clarify the date range? Do you want contracts ending in 
       the next 30 days, 60 days, or 90 days?"
```

### After (Correct):
```
User: "Show me contracts ending soon"
Agent: *Immediately calls metadata_search with date filter for next 60 days*
       *Displays table with results*
```

## Testing Recommendations

Test the following scenarios to verify the fix:

1. **Vague date queries**: "Show me contracts ending soon"
   - ✅ Should immediately search with reasonable date interpretation (30-60 days)
   - ❌ Should NOT ask for specific date ranges

2. **Company name queries**: "Find contracts with ABC Corp"
   - ✅ Should search all company fields (company_a, company_b, etc.)
   - ❌ Should NOT ask which company field to search

3. **General topic queries**: "Show me contracts about SLA"
   - ✅ Should immediately use semantic_search
   - ❌ Should NOT ask for clarification about what "about" means

4. **Ambiguous but actionable**: "What contracts do we have?"
   - ✅ Should list all contracts with pagination
   - ❌ Should NOT ask for filtering criteria

## Notes

- The fix maintains the same tool selection logic and other v3 improvements
- Only the questioning behavior has been addressed
- The agent should now be more action-oriented and less conversational
- This brings back the best behavior from v2 while keeping v3's improvements

## Rollback Plan

If issues arise, the previous version can be restored from git history. The specific commit before these changes can be used to revert.

## Related Documentation

- v2 prompts: `app/services/chatbot/prompts/system_prompts_en_v2.py`
- v3 prompts: `app/services/chatbot/prompts/system_prompts_en_v3.py`
- System prompt updates log: `docs/SYSTEM_PROMPT_UPDATES.md`

