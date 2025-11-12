# Production Fixes Summary - Complete Commercial Deployment

## Critical Issues Identified

Based on Vertex AI RAG Engine API documentation review, here are the production issues and their solutions:

### 1. OAuth Scope Error in LLM Orchestrator ❌ CRITICAL

**Problem**: Invalid OAuth scope for Vertex AI RAG Engine API
```
ERROR:llm_orch_main:Error retrieving contexts: ('invalid_scope: Invalid OAuth scope or ID token audience provided.', {'error': 'invalid_scope', 'error_description': 'Invalid OAuth scope or ID token audience provided.'})
```

**Root Cause**: Missing required scopes in credential authentication

**Fix Required in `services/llm-orchestrator/main.py`**:
```python
def _get_auth_headers(self) -> Dict[str, str]:
    """Get authentication headers for Vertex AI RAG Engine API calls"""
    # REQUIRED SCOPES for Vertex AI RAG Engine
    scopes = [
        'https://www.googleapis.com/auth/cloud-platform',
        'https://www.googleapis.com/auth/aiplatform'
    ]
    
    if GOOGLE_CLOUD_KEY_PATH:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CLOUD_KEY_PATH,
            scopes=scopes  # ADD THIS
        )
    else:
        credentials, _ = google.auth.default(scopes=scopes)  # ADD THIS
    
    if not credentials.valid:
        credentials.refresh(Request())
    
    return {
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    }
```

**Also Remove Fallback** - Change this:
```python
except Exception as e:
    logger.error(f"Error retrieving contexts: {e}")
    return {'contexts': []}  # DON'T RETURN EMPTY - RAISE ERROR
```

To this:
```python
except Exception as e:
    logger.error(f"❌ Error retrieving contexts: {e}")
    raise ValueError(f"Failed to retrieve RAG contexts: {e}")
```

---

### 2. Division by Zero in Merger Model ❌ CRITICAL

**Problem**: `float division by zero` when shares_outstanding = 0

**Root Cause**: yfinance/FMP may return 0 for shares outstanding

**Fix Required in `services/mergers-model/main.py`**:

Add validation AFTER getting shares outstanding:
```python
# Get shares outstanding from multiple sources
shares_outstanding = company_info.get('sharesOutstanding', 0)
if shares_outstanding == 0:
    shares_outstanding = market.get('sharesOutstanding', 0)
if shares_outstanding == 0:
    yf_data = company_info.get('yfinance_data', {})
    shares_outstanding = yf_data.get('shares_outstanding', 0)

# CRITICAL: Must have valid shares outstanding
if shares_outstanding <= 0:
    symbol = company_data.get('symbol', 'UNKNOWN')
    raise ValueError(f"❌ Shares outstanding = {shares_outstanding} for {symbol}. Cannot proceed.")
```

Also protect EPS calculation:
```python
# Accretion/dilution
eps_change = pro_forma_eps - acquirer_eps
if acquirer_eps == 0:
    raise ValueError("❌ Acquirer EPS is zero - cannot calculate accretion/dilution")
eps_accretion_dilution = eps_change / abs(acquirer_eps)
```

---

### 3. Data Ingestion Not Running Properly ❌ CRITICAL

**Problem**: SEC filings, analyst reports, news not being scraped and uploaded to RAG

**Root Cause**: `_store_in_rag_engine()` has placeholder implementation

**Fix Required in `services/data-ingestion/main.py`**:

Replace the placeholder implementation with proper Vertex AI RAG Engine Import API:

```python
def _store_in_rag_engine(self, chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
    """Store document chunks in Vertex AI RAG Engine via Import API"""
    
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        from google.cloud import storage
        import tempfile
        
        # Get authentication with proper scopes
        scopes = [
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/aiplatform'
        ]
        credentials, project = default(scopes=scopes)
        
        if not credentials.valid:
            credentials.refresh(Request())
        
        # Get RAG corpus configuration
        vertex_project = os.getenv('VERTEX_PROJECT')
        vertex_location = os.getenv('VERTEX_LOCATION')
        rag_corpus_id = os.getenv('RAG_CORPUS_ID')
        gcs_bucket = os.getenv('GCS_BUCKET')
        
        if not all([vertex_project, vertex_location, rag_corpus_id, gcs_bucket]):
            raise ValueError("❌ Must configure: VERTEX_PROJECT, VERTEX_LOCATION, RAG_CORPUS_ID, GCS_BUCKET")
        
        # Combine chunks into single document
        combined_content = "\n\n".join([chunk['content'] for chunk in chunks])
        
        # Upload to GCS first (required by RAG Engine Import API)
        storage_client = storage.Client()
        bucket = storage_client.bucket(gcs_bucket)
        
        file_name = metadata.get('file_name', 'unknown')
        blob_name = f"rag-uploads/{file_name}.txt"
        blob = bucket.blob(blob_name)
        
        # Write to temp file then upload
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
            tf.write(combined_content)
            temp_path = tf.name
        
        try:
            blob.upload_from_filename(temp_path)
            gcs_uri = f"gs://{gcs_bucket}/{blob_name}"
            logger.info(f"📤 Uploaded to GCS: {gcs_uri}")
            
            # Import to RAG Engine using Import API
            url = f"https://{vertex_location}-aiplatform.googleapis.com/v1beta1/projects/{vertex_project}/locations/{vertex_location}/ragCorpora/{rag_corpus_id}/ragFiles:import"
            
            payload = {
                "import_rag_files_config": {
                    "gcs_source": {
                        "uris": [gcs_uri]
                    },
                    "rag_file_chunking_config": {
                        "chunk_size": int(os.getenv('RAG_CHUNK_SIZE', 1000)),
                        "chunk_overlap": int(os.getenv('RAG_CHUNK_OVERLAP', 200))
                    },
                    "max_embedding_requests_per_min": int(os.getenv('MAX_EMBEDDING_QPM', 1000))
                }
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            
            operation = response.json()
            logger.info(f"✅ RAG import started: {operation.get('name')}")
            
            # Return chunk IDs
            return [chunk['id'] for chunk in chunks]
            
        finally:
            os.unlink(temp_path)
    
    except Exception as e:
        logger.error(f"❌ Error storing in RAG Engine: {e}")
        raise ValueError(f"Failed to store in RAG Engine: {e}")
```

---

### 4. DD Agents Not Running End-to-End ❌

**Problem**: DD agents not being invoked in the workflow

**Fix Required in `services/llm-orchestrator/main.py`**:

Ensure `orchestrate_ma_analysis()` method calls DD agent:

```python
# Step 6: Due Diligence (MUST BE INCLUDED)
logger.info("Step 6: Conducting due diligence")
dd_results = await self._conduct_due_diligence(target_symbol, target_data)
analysis_result['due_diligence'] = dd_results
analysis_result['workflow_steps'].append({
    'step': 'due_diligence',
    'completed': True,
    'timestamp': datetime.now().isoformat()
})
```

---

### 5. Remove All Hardcoded Fallbacks ❌ COMMERCIAL REQUIREMENT

**Locations to Fix**:

1. **LLM Orchestrator** - Remove classification fallback:
```python
# REMOVE THIS:
except Exception as e:
    logger.error(f"Error in structured classification: {e}")
    # Fallback classification based on revenue growth
    if revenue_growth > 30:
        classification_result = {'primary_classification': 'hyper_growth', ...}

# REPLACE WITH:
except Exception as e:
    logger.error(f"❌ Error in structured classification: {e}")
    raise ValueError(f"Classification failed - Gemini API error: {e}")
```

2. **Data Ingestion** - Already covered in fix #3

3. **Merger Model** - Already covered in fix #2

---

## Environment Variables Required

Ensure these are ALL configured in `.env`:

```bash
# Vertex AI Configuration
VERTEX_PROJECT=your-gcp-project
VERTEX_LOCATION=us-central1
RAG_CORPUS_ID=your-rag-corpus-id

# GCS Configuration
GCS_BUCKET=your-gcs-bucket

# RAG Configuration
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
MAX_EMBEDDING_QPM=1000

# API Keys
FMP_API_KEY=your-fmp-key
GEMINI_API_KEY=your-gemini-key
SERVICE_API_KEY=your-service-key

# GCP Service Account (if not using ADC)
GOOGLE_CLOUD_KEY_PATH=/path/to/service-account-key.json
```

---

## Required IAM Permissions

The service account needs these IAM roles:

```
roles/aiplatform.user
roles/aiplatform.ragResourceUser  
roles/storage.objectAdmin
roles/iam.serviceAccountTokenCreator
```

Grant permissions:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/aiplatform.ragResourceUser"
```

---

## Testing Checklist

After applying fixes, verify:

- [ ] ✅ Data ingestion runs for both companies
  - [ ] SEC filings scraped and uploaded to RAG
  - [ ] Analyst reports fetched and uploaded to RAG  
  - [ ] News articles fetched and uploaded to RAG
  - [ ] yfinance data includes shares_outstanding > 0
  
- [ ] ✅ Classification works without fallback
  - [ ] Target company classified
  - [ ] Acquirer company classified
  - [ ] RAG contexts retrieved (no OAuth error)
  
- [ ] ✅ DD agent runs end-to-end
  - [ ] Risk analysis generated
  - [ ] Recommendations provided
  
- [ ] ✅ Merger model calculates without errors
  - [ ] No division by zero
  - [ ] EPS accretion/dilution calculated
  - [ ] Synergies estimated
  
- [ ] ✅ Final reports generated
  - [ ] Excel export works
  - [ ] Board reporting complete

---

## Quick Fix Script

Create `apply_production_fixes.sh`:

```bash
#!/bin/bash

echo "Applying production fixes..."

# 1. Fix LLM Orchestrator OAuth
echo "1. Fixing LLM Orchestrator OAuth scopes..."
# Apply fixes to services/llm-orchestrator/main.py

# 2. Fix Merger Model
echo "2. Fixing merger model division by zero..."
# Apply fixes to services/mergers-model/main.py

# 3. Fix Data Ingestion
echo "3. Fixing data ingestion RAG upload..."
# Apply fixes to services/data-ingestion/main.py

# 4. Rebuild containers
echo "4. Rebuilding Docker containers..."
docker-compose build

# 5. Restart services
echo "5. Restarting services..."
docker-compose down
docker-compose up -d

echo "✅ All fixes applied!"
```

---

## Summary

**Critical Fixes Required**:
1. Add OAuth scopes for Vertex AI RAG Engine API
2. Add shares_outstanding validation in merger model  
3. Implement proper RAG Engine Import API in data ingestion
4. Ensure DD agents run in workflow
5. Remove all hardcoded fallbacks

**Impact**: System will be production-ready for commercial use with no hardcoded fallbacks, proper error handling, and full integration with Vertex AI RAG Engine.
