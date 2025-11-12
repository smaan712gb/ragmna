# Production Issues Fix Plan

## Critical Issues Identified

1. **OAuth Scope Error in Classification** - Invalid OAuth scope for Vertex AI RAG
2. **Merger Model Division by Zero** - Shares outstanding = 0 causing crashes
3. **Data Ingestion Not Running** - Scraping, analyst reports, news not executing
4. **DD Agents Not Running End-to-End** - Workflow incomplete
5. **Hardcoded Fallbacks** - Must remove for commercial use

## Root Causes

### 1. OAuth Scope Error
- **Location**: `services/llm-orchestrator/main.py` - RAGManager._get_auth_headers()
- **Issue**: Credentials don't have correct scopes for Vertex AI RAG API
- **Fix**: Add proper scopes and use application default credentials with correct audience

### 2. Division by Zero in Merger Model
- **Location**: `services/mergers-model/main.py` - Multiple locations
- **Issue**: shares_outstanding = 0 from yfinance/FMP
- **Fix**: Ensure shares_outstanding is properly fetched and validated, raise error if missing

### 3. Data Ingestion Not Running
- **Location**: `services/data-ingestion/main.py`
- **Issue**: Methods exist but not being called in workflow
- **Fix**: Ensure orchestrator calls ingestion service properly

### 4. DD Agents Not Running
- **Location**: `services/dd-agent/main.py` not being invoked
- **Fix**: Add DD agent invocation to workflow

### 5. Hardcoded Fallbacks
- **Location**: Multiple services
- **Fix**: Remove fallbacks, raise errors for missing data

## Implementation Plan

1. Fix OAuth scopes in LLM orchestrator
2. Fix shares outstanding fetching and validation
3. Ensure data ingestion runs completely
4. Add DD agent to workflow
5. Remove all hardcoded fallbacks
6. Create comprehensive end-to-end test
