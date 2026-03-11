# Fuzzy Company Name Matching - Deployment Guide

## Pre-Deployment Checklist

### 1. Install Dependencies

```bash
# Install rapidfuzz and sync all dependencies
uv sync
```

Verify installation:
```bash
python -c "import rapidfuzz; print(f'rapidfuzz version: {rapidfuzz.__version__}')"
```

Expected output: `rapidfuzz version: 3.10.0` (or higher)

### 2. Run Tests (Optional but Recommended)

```bash
# Run the fuzzy matching test suite
python -m app.services.chatbot.tools.metadata_search.test_fuzzy_matching
```

This will test:
- ✅ Company name extraction from queries
- ✅ Fuzzy matching with various inputs
- ✅ Company name normalization
- ✅ Full integration

**Note**: This requires OpenAI API key to be configured for LLM-based extraction.

### 3. Verify No Breaking Changes

The implementation is **backward compatible**. No changes to:
- API endpoints
- Request/response formats
- Database schema
- Qdrant configuration

## Deployment Steps

### Step 1: Deploy Code

Deploy the updated codebase with the new files:
- `app/services/chatbot/tools/metadata_search/company_name_cache.py`
- `app/services/chatbot/tools/metadata_search/company_name_extractor.py`
- `app/services/chatbot/tools/metadata_search/fuzzy_company_matcher.py`
- Modified: `app/services/chatbot/tools/metadata_search/text_to_qdrant_filters.py`
- Modified: `pyproject.toml`

### Step 2: Restart Services

```bash
# Restart the application
# The exact command depends on your deployment setup

# Example for Docker:
docker-compose restart conpass-agent-backend

# Example for systemd:
sudo systemctl restart conpass-agent-backend

# Example for local development:
uvicorn app.main:app --reload
```

### Step 3: Warm Up Cache (Optional)

The first query per directory will be slower (~1-2 seconds) as it fetches and caches company names. You can warm up the cache:

```python
# Run this after deployment to pre-populate cache
import asyncio
from app.services.chatbot.tools.metadata_search.company_name_cache import get_company_names

async def warmup():
    # Replace with your actual directory IDs
    directory_ids = [1, 2, 3, 4, 5]
    companies = await get_company_names(directory_ids)
    print(f"Cache warmed up with {len(companies)} companies")

asyncio.run(warmup())
```

### Step 4: Monitor Initial Performance

Watch logs for:
```
INFO - Fetching company names from Qdrant for directory_ids: [...]
INFO - Fetched X unique company names from Qdrant
INFO - Using cached company names (cache age: ...)
INFO - Fuzzy matched 'ABC Corp' to: ['ABC Corporation', 'ABC Corp Ltd']
```

## Configuration (Optional)

### Adjust Fuzzy Matching Threshold

Edit `app/services/chatbot/tools/metadata_search/fuzzy_company_matcher.py`:

```python
# Default: 75% similarity
DEFAULT_THRESHOLD = 75  # Increase for stricter matching, decrease for more lenient

# Examples:
# 90 = Very strict (only minor typos)
# 75 = Balanced (default)
# 60 = Lenient (more variations)
```

### Adjust Cache TTL

Edit `app/services/chatbot/tools/metadata_search/company_name_cache.py`:

```python
# Default: 24 hours
CACHE_TTL_HOURS = 24  # Increase for longer cache, decrease for fresher data
```

### Adjust Max Matches

Edit `app/services/chatbot/tools/metadata_search/fuzzy_company_matcher.py`:

```python
# Default: 10 matches per query
MAX_MATCHES = 10  # Increase to return more matches, decrease for fewer
```

## Monitoring

### Key Metrics to Track

1. **Cache Hit Rate**
   - Look for: `"Using cached company names"` in logs
   - Target: > 95% after initial warmup

2. **Fuzzy Match Success Rate**
   - Look for: `"Fuzzy matched 'X' to: [...]"` in logs
   - Track: % of queries with successful matches

3. **Performance**
   - First query per directory: ~1-2 seconds (cache miss)
   - Subsequent queries: ~10-50ms (cache hit)

4. **Match Quality**
   - Monitor user feedback
   - Check for false positives/negatives

### Log Examples

**Successful fuzzy match:**
```
INFO - Extracted company names from query: ['ABC Corp']
INFO - Using cached company names (cache age: 0:15:23)
INFO - Fuzzy matched 'ABC Corp' to: ['ABC Corporation', 'ABC Corp Ltd']
INFO - Found 2 matches for 'ABC Corp': ['ABC Corporation', 'ABC Corp Ltd']
```

**No match found:**
```
INFO - Extracted company names from query: ['NonExistent Company']
INFO - Using cached company names (cache age: 0:15:23)
WARNING - No fuzzy matches found for 'NonExistent Company' (threshold=75, available companies=1523)
```

**Cache miss (first query):**
```
INFO - Company name cache is invalid or force refresh requested, fetching from Qdrant
INFO - Fetching company names from Qdrant for directory_ids: [1, 2, 3]
INFO - Fetched 1523 unique company names from Qdrant
```

## Rollback Plan

If issues arise, rollback is simple:

### Option 1: Quick Rollback (Remove Fuzzy Matching)

Comment out the fuzzy matching call in `text_to_qdrant_filters.py`:

```python
async def convert_query_to_qdrant_filter(query, directory_ids):
    # Temporarily disable fuzzy matching
    # enhanced_query, company_matches = await _apply_fuzzy_company_matching(query, directory_ids)
    company_matches = None  # Disable fuzzy matching
    
    # Rest of the code...
```

### Option 2: Full Rollback (Revert Code)

```bash
# Revert to previous version
git revert <commit-hash>

# Reinstall dependencies
uv sync

# Restart services
docker-compose restart conpass-agent-backend
```

## Troubleshooting

### Issue: "Module 'rapidfuzz' not found"

**Solution:**
```bash
uv sync
# or
pip install rapidfuzz>=3.10.0
```

### Issue: Cache not being used (every query fetches from Qdrant)

**Check:**
1. Look for `"Company name cache is invalid"` in logs
2. Verify cache is not being invalidated unexpectedly

**Solution:**
```python
# Check cache status
from app.services.chatbot.tools.metadata_search.company_name_cache import get_cache_info
info = get_cache_info()
print(info)
```

### Issue: Too many false positive matches

**Solution:**
Increase threshold in `fuzzy_company_matcher.py`:
```python
DEFAULT_THRESHOLD = 85  # Increase from 75 to 85
```

### Issue: No matches found for valid company names

**Solution:**
Decrease threshold in `fuzzy_company_matcher.py`:
```python
DEFAULT_THRESHOLD = 65  # Decrease from 75 to 65
```

Or invalidate cache:
```python
from app.services.chatbot.tools.metadata_search.company_name_cache import invalidate_cache
await invalidate_cache()
```

## Testing in Production

### Test Queries

Try these queries after deployment:

1. **Abbreviation test:**
   ```
   "Show me contracts with ABC Corp"
   ```
   Should match: "ABC Corporation", "ABC Corp Ltd", etc.

2. **Typo test:**
   ```
   "Find contracts for Microsft"
   ```
   Should match: "Microsoft Corporation"

3. **Partial match test:**
   ```
   "Contracts with Google"
   ```
   Should match: "Google LLC", "Google Inc", etc.

4. **Japanese test:**
   ```
   "株式会社ABCの契約"
   ```
   Should match: "株式会社ABC"

5. **Multiple companies test:**
   ```
   "Show contracts with ABC Corp or XYZ Ltd"
   ```
   Should match both companies

### Verify Logs

After each test query, check logs for:
- ✅ Company names extracted correctly
- ✅ Cache being used (after first query)
- ✅ Fuzzy matches found
- ✅ Filter generated with matched names

## Performance Optimization

### If Cache Misses Are Frequent

**Increase cache TTL:**
```python
CACHE_TTL_HOURS = 48  # Increase from 24 to 48 hours
```

### If Memory Usage Is High

**Reduce cache TTL:**
```python
CACHE_TTL_HOURS = 12  # Decrease from 24 to 12 hours
```

Or implement cache size limits:
```python
MAX_CACHE_SIZE = 50000  # Limit to 50k company names
```

### If Fuzzy Matching Is Slow

**Reduce max matches:**
```python
MAX_MATCHES = 5  # Decrease from 10 to 5
```

Or increase threshold:
```python
DEFAULT_THRESHOLD = 85  # Stricter matching = fewer comparisons
```

## Success Criteria

Deployment is successful when:

1. ✅ All tests pass
2. ✅ No errors in logs
3. ✅ Cache hit rate > 95% after warmup
4. ✅ Fuzzy matching works for test queries
5. ✅ Response times < 100ms (cached)
6. ✅ No user complaints about search quality

## Post-Deployment

### Week 1: Monitor Closely

- Check logs daily for errors
- Monitor cache hit rate
- Track fuzzy match success rate
- Gather user feedback

### Week 2-4: Optimize

- Adjust threshold based on feedback
- Fine-tune cache TTL
- Optimize performance if needed

### Month 2+: Maintain

- Monthly review of match quality
- Update threshold if needed
- Monitor for new edge cases

## Support

If issues arise:

1. Check logs for errors
2. Review this troubleshooting guide
3. Check `docs/FUZZY_COMPANY_MATCHING.md` for details
4. Contact development team

---

**Deployment Status**: ✅ Ready for Production

The implementation is stable, tested, and ready to deploy!

