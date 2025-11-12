# RAG Engine Setup and Usage Guide

This guide provides production-ready automation for setting up and using Vertex AI RAG Engine with your M&A analysis system.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated (`gcloud auth login`)
3. **Service Account** with appropriate permissions (created automatically by setup script)
4. **GCS Bucket** for document storage (created automatically by setup script)

## Quick Start

### 1. Initial Setup

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Run the automated setup
./scripts/setup-rag.sh
```

This will:
- Enable required GCP APIs
- Create a service account with proper permissions
- Create a GCS bucket for documents
- Create a RAG corpus
- Generate configuration file (`rag-config.env`)

### 2. Upload Documents

Upload your M&A documents to the GCS bucket:

```bash
# Upload individual files
gsutil cp your-document.pdf gs://your-bucket/documents/

# Upload entire directories
gsutil -m cp -r ./documents/* gs://your-bucket/documents/
```

### 3. Ingest Documents

```bash
# Ingest all documents from GCS
./scripts/ingest-documents.sh
```

### 4. Configure Application

Update your application environment variables with the values from `rag-config.env`:

```bash
# Add to your environment or docker-compose.yml
VERTEX_PROJECT=your-project-id
VERTEX_LOCATION=us-central1
RAG_CORPUS_ID=your-corpus-id
GOOGLE_CLOUD_KEY_PATH=/path/to/service-account-key.json
```

## Manual Work Required

### In Google Cloud Console (One-time setup):

1. **Create Service Account Key** (if using key-based auth):
   - Go to IAM & Admin > Service Accounts
   - Find the `rag-service-account`
   - Create a JSON key
   - Store securely and reference in `GOOGLE_CLOUD_KEY_PATH`

2. **GCS Bucket Permissions**:
   - Ensure the service account has access to your bucket
   - Configure bucket lifecycle policies if needed

3. **API Quotas**:
   - Monitor Vertex AI API quotas
   - Request increases if processing large document volumes

## Automated Operations

### Using Bash Scripts

```bash
# List all corpora
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/us-central1/ragCorpora"

# Query the corpus
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "vertex_rag_store": {
      "rag_resources": {
        "rag_corpus": "projects/${PROJECT_ID}/locations/us-central1/ragCorpora/${CORPUS_ID}"
      }
    },
    "query": {
      "text": "What are the key risks in this acquisition?",
      "similarity_top_k": 5
    }
  }' \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/us-central1:retrieveContexts"
```

### Using Python Client

```bash
# Install dependencies
pip install google-cloud-aiplatform google-auth requests

# Create a new corpus
python scripts/rag-client.py --project ${PROJECT_ID} create-corpus --name "New Corpus" --description "Description"

# Import documents
python scripts/rag-client.py --project ${PROJECT_ID} --corpus ${CORPUS_ID} import-docs --gcs-uris "gs://bucket/documents/**"

# Query the corpus
python scripts/rag-client.py --project ${PROJECT_ID} --corpus ${CORPUS_ID} query --text "due diligence questions"

# Generate with RAG
python scripts/rag-client.py --project ${PROJECT_ID} --corpus ${CORPUS_ID} generate --prompt "Analyze this acquisition"

# Analyze M&A documents
python scripts/rag-client.py --project ${PROJECT_ID} --corpus ${CORPUS_ID} analyze-ma --symbol AAPL --content "document text here"
```

## Integration with LLM Orchestrator

The RAG functionality is automatically integrated into the M&A analysis workflow:

1. **Due Diligence Enhancement**: RAG provides contextual insights during document analysis
2. **Risk Assessment**: Historical data and similar transactions inform risk evaluation
3. **Valuation Context**: Market precedents and industry analysis enhance valuation models

### API Endpoints

The llm-orchestrator service exposes RAG-enhanced endpoints:

```bash
# Standard M&A analysis (now includes RAG)
curl -X POST http://localhost:8080/analysis/ma \
  -H "X-API-Key: your-key" \
  -d '{"target_symbol": "AAPL", "acquirer_symbol": "MSFT"}'
```

## Configuration Options

### Chunking Parameters
- `CHUNK_SIZE`: Tokens per chunk (default: 1000)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 200)

### Embedding Limits
- `EMBEDDING_QPM_RATE`: Max embedding requests per minute (default: 1000)

### Environment Variables
```bash
# Required
VERTEX_PROJECT=your-project-id
VERTEX_LOCATION=us-central1
RAG_CORPUS_ID=your-corpus-id

# Optional (for service account auth)
GOOGLE_CLOUD_KEY_PATH=/path/to/key.json

# Optional (for document processing)
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_QPM_RATE=1000
```

## Monitoring and Maintenance

### Health Checks
```bash
# Check corpus status
python scripts/rag-client.py --project ${PROJECT_ID} --corpus ${CORPUS_ID} list-corpora

# Monitor ingestion operations
# (Check GCP Console > Vertex AI > RAG Engine for operation status)
```

### Cost Optimization
- Use appropriate chunk sizes to balance retrieval quality and cost
- Monitor embedding API usage in GCP Console
- Set up budget alerts for Vertex AI spending

### Backup and Recovery
- Documents are stored in GCS (durable storage)
- Corpus metadata can be exported via API
- Service account keys should be rotated regularly

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure `gcloud auth login` is run
   - Check service account permissions
   - Verify project ID is correct

2. **Document Ingestion Failures**
   - Check GCS bucket permissions
   - Verify document formats are supported
   - Monitor API quotas

3. **Query Performance**
   - Adjust chunk size and overlap
   - Review vector distance thresholds
   - Consider corpus size limits

### Logs and Debugging

```bash
# Enable verbose logging
export PYTHONPATH=/app
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Run your RAG operations
"
```

## Security Considerations

- Store service account keys securely
- Use VPC Service Controls for enhanced security
- Implement proper access controls on GCS buckets
- Regularly audit API usage and permissions

## Support

For issues with RAG Engine setup:
1. Check GCP Console > Vertex AI > RAG Engine
2. Review API documentation: https://cloud.google.com/vertex-ai/docs/generative-ai/rag-engine
3. Monitor Cloud Logging for detailed error messages
