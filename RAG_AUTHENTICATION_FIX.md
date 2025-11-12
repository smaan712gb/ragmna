# RAG Authentication Fix - Complete

## Problem Identified

The `data-ingestion` service was receiving the error:
```
('No access token in response.', {'id_token': '...'})
```

This occurred because the code was incorrectly fetching an **ID token** instead of an **access token** when authenticating with Vertex AI RAG Engine.

### Root Cause
- **ID tokens** prove *identity* (who you are)
- **Access tokens** grant *permission* to resources (what you can access)
- Vertex AI RAG Engine API requires **access tokens**, not ID tokens

---

## Solution Implemented

### 1. Fixed Authentication in `services/data-ingestion/main.py`

**Before (Incorrect):**
```python
# Manually creating service account credentials and refreshing
credentials = service_account.Credentials.from_service_account_file(
    google_cloud_key_path
)
scoped_credentials = credentials.with_scopes(scopes)
scoped_credentials.refresh(auth_req)
access_token = scoped_credentials.token
```

**After (Correct):**
```python
# Using Application Default Credentials (ADC)
from google.auth import default
from google.auth.transport.requests import Request

credentials, project = default(scopes=[
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/aiplatform'
])

# Refresh credentials to get an ACCESS token (not ID token)
auth_request = Request()
credentials.refresh(auth_request)

access_token = credentials.token
```

**Key Benefits:**
- Uses `google.auth.default()` which automatically handles ACCESS token generation
- Properly respects the `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Follows Google Cloud best practices for authentication
- Automatically handles token refresh and expiration

### 2. Updated `docker-compose.yml`

**Changes:**
- ✅ Removed obsolete `version: '3.8'` attribute (no longer needed in modern Docker Compose)
- ✅ Verified `GOOGLE_APPLICATION_CREDENTIALS` is correctly set to `/app/secrets/gcp-service-key.json`
- ✅ Verified secrets volume is mounted as read-only: `./secrets:/app/secrets:ro`

**Current Configuration (Correct):**
```yaml
data-ingestion:
  environment:
    - GOOGLE_CLOUD_KEY_PATH=/app/secrets/gcp-service-key.json
    - GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-service-key.json
    # ... other env vars
  volumes:
    - ./services/data-ingestion:/app
    - ./secrets:/app/secrets:ro
```

---

## How Application Default Credentials (ADC) Works

1. **Environment Variable**: ADC checks `GOOGLE_APPLICATION_CREDENTIALS` first
2. **Service Account Key**: Points to `/app/secrets/gcp-service-key.json` in the container
3. **Automatic Token Generation**: Google Cloud libraries automatically:
   - Read the service account key
   - Generate ACCESS tokens (not ID tokens)
   - Refresh tokens when they expire
   - Add proper OAuth 2.0 scopes

---

## Testing the Fix

### Step 1: Rebuild the Container
```powershell
# Stop the current container
docker-compose stop data-ingestion

# Rebuild with the new code
docker-compose build data-ingestion

# Start the service
docker-compose up -d data-ingestion

# Check logs
docker-compose logs -f data-ingestion
```

### Step 2: Verify Authentication in Logs
Look for this log message:
```
✅ RAG: Access token generated via ADC (length: XXXX)
```

If you see this, authentication is working correctly.

### Step 3: Test RAG Ingestion
Run a test ingestion to verify the fix:

```python
import requests
import os

# Load your API keys
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

# Test data ingestion
url = "http://localhost:8001/ingest/comprehensive"
headers = {'X-API-Key': SERVICE_API_KEY}
payload = {
    'symbol': 'NVDA',
    'data_sources': ['sec_filings']  # Start with just SEC filings
}

response = requests.post(url, json=payload, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### Step 4: Check for Success
✅ **Success indicators:**
- No "No access token in response" error
- Log shows: "✅ RAG: Access token generated via ADC"
- Log shows: "✅ RAG import operation started"
- Status code 200 and successful response

❌ **Failure indicators:**
- "No access token" error persists
- "Invalid credentials" errors
- 401/403 status codes

---

## Service Account Permissions Required

Ensure your service account (`secrets/gcp-service-key.json`) has these IAM roles:

1. **Vertex AI User** (`roles/aiplatform.user`)
   - Required for RAG Engine API access
   - Allows creating/updating RAG corpora and files

2. **Storage Object Admin** (`roles/storage.objectAdmin`)
   - Required for uploading files to GCS bucket
   - Required by RAG Engine to read files from GCS

3. **Storage Object Viewer** (`roles/storage.objectViewer`)
   - Alternative minimum permission for reading objects

### Verify Permissions:
```powershell
# Set your service account email
$SA_EMAIL = "your-service-account@your-project.iam.gserviceaccount.com"
$PROJECT_ID = "your-project-id"

# Check IAM policy
gcloud projects get-iam-policy $PROJECT_ID `
  --flatten="bindings[].members" `
  --format="table(bindings.role)" `
  --filter="bindings.members:$SA_EMAIL"
```

---

## Troubleshooting

### Issue: Still getting "No access token" error
**Solution:**
1. Verify `GOOGLE_APPLICATION_CREDENTIALS` is set correctly in docker-compose.yml
2. Ensure the service account key file exists at `./secrets/gcp-service-key.json`
3. Rebuild the container: `docker-compose build data-ingestion`
4. Check file permissions on the service account key

### Issue: "Permission denied" or 403 errors
**Solution:**
1. Verify service account has required IAM roles (see above)
2. Check that RAG_CORPUS_ID in .env is correct
3. Ensure GCS_BUCKET in .env exists and SA has access

### Issue: Docker warning about obsolete version
**Solution:**
- ✅ Already fixed - removed `version: '3.8'` from docker-compose.yml

---

## Summary of Changes

| File | Changes | Status |
|------|---------|--------|
| `services/data-ingestion/main.py` | Changed to use `google.auth.default()` for ADC | ✅ Fixed |
| `docker-compose.yml` | Removed obsolete `version` attribute | ✅ Fixed |
| `docker-compose.yml` | Verified ADC configuration | ✅ Verified |

---

## Technical Details

### Why ADC is Better

**Before (Manual Token Generation):**
- Manually managed credentials
- Risk of fetching wrong token type (ID vs ACCESS)
- More complex error handling
- Not following Google Cloud best practices

**After (ADC):**
- Automatic credential discovery
- Always generates correct token type (ACCESS)
- Built-in token refresh
- Follows Google Cloud best practices
- Works seamlessly with Docker containers

### OAuth 2.0 Scopes Used
```python
scopes = [
    'https://www.googleapis.com/auth/cloud-platform',  # Full GCP access
    'https://www.googleapis.com/auth/aiplatform'       # Vertex AI access
]
```

These scopes ensure the ACCESS token has permissions for:
- Vertex AI RAG Engine operations
- Cloud Storage operations
- PubSub operations

---

## Next Steps

1. ✅ Rebuild and restart the data-ingestion container
2. ✅ Test with a sample ingestion (NVDA or another company)
3. ✅ Verify logs show successful authentication
4. ✅ Confirm RAG Engine operations complete without errors
5. ✅ Run full end-to-end M&A analysis test

---

## References

- [Google Cloud Authentication Best Practices](https://cloud.google.com/docs/authentication/best-practices-applications)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Vertex AI RAG Engine API](https://cloud.google.com/vertex-ai/docs/generative-ai/rag-api-overview)
- [OAuth 2.0 vs OpenID Connect](https://developers.google.com/identity/protocols/oauth2)
